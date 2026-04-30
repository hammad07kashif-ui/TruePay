"""
engine.py — TruePay Detection Engine
Multi-bank Pakistani transaction screenshot verifier.
Offline forensics + optional Gemini Vision AI layer.
"""
# Encoding: UTF-8

from __future__ import annotations

import io
import os
import re
import socket
import struct
import zlib
from dataclasses import dataclass, field
from typing import Optional

# Bank reference profiles for the 6th forensic algorithm
try:
    from bank_profiles import get_profile as _get_bank_profile
except ImportError:
    def _get_bank_profile(platform: str):  # type: ignore[misc]
        return None

# ── Third-party ───────────────────────────────────────────────────────────────
try:
    import cv2
    import numpy as np
    from PIL import Image, ImageEnhance, ImageFilter, ImageStat
    import pytesseract
    import google.generativeai as genai
except ImportError as exc:
    raise ImportError(
        f"Missing dependency: {exc}\n"
        "Run: pip install customtkinter opencv-python Pillow pytesseract "
        "google-generativeai numpy scikit-image requests scipy"
    ) from exc

# Windows default Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ── Bank / Platform keyword table ─────────────────────────────────────────────
BANK_KEYWORDS: dict[str, list[str]] = {
    "Easypaisa":  ["easypaisa", "easy paisa", "telenor microfinance"],
    "JazzCash":   ["jazzcash", "jazz cash", "mobilink microfinance"],
    "HBL":        ["hbl", "habib bank", "hbl mobile", "hblpay"],
    "UBL":        ["ubl", "united bank", "ubl omni", "omni"],
    "Meezan":     ["meezan", "meezan bank", "meezan internet"],
    "SadaPay":    ["sadapay", "sada pay"],
    "NayaPay":    ["nayapay", "naya pay"],
    "Raast":      ["raast", "1link", "ibft"],
    "MCB":        ["mcb", "muslim commercial bank", "mcb lite"],
    "Allied":     ["allied bank", "abl"],
    "BankIslami": ["bankislami", "bank islami"],
    "Zindigi":    ["zindigi"],
    "NBP":        ["nbp", "national bank of pakistan"],
    "SCB":        ["standard chartered", "scb"],
    "Faysal":     ["faysal bank"],
    "ZTBL":       ["ztbl", "zarai taraqiati bank"],
}

# Confirmation/success phrases per bank (positive OCR signals)
SUCCESS_PHRASES: list[str] = [
    r"successfully\s+sent",
    r"transaction\s+successful",
    r"payment\s+successful",
    r"transfer\s+successful",
    r"transfer\s+complete",
    r"amount\s+transferred",
    r"sent\s+successfully",
    r"payment\s+received",
    r"credited\s+successfully",
    r"debit\s+successful",
]

# ── Regex patterns ─────────────────────────────────────────────────────────────
AMOUNT_RE = [
    re.compile(r"Rs\.?\s*[\d,]+(?:\.\d+)?", re.I),
    re.compile(r"PKR\s*[\d,]+(?:\.\d+)?", re.I),
    re.compile(r"Rs\s*\n\s*[\d,]+(?:\.\d+)?", re.I),
    re.compile(r"[\d,]+(?:\.\d{2})?\s*(?:Rs|PKR)", re.I),
]
DATE_RE = [
    re.compile(r"\b\d{1,2}[/\-]\d{1,2}[/\-]\d{4}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(
        r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b",
        re.I,
    ),
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b", re.I),
]
TIME_RE = [
    re.compile(r"\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)\b"),
    re.compile(r"\b\d{2}:\d{2}:\d{2}\b"),
    re.compile(r"\b\d{2}:\d{2}\b"),
]
IBAN_RE = re.compile(r"\bPK\d{2}[A-Z]{4}\d{16}\b")
TXN_IGNORE = {
    "easypaisa", "jazzcash", "receipt", "payment", "status", "successful",
    "amount", "date", "time", "transfer", "transaction", "balance", "account",
    "sadapay", "hbl", "ubl", "meezan", "wallet", "mobile", "method", "number",
    "recipient", "sender", "total", "view", "share", "confirm", "receiver",
    "bank", "sent", "money", "important", "details", "successfully", "nayapay",
    "allied", "meezan", "raast", "ibft", "zindigi", "bankislami", "faysal",
}


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class ForensicResult:
    score: int                      # 0–100, higher = more suspicious
    notes: list[str] = field(default_factory=list)
    ela_score: int = 0
    noise_score: int = 0
    edge_score: int = 0
    exif_score: int = 0
    heuristic_score: int = 0
    profile_score: int = 0


@dataclass
class OCRResult:
    text: str
    platform: str
    amount: str
    date: str
    time_val: str
    txn_id: str
    iban: str
    confirmation: str
    missing_fields: list[str] = field(default_factory=list)


@dataclass
class VisualResult:
    verdict: str        # Authentic | Suspicious | Fake | Unknown
    findings: list[str] = field(default_factory=list)
    summary: str = ""
    error: str = ""


@dataclass
class Report:
    filepath: str
    platform: str
    ocr: OCRResult
    forensics: ForensicResult
    visual: VisualResult
    final_verdict: str
    confidence: int     # 0–100
    internet_used: bool = False


class ImageError(Exception):
    pass


# ── Image loading ──────────────────────────────────────────────────────────────
SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"}


def load_image(path: str) -> Image.Image:
    if not os.path.exists(path):
        raise ImageError(f"File not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXT:
        raise ImageError(
            f"Unsupported format '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXT))}"
        )
    try:
        img = Image.open(path)
        img.verify()
        return Image.open(path)  # reopen after verify()
    except Exception as exc:
        raise ImageError(f"Cannot open image: {exc}") from exc


# ── Platform detection ─────────────────────────────────────────────────────────

def detect_platform(text: str) -> str:
    lower = text.lower()
    for bank, keywords in BANK_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return bank
    return "Unknown Bank"


# ── OCR pipeline ───────────────────────────────────────────────────────────────

def _preprocess(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    grey = img.convert("L")
    w, h = grey.size
    if w < 800:
        grey = grey.resize((w * 2, h * 2), Image.LANCZOS)
    grey = ImageEnhance.Contrast(grey).enhance(2.0)
    grey = ImageEnhance.Sharpness(grey).enhance(2.5)
    grey = grey.filter(ImageFilter.SHARPEN)
    return grey


def extract_text(img: Image.Image) -> str:
    processed = _preprocess(img)
    cfg6 = "--psm 6 --oem 1"
    cfg11 = "--psm 11 --oem 1"
    t1 = pytesseract.image_to_string(processed, config=cfg6)
    t2 = pytesseract.image_to_string(processed, config=cfg11)
    raw_img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
    t3 = pytesseract.image_to_string(raw_img, config=cfg6)
    return max([t1, t2, t3], key=lambda s: len(s.strip()))


def _first(patterns: list, text: str) -> str:
    for p in patterns:
        m = p.search(text)
        if m:
            return re.sub(r"\s+", " ", m.group(0)).strip()
    return ""


def run_ocr(img: Image.Image) -> OCRResult:
    text = extract_text(img)
    platform = detect_platform(text)

    amount = _first(AMOUNT_RE, text)
    date = _first(DATE_RE, text)
    time_val = _first(TIME_RE, text)
    iban = (IBAN_RE.search(text) or type("", (), {"group": lambda s, x="": ""})()).group(0)

    txn_id = ""
    for m in re.finditer(r"\b[A-Za-z0-9]{6,}\b", text):
        v = m.group(0)
        if v.lower() not in TXN_IGNORE and not v.isdigit():
            txn_id = v
            break

    confirmation = ""
    for pat in SUCCESS_PHRASES:
        if re.search(pat, text, re.I):
            confirmation = re.search(pat, text, re.I).group(0).title()
            break

    missing = [f for f, v in [("amount", amount), ("date", date), ("time", time_val), ("txn_id", txn_id)] if not v]
    return OCRResult(text, platform, amount, date, time_val, txn_id, iban, confirmation, missing)


# ── FORENSICS: 5 Algorithms ────────────────────────────────────────────────────

# --- 1. Error Level Analysis (ELA) ---

def _ela(img: Image.Image) -> tuple[int, str]:
    """
    Re-save at JPEG quality=90, diff against original.
    Heavily edited regions show high residuals vs. untouched areas.
    Score 0–30.
    """
    try:
        rgb = img.convert("RGB")
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        recompressed = Image.open(buf).convert("RGB")

        orig_np = np.array(rgb, dtype=np.float32)
        comp_np = np.array(recompressed, dtype=np.float32)
        diff = np.abs(orig_np - comp_np)

        mean_diff = float(diff.mean())
        std_diff = float(diff.std())
        max_diff = float(diff.max())

        # High mean + high std → typical of edited composites
        # Very low mean + low std → AI-generated flat graphic
        if mean_diff < 0.5 and std_diff < 0.5:
            return 20, f"ELA: Near-zero residual (mean={mean_diff:.2f}) — consistent with AI-generated image."
        elif mean_diff > 15 or std_diff > 20:
            return 25, f"ELA: High residual variance (mean={mean_diff:.2f}, std={std_diff:.2f}) — signs of editing."
        elif mean_diff > 8 or (max_diff > 40 and std_diff > 1.1):
            return 12, f"ELA: Moderate residual (mean={mean_diff:.2f}, std={std_diff:.2f}, max={max_diff:.0f}) — minor editing possible."
        else:
            return 0, f"ELA: Normal residual (mean={mean_diff:.2f}) — consistent with real screenshot."
    except Exception as e:
        return 0, f"ELA: Skipped ({e})"


# --- 2. Noise Fingerprinting ---

def _noise(img: Image.Image) -> tuple[int, str]:
    """
    Real JPEG screenshots have characteristic high-frequency sensor/compression noise.
    AI-generated PNGs have near-zero noise in uniform regions.
    Score 0–25.
    """
    try:
        grey = np.array(img.convert("L"), dtype=np.float32)
        # Gaussian blur removes low-freq content; residual is the noise
        blurred = cv2.GaussianBlur(grey, (5, 5), 0)
        noise_map = np.abs(grey - blurred)
        noise_mean = float(noise_map.mean())
        noise_std = float(noise_map.std())

        if noise_mean < 0.8:
            return 22, f"Noise: Virtually zero noise (μ={noise_mean:.2f}) — hallmark of AI/vector-generated image."
        elif noise_mean < 2.0:
            return 12, f"Noise: Very low noise (μ={noise_mean:.2f}) — possibly a non-real-photo screenshot."
        elif noise_mean > 12:
            return 8, f"Noise: Unusually high noise (μ={noise_mean:.2f}) — may indicate heavy JPEG compression or editing."
        else:
            return 0, f"Noise: Natural noise level (μ={noise_mean:.2f}) — consistent with real device screenshot."
    except Exception as e:
        return 0, f"Noise: Skipped ({e})"


# --- 3. Edge Density (Canny) ---

def _edge_density(img: Image.Image) -> tuple[int, str]:
    """
    Real phone UI screenshots have a characteristic density of edges (text, icons, dividers).
    Too few edges = blank/flat AI graphic. Too many = noise or severe JPEG blocking.
    Score 0–20.
    Note: WhatsApp-forwarded/compressed real receipts can have low edge density — threshold
    is relaxed to 0.008 to avoid false positives on genuine images.
    """
    try:
        grey = np.array(img.convert("L"), dtype=np.uint8)
        edges = cv2.Canny(grey, threshold1=50, threshold2=150)
        density = float(np.count_nonzero(edges)) / float(edges.size)

        if density < 0.008:
            return 18, f"Edge Density: Very sparse ({density:.3f}) — image lacks UI structure; possibly blank or AI-generated."
        elif density < 0.02:
            return 6, f"Edge Density: Sparse ({density:.3f}) — lower than typical phone UI; may be WhatsApp-compressed."
        elif density > 0.35:
            return 15, f"Edge Density: Extremely high ({density:.3f}) — excessive noise or JPEG blocking detected."
        elif 0.02 <= density <= 0.30:
            return 0, f"Edge Density: Normal for phone UI ({density:.3f}) — consistent with real screenshot."
        else:
            return 5, f"Edge Density: Slightly off ({density:.3f}) — minor anomaly."
    except Exception as e:
        return 0, f"Edge Density: Skipped ({e})"


# --- 4. EXIF Metadata Inspection ---

def _exif(img: Image.Image) -> tuple[int, str]:
    """
    Real phone screenshots have minimal/no EXIF.
    Edited images may carry Adobe/Photoshop/GIMP software tags.
    Score 0–15.
    """
    try:
        exif_data = img._getexif() if hasattr(img, "_getexif") else None
        if exif_data is None:
            info = img.info or {}
            # PNG metadata check
            software = str(info.get("Software", "") or info.get("Comment", "")).lower()
            if any(kw in software for kw in ["photoshop", "gimp", "illustrator", "canva", "adobe"]):
                return 15, f"EXIF: Editing software detected in PNG metadata: '{software[:60]}'"
            # No EXIF at all — neutral for PNG (expected), slightly suspicious for JPEG
            fmt = (getattr(img, "format", "") or "").upper()
            if fmt == "JPEG":
                return 5, "EXIF: No EXIF in JPEG — stripped metadata can indicate editing."
            return 0, "EXIF: No metadata (expected for phone screenshot PNG)."

        # Parse EXIF tags
        from PIL.ExifTags import TAGS
        decoded = {TAGS.get(k, k): v for k, v in exif_data.items()}
        software = str(decoded.get("Software", "")).lower()
        make = str(decoded.get("Make", "")).lower()
        model_tag = str(decoded.get("Model", "")).lower()

        edit_kws = ["photoshop", "gimp", "illustrator", "canva", "adobe", "picsart", "snapseed", "lightroom"]
        if any(kw in software for kw in edit_kws):
            return 15, f"EXIF: Photo-editing software tag found: '{decoded.get('Software', '')[:60]}'"
        if make or model_tag:
            return 0, f"EXIF: Device metadata present (Make={make or '?'}, Model={model_tag or '?'}) — consistent with real photo."
        return 3, "EXIF: EXIF present but no device info — possibly stripped or edited."
    except Exception as e:
        return 0, f"EXIF: Skipped ({e})"


# --- 5. Colour & Format Heuristics ---

def _heuristics(img: Image.Image) -> tuple[int, list[str]]:
    """
    Combined pixel-level heuristics, calibrated for Pakistani banking receipts.
    RGBA + tiny resolution together are the strongest fake signal.
    Score 0-50 (increased cap to correctly catch AI-generated PNGs).
    """
    notes: list[str] = []
    score = 0
    w, h = img.size
    fmt = (getattr(img, "format", "") or "").upper()
    is_rgba = (img.mode == "RGBA")

    # Alpha channel — real phone screenshots are NEVER RGBA
    if is_rgba:
        notes.append("Format: Alpha channel (RGBA) detected — real screenshots are always RGB/JPEG.")
        score += 35

    # Resolution
    pixels = w * h
    if pixels < 400_000:
        notes.append(f"Resolution: Very low ({w}x{h} = {pixels:,}px) — real phone screenshots exceed 1M pixels.")
        score += 30
    elif pixels < 900_000:
        notes.append(f"Resolution: Below average ({w}x{h}) — may not be a real phone screenshot.")
        score += 12
    else:
        notes.append(f"Resolution: {w}x{h} ({pixels:,}px) — within range of a real phone screenshot.")

    # Aspect ratio
    ratio = h / w if w > 0 else 0
    if ratio < 1.5 or ratio > 2.8:
        notes.append(f"Aspect Ratio: {ratio:.2f} — outside standard phone portrait range (1.5-2.8).")
        score += 18

    # Colour variance
    try:
        stat = ImageStat.Stat(img.convert("RGB"))
        avg_std = sum(stat.stddev) / max(len(stat.stddev), 1)
        if avg_std < 18:
            notes.append(f"Colour Variance: Extremely flat (s={avg_std:.1f}) — hallmark of AI-generated graphic.")
            score += 28
        elif avg_std < 32:
            notes.append(f"Colour Variance: Low (s={avg_std:.1f}) — possibly a simplified design graphic.")
            score += 12
        else:
            notes.append(f"Colour Variance: Normal (s={avg_std:.1f}) — consistent with real screenshot.")
    except Exception:
        pass

    # Format bonus/penalty
    if fmt == "JPEG":
        notes.append("Format: JPEG — consistent with a real phone screenshot or WhatsApp-forwarded image.")
        score = max(0, score - 14)
    elif fmt == "PNG" and is_rgba:
        notes.append("Format: PNG+RGBA — typical of AI-generated or Canva-designed graphics.")
        score += 8  # extra penalty on top of RGBA flag

    return min(score, 50), notes


# --- 6. Bank Profile Matching ---

def _bank_profile_match(img: Image.Image, platform: str, img_format: str = "") -> tuple[int, str]:
    """
    Compares the image's dominant colour against the detected bank's known
    brand colour signature. A receipt claiming to be Easypaisa but lacking
    any green pixels, or HBL with no blue, scores high suspicion.
    Note: colour penalty is only applied to PNG/non-JPEG images since JPEG
    compression (e.g., WhatsApp forwarding) can desaturate brand colours.
    Score 0-25.
    """
    profile = _get_bank_profile(platform)
    if profile is None or platform == "Unknown Bank":
        return 0, "Bank Profile: No profile available for this platform — check skipped."

    try:
        import cv2 as _cv2
        import numpy as _np

        rgb = img.convert("RGB")
        w, h = rgb.size

        # --- Check 1: Aspect ratio vs profile ---
        ratio = h / w if w > 0 else 0
        ar_min = profile["expected_aspect_min"]
        ar_max = profile["expected_aspect_max"]
        ar_penalty = 0
        ar_note = ""
        if ratio < ar_min or ratio > ar_max:
            ar_penalty = 12
            ar_note = (f" Aspect ratio {ratio:.2f} outside expected range "
                       f"{ar_min}-{ar_max} for {platform}.")

        # --- Check 2: Resolution vs profile ---
        pixels = w * h
        min_mp = profile["min_resolution_mp"] * 1_000_000
        res_penalty = 0
        res_note = ""
        if pixels < min_mp:
            res_penalty = 10
            res_note = (f" Resolution {w}x{h} ({pixels/1e6:.2f}MP) below expected "
                        f"{profile['min_resolution_mp']:.1f}MP for {platform}.")

        # --- Check 3: Dominant brand colour match ---
        img_np = _np.array(rgb, dtype=_np.uint8)
        hsv    = _cv2.cvtColor(img_np, _cv2.COLOR_RGB2HSV)

        hue_min, hue_max = profile["dominant_hue_range"]
        sat_min          = profile["dominant_sat_min"]
        val_min          = profile["dominant_val_min"]

        # Build HSV mask for brand colour
        lower = _np.array([hue_min, sat_min, val_min], dtype=_np.uint8)
        upper = _np.array([hue_max, 255, 255],         dtype=_np.uint8)
        mask  = _cv2.inRange(hsv, lower, upper)

        # Handle red hue wrap-around (0-10 and 165-180)
        if hue_min < 10:
            lower2 = _np.array([165, sat_min, val_min], dtype=_np.uint8)
            upper2 = _np.array([180, 255, 255],          dtype=_np.uint8)
            mask   = _cv2.bitwise_or(mask, _cv2.inRange(hsv, lower2, upper2))

        brand_ratio = float(_np.count_nonzero(mask)) / float(mask.size)

        colour_penalty = 0
        colour_note = ""
        # Real receipts only have brand colour in the header bar:
        # e.g., 36px header in a 1170x2067 screen = ~0.18% of pixels.
        # WhatsApp compression can reduce this further (e.g. 0.10%).
        # 0.05% threshold catches completely wrong-coloured fakes
        # while tolerating genuine compact-header compressed receipts.
        if brand_ratio < 0.0005:   # definitely wrong colour for this bank
            colour_penalty = 25
            colour_note = (f" Brand colour ({profile['brand_colour_rgb']}) covers only "
                           f"{brand_ratio*100:.3f}% of pixels — mismatched or wrong bank claimed.")
        elif brand_ratio < 0.015:
            colour_penalty = 8
            colour_note = (f" Brand colour present but sparse ({brand_ratio*100:.2f}%).")
        else:
            colour_note = (f" Brand colour present ({brand_ratio*100:.1f}%) — consistent "
                           f"with {platform}.")

        total_penalty = min(ar_penalty + res_penalty + colour_penalty, 25)
        note = f"Bank Profile ({platform}):{ar_note}{res_note}{colour_note}"
        return total_penalty, note

    except Exception as e:
        return 0, f"Bank Profile: Skipped ({e})"


# ── Forensics orchestrator ─────────────────────────────────────────────────────

def run_forensics(img: Image.Image, platform: str = "Unknown Bank") -> ForensicResult:
    ela_s, ela_note     = _ela(img)
    noise_s, noise_note = _noise(img)
    edge_s, edge_note   = _edge_density(img)
    exif_s, exif_note   = _exif(img)
    heur_s, heur_notes  = _heuristics(img)
    prof_s, prof_note   = _bank_profile_match(
        img, platform,
        img_format=(getattr(img, "format", "") or ""),
    )

    notes = [ela_note, noise_note, edge_note, exif_note, prof_note] + heur_notes
    # max raw: ELA(30) + Noise(25) + Edge(20) + EXIF(15) + Profile(25) + Heuristics(50) = 165
    raw   = ela_s + noise_s + edge_s + exif_s + heur_s + prof_s
    score = min(int(raw * 100 / 165), 100)

    return ForensicResult(
        score=score,
        notes=notes,
        ela_score=ela_s,
        noise_score=noise_s,
        edge_score=edge_s,
        exif_score=exif_s,
        heuristic_score=heur_s,
        profile_score=prof_s,
    )


# ── Internet check ─────────────────────────────────────────────────────────────

def has_internet(timeout: float = 2.0) -> bool:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=timeout)
        return True
    except OSError:
        return False


# ── Gemini Vision layer ────────────────────────────────────────────────────────

GEMINI_PROMPT = """You are a digital forensics expert specialising in Pakistani mobile banking apps.

Examine this transaction receipt screenshot carefully.

Supported apps include: Easypaisa, JazzCash, HBL Mobile, UBL Omni, Meezan Bank, SadaPay, NayaPay, Raast, MCB, Allied Bank, BankIslami, Zindigi, NBP, Standard Chartered, Faysal Bank.

Determine if this is REAL (genuine screenshot from a device) or FAKE (AI-generated, Photoshopped, or edited).

Check specifically:
1. Phone status bar (time, signal bars, battery) — realistic vs. missing/fake
2. Font rendering — real screens have sub-pixel rendering; AI images have unnaturally perfect fonts
3. UI layout consistency with the detected banking app's real interface
4. JPEG compression artefacts — real photos have them; AI PNGs do not
5. Signs of copy-paste, compositing, or layer editing (misaligned text, inconsistent shadows)
6. Amount, date, and transaction ID format — do they match real app conventions?
7. Colour accuracy — does the colour scheme match the real app?

Respond EXACTLY in this format:
VERDICT: <Authentic|Suspicious|Fake>
FINDINGS:
- <finding 1>
- <finding 2>
- <finding 3>
SUMMARY: <one concise paragraph>
"""


def _parse_gemini(resp: str) -> VisualResult:
    v = re.search(r"VERDICT:\s*(Authentic|Suspicious|Fake)", resp, re.I)
    if not v:
        return VisualResult("Unknown", [], "", "Could not parse AI verdict.")
    verdict = v.group(1).capitalize()

    findings: list[str] = []
    fm = re.search(r"FINDINGS:\s*(.*?)(?=SUMMARY:|$)", resp, re.S | re.I)
    if fm:
        findings = [ln.strip().lstrip("-• ").strip() for ln in fm.group(1).splitlines() if ln.strip()]

    summary = ""
    sm = re.search(r"SUMMARY:\s*(.*)", resp, re.S | re.I)
    if sm:
        summary = sm.group(1).strip()

    return VisualResult(verdict, findings, summary)


def run_gemini(img: Image.Image, api_key: str) -> VisualResult:
    if not api_key:
        return VisualResult("Unknown", [], "", "No API key provided.")
    if not has_internet():
        return VisualResult("Unknown", [], "", "No internet connection — AI layer skipped.")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        response = model.generate_content([
            GEMINI_PROMPT,
            {"mime_type": "image/png", "data": buf.getvalue()},
        ])
        return _parse_gemini(response.text)
    except Exception as exc:
        return VisualResult("Unknown", [], "", str(exc))


# ── Verdict assembly ───────────────────────────────────────────────────────────

def _count_positive_ocr(ocr: OCRResult) -> int:
    return sum([
        bool(ocr.amount),
        bool(ocr.date),
        bool(ocr.time_val),
        bool(ocr.txn_id),
        bool(ocr.confirmation),
        bool(ocr.iban),
    ])


def assemble_verdict(ocr: OCRResult, forensics: ForensicResult, visual: VisualResult) -> tuple[str, int]:
    """
    Returns (verdict_string, confidence_0_to_100).
    Priority: Visual AI > Hard forensic rules > Forensic score > OCR.
    """
    fs = forensics.score
    positive_ocr = _count_positive_ocr(ocr)
    vv = visual.verdict

    # Check note strings for key forensic flags
    note_text = " ".join(forensics.notes).lower()
    has_rgba    = "alpha channel (rgba)" in note_text
    has_tiny_res = "very low" in note_text and "resolution" in note_text
    has_png_rgba = "png+rgba" in note_text

    # --- AI verdict takes priority ---
    if vv == "Fake":
        conf = min(70 + fs // 5, 99)
        return "Likely Fake", conf

    if vv == "Authentic":
        if fs >= 55:
            return "Suspicious - AI says Authentic but forensics disagree", 55
        conf = max(70, 95 - fs)
        return "Likely Authentic", conf

    if vv == "Suspicious":
        if fs >= 40:
            return "Likely Fake", min(60 + fs // 4, 95)
        return "Suspicious", 50

    # --- No AI verdict: offline rules ---

    # Check additional note flags
    has_below_avg_res = "below average" in note_text and "resolution" in note_text
    has_flat_colour   = "extremely flat" in note_text
    has_low_colour    = "colour variance: low" in note_text
    has_profile_mismatch = "brand colour" in note_text and "mismatched" in note_text
    fmt_is_jpeg = "format: jpeg" in note_text

    # Hard rule: RGBA + tiny resolution = near-certain design-tool fake
    if has_rgba and has_tiny_res:
        return "Likely Fake", min(75 + fs // 5, 95)

    # Hard rule: PNG+RGBA alone is very suspicious
    if has_png_rgba:
        if fs >= 30:
            return "Likely Fake", min(65 + fs // 4, 92)
        return "Suspicious - PNG with transparency is unusual for real receipts", 55

    # Hard rule: Brand colour completely wrong for the declared bank
    # Exception: real WhatsApp-forwarded JPEGs can have muted/washed colours —
    # but only exempt if the overall suspicion score is very low (genuine compressed receipt)
    jpeg_colour_exempt = fmt_is_jpeg and bool(ocr.confirmation) and fs < 15
    if has_profile_mismatch and not jpeg_colour_exempt:
        if fs >= 15:
            return "Likely Fake", min(60 + fs // 3, 90)
        return "Suspicious - colour signature does not match declared bank", 52

    # Hard rule: Flat image (near-zero variance) = AI/vector generated
    if has_flat_colour:
        return "Likely Fake", min(55 + fs // 3, 88)

    # Hard rule: Very low resolution on a non-JPEG (= design tool, not real phone)
    if has_tiny_res and not fmt_is_jpeg:
        return "Likely Fake", min(60 + fs // 4, 88)

    if fs >= 55:
        return "Likely Fake", min(55 + fs // 3, 92)
    if fs >= 35:
        if positive_ocr >= 4 or bool(ocr.confirmation):
            return "Suspicious - forensic flags present but OCR content looks real", 45
        return "Suspicious", 50
    if fs >= 22:
        # Moderate suspicion — flag for review
        if not fmt_is_jpeg or has_below_avg_res:
            return "Suspicious", 48
    # Low forensic suspicion
    if positive_ocr >= 3 or bool(ocr.confirmation):
        return "Likely Authentic", max(62, 85 - fs)
    return "Suspicious - provide Gemini API key for stronger analysis", 40


# ── Main entry point ───────────────────────────────────────────────────────────

def analyse(image_path: str, api_key: str = "") -> Report:
    img = load_image(image_path)
    ocr = run_ocr(img)
    forensics = run_forensics(img, platform=ocr.platform)

    online = has_internet() and bool(api_key)
    visual = run_gemini(img, api_key) if online else VisualResult(
        "Unknown", [], "",
        "Offline mode — add Gemini API key and ensure internet access for AI analysis."
        if not api_key else "No internet connection — AI layer skipped."
    )

    verdict_text, confidence = assemble_verdict(ocr, forensics, visual)
    # Prefix emoji icons for display
    _icons = {"Likely Fake": "Likely Fake", "Likely Authentic": "Likely Authentic", "Suspicious": "Suspicious"}
    verdict = verdict_text
    return Report(
        filepath=image_path,
        platform=ocr.platform,
        ocr=ocr,
        forensics=forensics,
        visual=visual,
        final_verdict=verdict,
        confidence=confidence,
        internet_used=online,
    )
