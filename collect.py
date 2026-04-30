"""
collect.py — TruePay Dataset Collector
======================================
Collects real Pakistani banking app screenshots from official sources
and generates a synthetic fake dataset for calibration/testing.

Usage:
    python collect.py

Outputs:
    dataset/real/<bank>/   — real app screenshots
    dataset/fake/          — synthetically generated fake receipts
    dataset/metadata.json  — full image index with labels
"""

from __future__ import annotations

import io
import json
import os
import random
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

try:
    import requests
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageStat
    import numpy as np
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install requests Pillow numpy")
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
DATASET_DIR = ROOT / "dataset"
REAL_DIR    = DATASET_DIR / "real"
FAKE_DIR    = DATASET_DIR / "fake" / "generated"
META_FILE   = DATASET_DIR / "metadata.json"

for d in [REAL_DIR, FAKE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Bank definitions ──────────────────────────────────────────────────────────

BANKS = {
    "easypaisa": {
        "play_id": "pk.com.telenor.phoenix",
        "site_url": "https://www.easypaisa.com.pk",
        "brand_colour": (0, 155, 58),      # Easypaisa green
        "bg_colour": (255, 255, 255),
        "accent": (0, 100, 40),
        "success_text": "Successfully Sent",
        "app_name": "easypaisa",
    },
    "jazzcash": {
        "play_id": "com.techlogix.mobilinkcustomer",
        "site_url": "https://www.jazzcash.com.pk",
        "brand_colour": (230, 0, 0),        # JazzCash red
        "bg_colour": (255, 255, 255),
        "accent": (180, 0, 0),
        "success_text": "Payment Successful",
        "app_name": "JazzCash",
    },
    "hbl": {
        "play_id": "com.hbl.android.hblmobilebanking",
        "site_url": "https://www.hbl.com",
        "brand_colour": (0, 56, 147),       # HBL navy
        "bg_colour": (245, 248, 255),
        "accent": (0, 120, 200),
        "success_text": "Transfer Successful",
        "app_name": "HBL Mobile",
    },
    "ubl": {
        "play_id": "com.ubldigital.ubldigital",
        "site_url": "https://www.ubl.com.pk",
        "brand_colour": (0, 83, 155),       # UBL blue
        "bg_colour": (255, 255, 255),
        "accent": (0, 150, 220),
        "success_text": "Amount Transferred",
        "app_name": "UBL Digital",
    },
    "meezan": {
        "play_id": "com.meezanbank.meezan",
        "site_url": "https://www.meezanbank.com",
        "brand_colour": (0, 128, 0),        # Meezan green
        "bg_colour": (255, 255, 255),
        "accent": (0, 80, 0),
        "success_text": "Transfer Complete",
        "app_name": "Meezan Bank",
    },
    "sadapay": {
        "play_id": "com.sadapay.sadapay",
        "site_url": "https://www.sadapay.pk",
        "brand_colour": (255, 220, 0),      # SadaPay yellow
        "bg_colour": (30, 30, 30),
        "accent": (200, 170, 0),
        "success_text": "Sent Successfully",
        "app_name": "SadaPay",
    },
    "nayapay": {
        "play_id": "com.nayapay.app",
        "site_url": "https://www.nayapay.com",
        "brand_colour": (92, 45, 145),      # NayaPay purple
        "bg_colour": (248, 245, 255),
        "accent": (120, 80, 180),
        "success_text": "Payment Successful",
        "app_name": "NayaPay",
    },
    "mcblite": {
        "play_id": "com.mcb.mcblite",
        "site_url": "https://www.mcblite.com",
        "brand_colour": (0, 100, 60),       # MCB green
        "bg_colour": (255, 255, 255),
        "accent": (0, 60, 40),
        "success_text": "Successfully Sent",
        "app_name": "MCB Lite",
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

metadata: list[dict] = []


# ── Helper functions ──────────────────────────────────────────────────────────

def _save_meta(path: Path, label: str, bank: str, source: str) -> None:
    metadata.append({
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "label": label,
        "bank": bank,
        "source": source,
    })


def _download_image(url: str, dest: Path, bank: str, source: str) -> bool:
    """Download a single image URL, return True on success."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, stream=True)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        if "image" not in ctype and not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return False
        raw = resp.content
        img = Image.open(io.BytesIO(raw))
        # Verify it looks like a phone screenshot (portrait, reasonable size)
        w, h = img.size
        if w < 200 or h < 300:
            return False
        img.save(str(dest))
        _save_meta(dest, "real", bank, source)
        return True
    except Exception as e:
        print(f"    [skip] {url[:70]}... — {e}")
        return False


# ── Phase 1: Scrape Google Play Store app screenshots ─────────────────────────

PLAY_CDN_RE = re.compile(
    r'https://play-lh\.googleusercontent\.com/[A-Za-z0-9_\-=]+(?:=w\d+-h\d+[^\s"\'<>]*)?'
)

def _play_store_screenshots(bank_name: str, play_id: str) -> list[str]:
    """Parse Google Play Store page HTML to extract screenshot CDN URLs."""
    url = f"https://play.google.com/store/apps/details?id={play_id}&hl=en"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        resp.raise_for_status()
        raw_urls = PLAY_CDN_RE.findall(resp.text)
        # Deduplicate, prefer larger resolution
        seen = {}
        for u in raw_urls:
            base = u.split("=w")[0]
            if base not in seen:
                seen[base] = u
        # Return up to 8 unique screenshot URLs, requesting high-res
        results = []
        for base, original in list(seen.items())[:12]:
            # Request max size from CDN
            results.append(base + "=w540-h960-rw")
        return results
    except Exception as e:
        print(f"  [warn] Could not fetch Play Store page for {bank_name}: {e}")
        return []


def collect_real_screenshots() -> None:
    print("\n" + "=" * 60)
    print("  PHASE 1 — Collecting real bank app screenshots")
    print("=" * 60)

    for bank_name, info in BANKS.items():
        bank_dir = REAL_DIR / bank_name
        bank_dir.mkdir(exist_ok=True)

        print(f"\n  [{bank_name.upper()}]")
        print(f"    Fetching Play Store screenshots...")

        urls = _play_store_screenshots(bank_name, info["play_id"])
        if not urls:
            print(f"    No CDN URLs found — skipping online fetch for {bank_name}")
        else:
            saved = 0
            for i, img_url in enumerate(urls):
                dest = bank_dir / f"play_{i+1:02d}.jpg"
                if dest.exists():
                    print(f"    [exists] {dest.name}")
                    _save_meta(dest, "real", bank_name, "google_play")
                    saved += 1
                    continue
                ok = _download_image(img_url, dest, bank_name, "google_play")
                if ok:
                    saved += 1
                    print(f"    [saved]  {dest.name} ({img_url[40:70]}...)")
                time.sleep(0.3)
            print(f"    Saved {saved}/{len(urls)} images from Google Play")


# ── Phase 2: Generate synthetic fake receipts ──────────────────────────────────

# Standard phone receipt dimensions (portrait, ~540x960)
CANVAS_W = 540
CANVAS_H = 960


def _load_font(size: int) -> ImageFont.ImageFont:
    """Try to load a clean system font, fall back to default."""
    for fname in ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "Roboto-Regular.ttf"]:
        for sdir in [
            "C:/Windows/Fonts",
            "/usr/share/fonts/truetype/dejavu",
            "/System/Library/Fonts",
        ]:
            fp = Path(sdir) / fname
            if fp.exists():
                try:
                    return ImageFont.truetype(str(fp), size)
                except Exception:
                    pass
    return ImageFont.load_default()


def _draw_real_looking_receipt(
    bank: str,
    info: dict,
    amount: str = "Rs. 2,500.00",
    txn_id: str = "EP241029KLM99",
    recipient: str = "Ali Hassan",
    date: str = "29 Apr 2026",
    time_val: str = "03:45 PM",
) -> Image.Image:
    """
    Draw a synthetic receipt that looks like a real bank app screenshot.
    Used as a base for generating deliberately flawed fakes.
    """
    brand   = info["brand_colour"]
    bg      = info["bg_colour"]
    accent  = info["accent"]
    success = info["success_text"]
    appname = info["app_name"]

    img  = Image.new("RGB", (CANVAS_W, CANVAS_H), bg)
    draw = ImageDraw.Draw(img)

    f_large  = _load_font(28)
    f_medium = _load_font(20)
    f_small  = _load_font(16)
    f_tiny   = _load_font(13)

    # Status bar simulation
    draw.rectangle([(0, 0), (CANVAS_W, 36)], fill=brand)
    draw.text((16, 8),  appname,            font=f_small, fill=(255, 255, 255))
    draw.text((CANVAS_W - 90, 8), "9:41 AM", font=f_small, fill=(255, 255, 255))

    # Header bar
    draw.rectangle([(0, 36), (CANVAS_W, 110)], fill=brand)
    draw.text((CANVAS_W // 2 - 80, 55), "Transaction Receipt",
              font=f_medium, fill=(255, 255, 255))

    # Success circle / checkmark area
    draw.ellipse([(CANVAS_W // 2 - 40, 120), (CANVAS_W // 2 + 40, 200)],
                 fill=brand, outline=accent, width=3)
    draw.text((CANVAS_W // 2 - 8, 148), "✓", font=f_large, fill=(255, 255, 255))

    # Success label
    draw.text((CANVAS_W // 2 - 80, 212), success,
              font=f_medium, fill=brand)

    # Amount
    draw.text((CANVAS_W // 2 - 70, 255), amount,
              font=f_large, fill=(30, 30, 30))

    # Divider
    draw.line([(30, 300), (CANVAS_W - 30, 300)], fill=(200, 200, 200), width=1)

    # Detail rows
    rows = [
        ("Recipient",    recipient),
        ("Date",         date),
        ("Time",         time_val),
        ("Transaction ID", txn_id),
        ("Payment Method", "Mobile Wallet"),
        ("Status",       "Completed"),
    ]
    y = 315
    for label, value in rows:
        draw.text((30, y), label + ":",   font=f_small, fill=(130, 130, 130))
        draw.text((CANVAS_W - 30 - len(value) * 8, y), value,
                  font=f_small, fill=(30, 30, 30))
        draw.line([(30, y + 26), (CANVAS_W - 30, y + 26)],
                  fill=(235, 235, 235), width=1)
        y += 45

    # Footer
    draw.rectangle([(0, CANVAS_H - 60), (CANVAS_W, CANVAS_H)], fill=(245, 245, 245))
    draw.text((30, CANVAS_H - 42), "Keep this receipt for your records.",
              font=f_tiny, fill=(150, 150, 150))
    draw.text((CANVAS_W - 120, CANVAS_H - 42), appname,
              font=f_tiny, fill=(150, 150, 150))

    return img


def _generate_fake_rgba(base: Image.Image, dest: Path, bank: str) -> None:
    """Fake type 1: RGBA export — dead giveaway for real phone screenshots."""
    fake = base.convert("RGBA")
    fake.save(str(dest), format="PNG")
    _save_meta(dest, "fake", bank, "synthetic_rgba")


def _generate_fake_low_res(base: Image.Image, dest: Path, bank: str) -> None:
    """Fake type 2: Downscale to tiny resolution — real phones never produce <400px wide."""
    small = base.resize((320, 568), Image.LANCZOS)
    small.save(str(dest), format="PNG")
    _save_meta(dest, "fake", bank, "synthetic_lowres")


def _generate_fake_wrong_colour(info: dict, dest: Path, bank: str) -> None:
    """Fake type 3: Wrong brand colour — invert the RGB channels to make it completely wrong."""
    bad_info = {**info}
    r, g, b = info["brand_colour"]
    bad_info["brand_colour"] = (255 - r, 255 - g, 255 - b)
    ar, ag, ab = info["accent"]
    bad_info["accent"] = (255 - ar, 255 - ag, 255 - ab)
    fake = _draw_real_looking_receipt(bank, bad_info,
                                      amount="Rs. 9,999.00",
                                      txn_id="XFAKE12345XZ")
    fake.save(str(dest), format="JPEG", quality=92)
    _save_meta(dest, "fake", bank, "synthetic_wrong_colour")


def _generate_fake_ela_injected(base: Image.Image, dest: Path, bank: str) -> None:
    """Fake type 4: ELA-injected — paste a block of text from another image into this one."""
    # To create a real ELA signal, compress the background heavily
    buf = io.BytesIO()
    base.convert("RGB").save(buf, format="JPEG", quality=15)
    buf.seek(0)
    fake = Image.open(buf).convert("RGB")
    
    draw = ImageDraw.Draw(fake)
    # Paste a conspicuous bright rectangle and redraw the amount
    draw.rectangle([(60, 248), (400, 290)], fill=(240, 240, 240))
    f = _load_font(28)
    draw.text((65, 252), "Rs. 50,000.00", font=f, fill=(255, 0, 0))
    # Save at JPEG 100% to preserve the sharp paste edge and trigger ELA
    fake.save(str(dest), format="JPEG", quality=100)
    _save_meta(dest, "fake", bank, "synthetic_ela_injected")


def _generate_fake_flat_colour(info: dict, dest: Path, bank: str) -> None:
    """Fake type 5: Near-zero noise flat background — hallmark of AI/vector generation."""
    bg = info["bg_colour"]
    # Perfectly flat, zero-noise background
    fake = Image.new("RGB", (CANVAS_W, CANVAS_H), bg)
    draw = ImageDraw.Draw(fake)
    brand = info["brand_colour"]
    f_large  = _load_font(28)
    f_medium = _load_font(20)
    f_small  = _load_font(16)
    draw.rectangle([(0, 0), (CANVAS_W, 120)], fill=brand)
    draw.text((30, 45), info["success_text"], font=f_medium, fill=(255, 255, 255))
    draw.text((30, 160), "Rs. 3,000.00",     font=f_large,  fill=(30, 30, 30))
    draw.text((30, 220), "To: Bilal Raza",   font=f_small,  fill=(100, 100, 100))
    draw.text((30, 260), "Ref: FAKE99999",    font=f_small,  fill=(100, 100, 100))
    fake.save(str(dest), format="PNG")
    _save_meta(dest, "fake", bank, "synthetic_flat_colour")


def _generate_fake_wrong_aspect(info: dict, dest: Path, bank: str) -> None:
    """Fake type 6: Wrong aspect ratio — landscape or square, not phone portrait."""
    fake = _draw_real_looking_receipt(bank, info)
    # Crop to a square (non-phone aspect ratio)
    side = min(fake.size)
    fake = fake.crop((0, 0, side, side))
    fake.save(str(dest), format="JPEG", quality=88)
    _save_meta(dest, "fake", bank, "synthetic_wrong_aspect")


def generate_fake_receipts() -> None:
    print("\n" + "=" * 60)
    print("  PHASE 2 — Generating synthetic fake receipts")
    print("=" * 60)

    fake_types = [
        ("rgba",         _generate_fake_rgba,         "png"),
        ("lowres",       _generate_fake_low_res,       "png"),
        ("wrong_colour", None,                         "jpg"),
        ("ela_injected", _generate_fake_ela_injected,  "jpg"),
        ("flat_colour",  None,                         "png"),
        ("wrong_aspect", None,                         "jpg"),
    ]

    for bank_name, info in BANKS.items():
        print(f"\n  [{bank_name.upper()}]")
        base_img = _draw_real_looking_receipt(bank_name, info)

        for fake_type, fn, ext in fake_types:
            dest = FAKE_DIR / f"{bank_name}_{fake_type}.{ext}"
            if dest.exists():
                print(f"    [exists] {dest.name}")
                _save_meta(dest, "fake", bank_name, f"synthetic_{fake_type}")
                continue

            try:
                if fake_type == "rgba":
                    _generate_fake_rgba(base_img, dest, bank_name)
                elif fake_type == "lowres":
                    _generate_fake_low_res(base_img, dest, bank_name)
                elif fake_type == "wrong_colour":
                    _generate_fake_wrong_colour(info, dest, bank_name)
                elif fake_type == "ela_injected":
                    _generate_fake_ela_injected(base_img, dest, bank_name)
                elif fake_type == "flat_colour":
                    _generate_fake_flat_colour(info, dest, bank_name)
                elif fake_type == "wrong_aspect":
                    _generate_fake_wrong_aspect(info, dest, bank_name)
                print(f"    [gen]    {dest.name}")
            except Exception as e:
                print(f"    [error]  {dest.name}: {e}")


# ── Phase 3: Write metadata index ──────────────────────────────────────────────

def write_metadata() -> None:
    META_FILE.write_text(
        json.dumps({"images": metadata, "total": len(metadata)}, indent=2),
        encoding="utf-8",
    )
    real_count = sum(1 for m in metadata if m["label"] == "real")
    fake_count = sum(1 for m in metadata if m["label"] == "fake")
    print("\n" + "=" * 60)
    print("  PHASE 3 — Dataset index written")
    print("=" * 60)
    print(f"  Total images : {len(metadata)}")
    print(f"  Real         : {real_count}")
    print(f"  Fake         : {fake_count}")
    print(f"  Saved to     : {META_FILE}")


# ── Phase 4: Run engine against dataset and print calibration report ───────────

def calibration_report() -> None:
    # Force UTF-8 output on Windows to avoid cp1252 crash
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    print("\n" + "=" * 60)
    print("  PHASE 4 -- Engine calibration report")
    print("=" * 60)

    try:
        sys.path.insert(0, str(ROOT))
        from engine import analyse
    except ImportError as e:
        print(f"  [skip] Cannot import engine: {e}")
        return

    results = {"real": {"correct": 0, "total": 0}, "fake": {"correct": 0, "total": 0}}
    errors = []

    for entry in metadata:
        fpath = ROOT / entry["path"]
        label = entry["label"]
        bank  = entry["bank"]
        try:
            report = analyse(str(fpath), api_key="")
            verdict = report.final_verdict.lower()
            is_fake_verdict = "fake" in verdict
            if label == "real":
                results["real"]["total"] += 1
                if not is_fake_verdict:
                    results["real"]["correct"] += 1
                else:
                    errors.append(f"  FALSE POSITIVE: {entry['path']} -> {report.final_verdict}")
            else:
                results["fake"]["total"] += 1
                if is_fake_verdict or "suspicious" in verdict:
                    results["fake"]["correct"] += 1
                else:
                    errors.append(f"  MISSED FAKE:    {entry['path']} -> {report.final_verdict}")
        except Exception as e:
            errors.append(f"  ERROR: {entry['path']}: {e}")

    r = results["real"]
    f = results["fake"]
    rt = r["total"] or 1
    ft = f["total"] or 1
    print(f"  Real accuracy : {r['correct']}/{r['total']} ({100*r['correct']//rt}%)")
    print(f"  Fake accuracy : {f['correct']}/{f['total']} ({100*f['correct']//ft}%)")
    total = r["total"] + f["total"]
    correct = r["correct"] + f["correct"]
    tt = total or 1
    print(f"  Overall       : {correct}/{total} ({100*correct//tt}%)")
    if errors:
        print(f"\n  Misclassifications ({len(errors)}):")
        for err in errors[:20]:
            # Encode safely for Windows console
            safe = err.encode('ascii', errors='replace').decode('ascii')
            print(safe)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  TruePay Dataset Collector v1.0")
    print("  Real screenshots + synthetic fakes")
    print("=" * 60)

    collect_real_screenshots()
    generate_fake_receipts()
    write_metadata()
    calibration_report()

    print("\nDone. Dataset saved to:", DATASET_DIR)
