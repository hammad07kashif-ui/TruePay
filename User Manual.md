# TruePay — User Manual

> **Version 2.0** | Multi-Bank Pakistani Receipt Verifier | April 2026

---

## Table of Contents

1. [What is TruePay?](#1-what-is-truepay)
2. [Supported Banks & Apps](#2-supported-banks--apps)
3. [Installation Guide](#3-installation-guide)
4. [Launching the Application](#4-launching-the-application)
5. [GUI Walkthrough](#5-gui-walkthrough)
6. [Detection Algorithms (Technical)](#6-detection-algorithms-technical)
7. [How the Final Verdict Works](#7-how-the-final-verdict-works)
8. [Gemini AI Layer](#8-gemini-ai-layer)
9. [CLI Mode (`verifier.py`)](#9-cli-mode-verifierpy)
10. [Limitations & Disclaimer](#10-limitations--disclaimer)

---

## 1. What is TruePay?

TruePay is a **desktop application** for Pakistan that detects fake, edited, or AI-generated banking transaction screenshots. Receipt fraud is widespread — someone can screenshot a real payment, edit the amount in a photo editor, and send it to you. TruePay analyses the image itself (not just the text) to determine authenticity.

### Three-Layer Analysis

```
Your Screenshot
      │
      ├──► Layer 1: OCR Field Validation   (offline, instant)
      │         Extract amount, date, time, IBAN, transaction ID
      │
      ├──► Layer 2: Offline Forensics      (offline, 5 algorithms)
      │         Pixel-level mathematical analysis
      │
      └──► Layer 3: Gemini Vision AI       (online, optional)
                 Advanced visual reasoning by Google Gemini
                        │
                        ▼
               Final Verdict + Confidence Score
```

| Layer | Internet Required? | Speed |
|---|---|---|
| OCR Field Validation | No | < 3 seconds |
| Offline Forensics | No | < 1 second |
| Gemini Vision AI | Yes + API key | 5–10 seconds |

---

## 2. Supported Banks & Apps

TruePay dynamically detects **16 Pakistani banks and fintechs** by recognising their brand text in the OCR output — no hardcoded layouts:

| # | Bank / App | Detected Keywords |
|---|---|---|
| 1 | Easypaisa | easypaisa, easy paisa, telenor |
| 2 | JazzCash | jazzcash, jazz cash, mobilink |
| 3 | HBL | hbl, habib bank, hblpay |
| 4 | UBL | ubl, united bank, omni |
| 5 | Meezan Bank | meezan, meezan bank |
| 6 | SadaPay | sadapay, sada pay |
| 7 | NayaPay | nayapay, naya pay |
| 8 | Raast | raast, 1link, ibft |
| 9 | MCB | mcb, muslim commercial bank |
| 10 | Allied Bank | allied bank, abl |
| 11 | BankIslami | bankislami, bank islami |
| 12 | Zindigi | zindigi |
| 13 | NBP | nbp, national bank of pakistan |
| 14 | Standard Chartered | standard chartered, scb |
| 15 | Faysal Bank | faysal bank |
| 16 | ZTBL | ztbl, zarai taraqiati bank |

> **Note:** If no bank keyword is found, the platform shows as "Unknown Bank" — the forensic checks still run.

---

## 3. Installation Guide

### Step 1 — Install Tesseract OCR (required)

Tesseract is the OCR engine. Install it separately:

**Windows:**
1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer — keep the default path `C:\Program Files\Tesseract-OCR\`

**macOS:**
```bash
brew install tesseract
```

**Linux:**
```bash
sudo apt-get install tesseract-ocr
```

### Step 2 — Install Python packages

```bash
pip install customtkinter pytesseract opencv-python Pillow google-generativeai numpy scikit-image requests scipy
```

### Step 3 — Get a Gemini API key (optional)

1. Visit https://aistudio.google.com/
2. Click **Get API Key → Create API Key**
3. Paste the key into the TruePay sidebar when running the app

---

## 4. Launching the Application

```bash
cd "AI project/TruePay"
python app.py
```

You should see in the terminal:
```
================================================
  TruePay — GUI started successfully ✅
================================================
```

The dark-mode GUI window will open immediately.

---

## 5. GUI Walkthrough

### Left Sidebar

| Element | Purpose |
|---|---|
| **TruePay** logo | Branding |
| **Gemini API Key** field | Enter your key here (masked by default, toggle to show) |
| **Supported Banks** list | Visual reference for all 16 detected banks |
| **Detection Algorithms** list | Shows the 5 active forensic algorithms |

### Central Upload Zone

- **Click** anywhere in the dashed box to open a file browser
- **Drag and drop** a receipt image directly into the box (requires `tkinterdnd2`)
- The border glows **brighter teal** on hover
- Once loaded, a **thumbnail preview** of your image appears in the drop zone

### Control Buttons

| Button | Action |
|---|---|
| 📂 Browse Image | Open file picker dialog |
| 🔍 Analyse Receipt | Run full detection (enabled after image loaded) |
| ✕ Clear | Remove image and reset results |

### Results Panel

After analysis, three expandable sections appear:

1. **Verdict Card** — colour-coded banner (🟢 green = Authentic, 🟡 amber = Suspicious, 🔴 red = Fake) with confidence percentage and platform name.

2. **OCR Extracted Fields** — table showing what was read from the image:
   - Amount (Rs./PKR)
   - Date and Time
   - Transaction ID
   - IBAN (if present)
   - Confirmation phrase
   - Missing fields count

3. **Local Forensic Analysis** — all 5 algorithm findings with a **suspicion score bar** (green → amber → red).

4. **Gemini AI Layer** — findings and summary from Gemini Vision (if online + API key provided), or an explanation of why it was skipped.

---

## 6. Detection Algorithms (Technical)

### Algorithm 1 — Error Level Analysis (ELA)

**What it does:**
ELA detects image editing by exploiting JPEG compression mathematics. When a JPEG image is saved, each region is compressed uniformly. If a region has been edited (e.g., an amount pasted in), the edited pixels were last compressed at a *different* time than the surrounding pixels, causing a discrepancy.

**Method:**
1. Re-save the image at JPEG quality = 90%
2. Compute the absolute pixel difference between the original and re-saved version
3. Measure the mean and standard deviation of this residual map

**Scoring:**
| Condition | Score | Meaning |
|---|---|---|
| Mean residual < 0.5 | +20 pts | Near-zero → AI-generated flat graphic |
| Mean residual > 15 | +25 pts | High variance → signs of editing |
| Mean residual 8–15 | +12 pts | Moderate → minor editing possible |
| Mean residual 0.5–8 | 0 pts | Normal → consistent with real screenshot |

---

### Algorithm 2 — Noise Fingerprinting

**What it does:**
Real phone screenshots contain characteristic high-frequency noise from JPEG compression, screen anti-aliasing, and subpixel rendering. AI-generated images and vector graphics have virtually zero noise in uniform regions — they are mathematically "too clean."

**Method:**
1. Convert image to greyscale
2. Apply Gaussian blur (5×5 kernel) to remove low-frequency content
3. Compute the absolute difference between original and blurred (this is the noise map)
4. Measure mean and std of the noise map

**Scoring:**
| Noise Mean (μ) | Score | Meaning |
|---|---|---|
| < 0.8 | +22 pts | Zero noise → AI-generated |
| 0.8–2.0 | +12 pts | Very low → possibly generated |
| > 12 | +8 pts | Unusually high → heavy compression or editing |
| 2–12 | 0 pts | Natural → real device screenshot |

---

### Algorithm 3 — Edge Density Analysis (Canny)

**What it does:**
A real phone banking UI has a predictable structure: text lines, divider lines, buttons, icons. Running the Canny edge detector on a real screenshot yields a characteristic edge pixel density (~5–25% of pixels are edges). AI-generated blank receipts have very few edges; heavily JPEG-blocked images have too many.

**Method:**
1. Convert image to greyscale
2. Run OpenCV Canny edge detector (thresholds: 50, 150)
3. Compute edge density = (edge pixels) / (total pixels)

**Scoring:**
| Edge Density | Score | Meaning |
|---|---|---|
| < 2% | +18 pts | Too sparse → blank or AI-generated graphic |
| > 35% | +15 pts | Too dense → heavy noise or JPEG blocking |
| 5%–25% | 0 pts | Normal UI structure |
| Otherwise | +5 pts | Slightly off |

---

### Algorithm 4 — EXIF Metadata Inspection

**What it does:**
EXIF metadata is stored inside image files and contains information about how the image was created. Real phone screenshots contain minimal EXIF (or none). Edited images often contain tags identifying the editing software (Adobe Photoshop, GIMP, Canva, PicsArt, Lightroom).

**Method:**
1. Extract EXIF using Pillow's `_getexif()` method
2. Check for `Software`, `Make`, `Model` tags
3. For PNG files, check the `Software` and `Comment` metadata fields

**Scoring:**
| Condition | Score | Meaning |
|---|---|---|
| Editing software tag found | +15 pts | Photoshopped/edited |
| No EXIF in a JPEG | +5 pts | Stripped metadata — suspicious |
| Device Make/Model present | 0 pts | Real phone data |
| No EXIF in PNG | 0 pts | Normal for screenshots |

---

### Algorithm 5 — Colour & Format Heuristics

**What it does:**
A set of combined pixel-level checks based on well-established forensic indicators for mobile banking receipts.

**Sub-checks:**

| Check | Method | Score |
|---|---|---|
| Alpha channel (RGBA) | `img.mode == "RGBA"` | +28 pts |
| Very low resolution | Total pixels < 400,000 | +22 pts |
| Below-average resolution | Total pixels < 900,000 | +10 pts |
| Wrong aspect ratio | Height/Width outside 1.5–2.8 | +18 pts |
| Colour flatness (very low σ) | `ImageStat.stddev` < 18 | +28 pts |
| Colour flatness (moderate) | `ImageStat.stddev` < 32 | +12 pts |
| JPEG format bonus | Confirms real screenshot | −12 pts |

**Total score** from all 5 algorithms is summed (max raw ≈ 120) and normalised to 0–100.

---

## 7. How the Final Verdict Works

All three layers feed into a priority-based decision tree:

```
1. Gemini says FAKE              → 🚨 Likely Fake          (high confidence)
2. Gemini says AUTHENTIC
      forensics < 70             → ✅ Likely Authentic
      forensics ≥ 70             → ⚠️ Suspicious (disagreement)
3. Gemini says SUSPICIOUS
      forensics ≥ 50             → 🚨 Likely Fake
      forensics < 50             → ⚠️ Suspicious
4. No Gemini (offline/no key)
      forensics ≥ 65             → 🚨 Likely Fake
      forensics 40–64            → ⚠️ Suspicious (check OCR signals)
      forensics < 40 + OCR ok    → ✅ Likely Authentic
```

**Confidence Score (0–100%):** Calculated from the combination of forensic score and AI verdict agreement. Higher confidence means the verdict has stronger evidence support.

---

## 8. Gemini AI Layer

TruePay automatically checks for an internet connection (`socket` DNS test to 8.8.8.8) before attempting the Gemini API call. If offline or if no key is provided, it skips gracefully — the offline forensics still run.

**Model used:** `gemini-1.5-flash` (fast, supports image input, free tier available)

**Prompt instructs Gemini to check:**
1. Phone status bar realism (time, signal, battery icons)
2. Font rendering quality (sub-pixel vs. artificially perfect)
3. UI layout match against the detected bank's real app
4. JPEG compression artefacts presence
5. Copy-paste or compositing signs
6. Amount/date/IBAN format correctness
7. Colour scheme match against real app branding

---

## 9. CLI Mode (`verifier.py`)

The original command-line tool is preserved for users who prefer terminal output:

```bash
# Basic analysis
python verifier.py receipt.png

# With Gemini AI
python verifier.py receipt.png --key YOUR_KEY

# Dry run (synthetic test image)
python verifier.py --dry-run
```

The CLI outputs a text report and saves a `report_<filename>.txt` automatically.

---

## 10. Limitations & Disclaimer

### Technical Limitations

- **OCR accuracy** — Tesseract struggles with white text on coloured headers (e.g., Easypaisa's green banner). Some fields may show as "not found" on genuine receipts — this does not automatically trigger a Fake verdict.
- **High-quality fakes** — A professionally edited receipt at full phone resolution, saved as JPEG, with realistic noise, can potentially score low on forensics. Always use Gemini AI for high-stakes decisions.
- **Unknown banks** — If the bank keyword isn't in the table, the platform shows "Unknown Bank" but forensics still run.

### Legal Disclaimer

> TruePay is built for **fraud awareness and academic research only**.
>
> The verdicts are **probabilistic estimates**, not legal proof. A "Likely Fake" result means the image has suspicious characteristics; it does not prove fraud. A "Likely Authentic" result does not guarantee the receipt is genuine.
>
> **Always verify payments** through your official banking app or by calling your bank before making any financial decisions.
>
> The authors accept no liability for decisions made based on this tool's output.

---

*TruePay v2.0 — Built with Python, customtkinter, Tesseract OCR, OpenCV, and Google Gemini*
