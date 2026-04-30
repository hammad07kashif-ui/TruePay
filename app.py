"""
TruePay - Pakistani Banking Receipt Verifier
Beautiful customtkinter GUI with offline forensics + Gemini Vision AI.
Run: python app.py
"""

from __future__ import annotations
import sys
import io
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import os
import threading
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk

# ── Colour tokens ─────────────────────────────────────────────────────────────
BG_DARK    = "#0d1b2a"
BG_PANEL   = "#112236"
BG_CARD    = "#162b40"
BG_HOVER   = "#1e3a52"
TEAL       = "#00c4cc"
TEAL_DARK  = "#009aa0"
AMBER      = "#f5a623"
RED        = "#e05252"
GREEN      = "#3ecf8e"
MUTED      = "#7a94a8"
TEXT_MAIN  = "#e8f0f7"
TEXT_DIM   = "#8fa8be"
FONT_MAIN  = "Segoe UI"

# ── CustomTkinter appearance ──────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ── Helper widgets ─────────────────────────────────────────────────────────────

def _label(parent, text, size=13, weight="normal", color=TEXT_MAIN, **kw):
    return ctk.CTkLabel(parent, text=text,
                        font=(FONT_MAIN, size, weight), text_color=color, **kw)


def _sep(parent, color="#1e3a52", height=1):
    return tk.Frame(parent, bg=color, height=height)


class GradientHeader(tk.Canvas):
    """Simple two-stop horizontal gradient banner."""
    def __init__(self, parent, h=6, **kw):
        super().__init__(parent, height=h, bd=0, highlightthickness=0, **kw)
        self.bind("<Configure>", self._draw)

    def _draw(self, _=None):
        self.delete("all")
        w = self.winfo_width() or 800
        stops = [(0, 0x00, 0xC4, 0xCC), (1, 0xF5, 0xA6, 0x23)]
        steps = max(w, 1)
        for i in range(steps):
            r = int(stops[0][1] + (stops[1][1] - stops[0][1]) * i / steps)
            g = int(stops[0][2] + (stops[1][2] - stops[0][2]) * i / steps)
            b = int(stops[0][3] + (stops[1][3] - stops[0][3]) * i / steps)
            self.create_line(i, 0, i, 6, fill=f"#{r:02x}{g:02x}{b:02x}")


class AnimatedButton(ctk.CTkButton):
    def __init__(self, *a, **kw):
        kw.setdefault("corner_radius", 10)
        kw.setdefault("fg_color", TEAL)
        kw.setdefault("hover_color", TEAL_DARK)
        kw.setdefault("text_color", "#000000")
        kw.setdefault("font", (FONT_MAIN, 13, "bold"))
        super().__init__(*a, **kw)


# ── Main Application ───────────────────────────────────────────────────────────

class TruePayApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TruePay — Pakistani Receipt Verifier")
        self.geometry("1100x720")
        self.minsize(900, 620)
        self.configure(fg_color=BG_DARK)

        self._image_path: Optional[str] = None
        self._api_key_var = ctk.StringVar()
        self._status_var = ctk.StringVar(value="Upload a receipt screenshot to begin.")
        self._analysing = False

        self._build_layout()
        self._bind_drop()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        GradientHeader(self, bg=BG_DARK).pack(fill="x")

        body = tk.Frame(self, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=0, pady=0)

        self._sidebar = self._build_sidebar(body)
        self._sidebar.pack(side="left", fill="y", padx=0, pady=0)

        right = tk.Frame(body, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True, padx=18, pady=18)

        self._upload_zone = self._build_upload_zone(right)
        self._upload_zone.pack(fill="x")

        self._results_frame = self._build_results(right)
        self._results_frame.pack(fill="both", expand=True, pady=(14, 0))

    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=BG_PANEL, width=240)
        sb.pack_propagate(False)

        # Logo area
        logo_frame = tk.Frame(sb, bg=BG_PANEL)
        logo_frame.pack(fill="x", padx=20, pady=(22, 8))

        _label(logo_frame, "TruePay", size=22, weight="bold", color=TEAL).pack(anchor="w")
        _label(logo_frame, "Receipt Authenticity Verifier", size=10, color=TEXT_DIM).pack(anchor="w")

        _sep(sb, color="#1e3a52", height=1).pack(fill="x", padx=16, pady=10)

        # API Key
        key_frame = tk.Frame(sb, bg=BG_PANEL)
        key_frame.pack(fill="x", padx=16, pady=(0, 6))
        _label(key_frame, "Gemini API Key", size=11, color=TEXT_DIM).pack(anchor="w", pady=(0, 4))
        self._key_entry = ctk.CTkEntry(
            key_frame, textvariable=self._api_key_var,
            placeholder_text="Paste key for AI analysis…",
            show="*", width=208,
            fg_color=BG_CARD, border_color=TEAL_DARK,
            text_color=TEXT_MAIN, font=(FONT_MAIN, 11),
        )
        self._key_entry.pack(fill="x")

        toggle_row = tk.Frame(key_frame, bg=BG_PANEL)
        toggle_row.pack(fill="x", pady=(6, 0))
        self._show_key_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            toggle_row, text="Show key", variable=self._show_key_var,
            command=self._toggle_key_vis,
            fg_color=TEAL, hover_color=TEAL_DARK,
            text_color=TEXT_DIM, font=(FONT_MAIN, 10),
            width=16, height=16, checkbox_width=14, checkbox_height=14,
        ).pack(side="left")

        _sep(sb, color="#1e3a52").pack(fill="x", padx=16, pady=12)

        # Supported banks
        _label(sb, "Supported Banks", size=11, weight="bold", color=MUTED).pack(anchor="w", padx=16)
        banks = [
            "Easypaisa", "JazzCash", "HBL", "UBL", "Meezan",
            "SadaPay", "NayaPay", "Raast", "MCB", "Allied Bank",
            "BankIslami", "Zindigi", "NBP", "SCB", "Faysal", "ZTBL",
        ]
        bank_scroll = tk.Frame(sb, bg=BG_PANEL)
        bank_scroll.pack(fill="x", padx=16, pady=(6, 0))
        for b in banks:
            row = tk.Frame(bank_scroll, bg=BG_PANEL)
            row.pack(fill="x", pady=1)
            tk.Label(row, text="●", fg=TEAL, bg=BG_PANEL, font=(FONT_MAIN, 8)).pack(side="left")
            tk.Label(row, text=b, fg=TEXT_DIM, bg=BG_PANEL, font=(FONT_MAIN, 10)).pack(side="left", padx=4)

        _sep(sb, color="#1e3a52").pack(fill="x", padx=16, pady=12)

        # Algorithms badge
        _label(sb, "Detection Algorithms", size=11, weight="bold", color=MUTED).pack(anchor="w", padx=16)
        algos = ["① ELA Analysis", "② Noise Fingerprint", "③ Edge Density", "④ EXIF Inspection", "⑤ Colour Heuristics"]
        for a in algos:
            tk.Label(sb, text=a, fg=TEXT_DIM, bg=BG_PANEL, font=(FONT_MAIN, 10), anchor="w").pack(fill="x", padx=20, pady=1)

        return sb

    def _build_upload_zone(self, parent):
        outer = tk.Frame(parent, bg=BG_PANEL, bd=0)
        outer.pack(fill="x")

        # Dashed-border canvas
        self._drop_canvas = tk.Canvas(
            outer, bg=BG_CARD, highlightthickness=2,
            highlightbackground=TEAL_DARK, height=180, cursor="hand2",
        )
        self._drop_canvas.pack(fill="x", padx=0, pady=0)
        self._drop_canvas.bind("<Button-1>", lambda _: self._browse())
        self._drop_canvas.bind("<Enter>", lambda _: self._drop_canvas.configure(highlightbackground=TEAL))
        self._drop_canvas.bind("<Leave>", lambda _: self._drop_canvas.configure(highlightbackground=TEAL_DARK))
        self._drop_canvas.bind("<Configure>", self._draw_drop_zone)

        # Button row
        btn_row = tk.Frame(outer, bg=BG_PANEL)
        btn_row.pack(fill="x", pady=(10, 0))

        AnimatedButton(btn_row, text="📂  Browse Image", command=self._browse, width=170).pack(side="left")

        self._analyse_btn = AnimatedButton(
            btn_row, text="🔍  Analyse Receipt",
            command=self._start_analysis, width=200,
            fg_color=AMBER, hover_color="#d4901e", text_color="#000000",
            state="disabled",
        )
        self._analyse_btn.pack(side="left", padx=12)

        self._clear_btn = AnimatedButton(
            btn_row, text="✕  Clear",
            command=self._clear, width=100,
            fg_color=BG_HOVER, hover_color=BG_CARD,
            text_color=TEXT_DIM,
        )
        self._clear_btn.pack(side="left")

        _label(btn_row, "", textvariable=self._status_var, size=11, color=TEXT_DIM).pack(side="right", padx=6)

        return outer

    def _draw_drop_zone(self, _=None):
        c = self._drop_canvas
        c.delete("all")
        w, h = c.winfo_width() or 700, c.winfo_height() or 180

        if self._image_path and self._thumb_image:
            # Show thumbnail
            c.create_image(w // 2, h // 2, anchor="center", image=self._thumb_image)
            c.create_text(w // 2, h - 16, text=Path(self._image_path).name,
                          fill=TEAL, font=(FONT_MAIN, 10))
        else:
            # Dashed border
            dash = (6, 4)
            c.create_rectangle(10, 10, w - 10, h - 10,
                                outline=TEAL_DARK, dash=dash, width=2)
            c.create_text(w // 2, h // 2 - 18, text="⬆",
                          fill=TEAL, font=(FONT_MAIN, 30))
            c.create_text(w // 2, h // 2 + 18,
                          text="Click or drag & drop a receipt screenshot here",
                          fill=TEXT_DIM, font=(FONT_MAIN, 12))
            c.create_text(w // 2, h // 2 + 38,
                          text="PNG · JPG · JPEG · BMP · WEBP · TIFF",
                          fill=MUTED, font=(FONT_MAIN, 10))

    def _build_results(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)

        # Verdict card (hidden until result)
        self._verdict_card = tk.Frame(frame, bg=BG_CARD, bd=0)
        self._verdict_label = tk.Label(
            self._verdict_card, text="", bg=BG_CARD,
            font=(FONT_MAIN, 18, "bold"), fg=TEXT_MAIN, pady=10,
        )
        self._verdict_label.pack(pady=(12, 4))
        self._confidence_label = tk.Label(
            self._verdict_card, text="", bg=BG_CARD,
            font=(FONT_MAIN, 11), fg=TEXT_DIM,
        )
        self._confidence_label.pack(pady=(0, 8))

        # Scrollable detail area
        self._detail_scroll = ctk.CTkScrollableFrame(
            frame, fg_color=BG_DARK, scrollbar_button_color=BG_HOVER,
        )
        self._detail_scroll.pack(fill="both", expand=True, pady=(10, 0))

        # Spinner label
        self._spinner_label = _label(frame, "", size=13, color=TEAL)

        return frame

    # ── Interactions ──────────────────────────────────────────────────────────

    def _toggle_key_vis(self):
        self._key_entry.configure(show="" if self._show_key_var.get() else "*")

    def _bind_drop(self):
        """Enable native tkinterdnd2 drag-and-drop if available, else silent fallback."""
        try:
            import tkinterdnd2  # type: ignore
            self.drop_target_register(tkinterdnd2.DND_FILES)  # type: ignore
            self.dnd_bind("<<Drop>>", self._on_drop)          # type: ignore
        except Exception:
            pass

    def _on_drop(self, event):
        raw = event.data.strip()
        path = raw.strip("{}").split("} {")[0]
        self._load_file(path)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select Receipt Screenshot",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.tif"), ("All files", "*.*")],
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        self._image_path = path
        self._thumb_image = None
        try:
            img = Image.open(path)
            img.thumbnail((640, 150), Image.LANCZOS)
            self._thumb_image = ImageTk.PhotoImage(img)
        except Exception:
            pass
        self._draw_drop_zone()
        self._analyse_btn.configure(state="normal")
        self._status_var.set(f"Loaded: {Path(path).name}")
        self._clear_details()

    def _clear(self):
        self._image_path = None
        self._thumb_image = None
        self._draw_drop_zone()
        self._analyse_btn.configure(state="disabled")
        self._status_var.set("Upload a receipt screenshot to begin.")
        self._clear_details()
        self._verdict_card.pack_forget()

    def _clear_details(self):
        for w in self._detail_scroll.winfo_children():
            w.destroy()

    # ── Analysis ──────────────────────────────────────────────────────────────

    def _start_analysis(self):
        if self._analysing or not self._image_path:
            return
        self._analysing = True
        self._analyse_btn.configure(state="disabled", text="Analysing…")
        self._status_var.set("Running detection engine…")
        self._clear_details()
        self._verdict_card.pack_forget()
        self._spinner_label.configure(text="⏳ Analysing — please wait…")
        self._spinner_label.pack(pady=10)
        threading.Thread(target=self._run_engine, daemon=True).start()

    def _run_engine(self):
        try:
            from engine import analyse, ImageError
            api_key = self._api_key_var.get().strip()
            report = analyse(self._image_path, api_key)
            self.after(0, self._show_results, report, None)
        except Exception as exc:
            self.after(0, self._show_results, None, str(exc))

    # ── Results rendering ─────────────────────────────────────────────────────

    def _show_results(self, report, error: Optional[str]):
        self._spinner_label.pack_forget()
        self._analysing = False
        self._analyse_btn.configure(state="normal", text="🔍  Analyse Receipt")

        if error:
            self._status_var.set("Error during analysis.")
            self._add_section("❌ Error", [(error, RED)])
            return

        self._status_var.set(f"Analysis complete — Platform: {report.platform}")

        # ── Verdict card ──
        vv = report.final_verdict
        vv_lower = vv.lower()
        if "fake" in vv_lower:
            card_col, verd_col = "#2a1010", RED
        elif "authentic" in vv_lower and "suspicious" not in vv_lower:
            card_col, verd_col = "#0d2218", GREEN
        else:
            card_col, verd_col = "#1f1a08", AMBER

        self._verdict_card.configure(bg=card_col)
        self._verdict_label.configure(text=vv, bg=card_col, fg=verd_col)
        self._confidence_label.configure(
            text=f"Confidence: {report.confidence}%   |   Platform: {report.platform}   |   "
                 f"AI Layer: {'✅ Used' if report.internet_used else '⬜ Offline'}",
            bg=card_col,
        )
        self._verdict_card.pack(fill="x", pady=(0, 6))

        # ── OCR fields ──
        o = report.ocr
        ocr_rows = [
            ("Amount",         o.amount      or "—"),
            ("Date",           o.date        or "—"),
            ("Time",           o.time_val    or "—"),
            ("Transaction ID", o.txn_id      or "—"),
            ("IBAN",           o.iban        or "—"),
            ("Confirmation",   o.confirmation or "—"),
            ("Missing Fields", ", ".join(o.missing_fields) if o.missing_fields else "None"),
        ]
        self._add_table("📋 OCR Extracted Fields", ocr_rows)

        # ── Forensics ──
        fs = report.forensics
        frows = [(n, None) for n in fs.notes]
        self._add_section(
            f"🔬 Local Forensic Analysis   [Suspicion Score: {fs.score}/100]",
            frows,
            score=fs.score,
        )

        # ── Visual AI ──
        vis = report.visual
        if vis.error:
            self._add_section("🤖 Gemini AI Layer", [(vis.error, MUTED)])
        else:
            vrows = [(f, None) for f in vis.findings]
            if vis.summary:
                vrows.append((f"Summary: {vis.summary}", TEXT_DIM))
            self._add_section(f"🤖 Gemini AI Layer   [Verdict: {vis.verdict}]", vrows)

    def _add_table(self, title: str, rows: list[tuple[str, str]]):
        card = tk.Frame(self._detail_scroll, bg=BG_CARD, bd=0)
        card.pack(fill="x", pady=(0, 10))

        tk.Label(card, text=title, bg=BG_CARD, fg=TEAL,
                 font=(FONT_MAIN, 12, "bold"), anchor="w", pady=6, padx=12).pack(fill="x")
        _sep(card, color=BG_HOVER).pack(fill="x", padx=10)

        grid = tk.Frame(card, bg=BG_CARD)
        grid.pack(fill="x", padx=12, pady=8)
        for i, (k, v) in enumerate(rows):
            tk.Label(grid, text=k, bg=BG_CARD, fg=TEXT_DIM,
                     font=(FONT_MAIN, 11), anchor="w", width=18).grid(row=i, column=0, sticky="w", pady=2)
            col = GREEN if v and v != "—" and v != "None" else (RED if v == "—" else TEXT_MAIN)
            tk.Label(grid, text=v, bg=BG_CARD, fg=col,
                     font=(FONT_MAIN, 11, "bold"), anchor="w").grid(row=i, column=1, sticky="w", padx=8)

    def _add_section(self, title: str, items: list[tuple[str, Optional[str]]], score: int = -1):
        card = tk.Frame(self._detail_scroll, bg=BG_CARD, bd=0)
        card.pack(fill="x", pady=(0, 10))

        # Title bar with optional score bar
        title_row = tk.Frame(card, bg=BG_CARD)
        title_row.pack(fill="x")
        tk.Label(title_row, text=title, bg=BG_CARD, fg=TEAL,
                 font=(FONT_MAIN, 12, "bold"), anchor="w", pady=6, padx=12).pack(side="left")

        if score >= 0:
            bar_col = GREEN if score < 35 else (AMBER if score < 65 else RED)
            bar_frame = tk.Frame(title_row, bg=BG_CARD)
            bar_frame.pack(side="right", padx=12, pady=6)
            tk.Canvas(bar_frame, width=120, height=10, bg=BG_HOVER,
                      highlightthickness=0).pack(side="left")
            fill_w = int(120 * score / 100)
            bar_c = tk.Canvas(bar_frame, width=120, height=10, bg=BG_HOVER,
                              highlightthickness=0)
            bar_c.pack(side="left")
            bar_c.create_rectangle(0, 0, fill_w, 10, fill=bar_col, outline="")

        _sep(card, color=BG_HOVER).pack(fill="x", padx=10)

        content = tk.Frame(card, bg=BG_CARD)
        content.pack(fill="x", padx=12, pady=8)

        for text, col in items:
            c = col or TEXT_DIM
            tk.Label(content, text=f"• {text}", bg=BG_CARD, fg=c,
                     font=(FONT_MAIN, 10), anchor="w", wraplength=680,
                     justify="left").pack(fill="x", pady=1)

        if not items:
            tk.Label(content, text="No findings.", bg=BG_CARD, fg=MUTED,
                     font=(FONT_MAIN, 10)).pack(anchor="w")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    app = TruePayApp()
    print("=" * 48)
    print("  TruePay - GUI started successfully [OK]")
    print("  Platform: All 16 Pakistani Banks")
    print("  Forensics: ELA, Noise, Edge, EXIF, Heuristics")
    print("=" * 48)
    app.mainloop()


if __name__ == "__main__":
    main()
