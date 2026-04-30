# TruePay v2.0 — Multi-Bank Transaction Verifier

A robust Python forensics tool and GUI application designed to detect fake, edited, or synthetically generated banking screenshots in Pakistan. TruePay uses a 6-layer offline pixel forensics engine with an optional online Gemini Vision AI fallback to verify transaction receipts from 16 major Pakistani financial institutions.

---

## Why TruePay?

Receipt fraud is a growing issue. Scammers use photo editors or automated Telegram bots to generate fake payment confirmations (like Easypaisa, JazzCash, or SadaPay screenshots). TruePay automates the detection of these fakes by inspecting the image metadata, compression signatures, and pixel data, ensuring you don't have to rely solely on your banking app's slow SMS notifications.

---

## Supported Platforms

TruePay's brand profile matching and OCR heuristics are calibrated for the following platforms:
- **Mobile Wallets:** Easypaisa, JazzCash, SadaPay, NayaPay, Upaisa
- **Traditional Banks:** HBL, UBL, Meezan Bank, MCB, Allied Bank (ABL), Bank Alfalah, Askari Bank, Standard Chartered (SCB), Faisal Bank, Bank Al Habib, Habib Metro

---

## Architecture & How It Works

TruePay relies on an **Offline-First Forensics Engine** (`engine.py`). When an image is provided, it goes through the following pipeline:

### 1. Optical Character Recognition (OCR)
Uses Tesseract to read the image text. It looks for confirmation phrases (e.g., "Successfully Sent", "Transaction Successful") and extracts the claimed banking platform. 

### 2. The 6-Algorithm Forensics Engine
TruePay analyzes the image at the pixel and metadata level without requiring an internet connection:
1. **Error Level Analysis (ELA):** Detects regions of the image that have been edited by analyzing JPEG compression residuals. Copy-pasted text stands out brightly.
2. **Noise Fingerprinting:** Real phone cameras and OS screenshots have a natural noise baseline. AI-generated flat graphics lack this noise.
3. **Edge Density (Canny):** Measures UI structural integrity.
4. **EXIF Inspection:** Detects missing device tags or the presence of Adobe Photoshop/Canva metadata.
5. **Format & Heuristics:** The strongest indicator of a fake. Real phone screenshots are natively RGB JPEGs. A receipt provided as an RGBA (transparent) PNG or with a tiny resolution (e.g., 300x600) is immediately flagged as a generated graphic.
6. **Bank Profile Matching:** Extracts the dominant colors from the image and compares them against the claimed bank's official brand colors (e.g., if a receipt claims to be Easypaisa but lacks the signature green, it is penalized).

### 3. Final Verdict Assembly
The engine weighs the scores from the 6 algorithms. If the offline score is highly suspicious (e.g., an RGBA PNG with wrong colors), it immediately returns **Likely Fake**. If it passes all local checks, it returns **Likely Authentic**.

### 4. Gemini Vision AI (Optional Fallback)
If the offline score is ambiguous (moderate suspicion), and you have provided a Gemini API key, the tool will send the image to Gemini 1.5 Flash for a deep-dive contextual analysis of the UI layout, fonts, and artifacts.

---

## Dataset Collection & Calibration

TruePay v2.0 includes a self-contained dataset collector (`collect.py`) used to calibrate the engine's thresholds.

The collector operates in two phases:
1. **Scraping Real Data:** It connects to the Google Play Store CDN and downloads genuine, high-resolution app screenshots for each supported Pakistani bank to serve as a baseline for authentic structural integrity.
2. **Generating Synthetic Fakes:** It automatically generates hundreds of synthetic forgeries (e.g., wrong aspect ratios, flat colors, ELA-injected text, RGBA PNG exports) to test the engine's detection limits.

The test suite (`test_run.py`) and calibration reporter use this dataset to ensure the forensic algorithms remain sharp against emerging spoofing techniques.

---

## Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/TruePay.git
cd TruePay
```

### 2. Install Tesseract OCR
TruePay requires Tesseract installed on your system.
- **Windows:** Download from [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki). Install to the default directory (`C:\Program Files\Tesseract-OCR\`).
- **macOS:** `brew install tesseract`
- **Linux:** `sudo apt-get install tesseract-ocr`

### 3. Install Python Dependencies
Ensure you have Python 3.10+ installed.
```bash
pip install customtkinter pytesseract Pillow opencv-python numpy scikit-image google-generativeai requests
```

### 3. API Key (Optional)
For the Gemini AI fallback to work, obtain a free API key from [Google AI Studio](https://aistudio.google.com/) and paste it into the TruePay GUI settings when you launch the app.

---

## Usage

### Launch the GUI
TruePay features a modern, dark-themed GUI built with `customtkinter`.
```bash
python app.py
```
From the GUI, you can select an image, optionally paste your API key, and view the real-time forensic analysis breakdown and final verdict.

### Run the Calibration Dataset
To build the dataset and generate synthetic fakes for engine calibration:
```bash
python collect.py
```

### Run the Test Suite
To verify the engine's core logic against a sample `Real.jpeg` and `Fake.png`:
```bash
python test_run.py
```

---

## Limitations & Ethical Disclaimer

- **Compression Loss:** Genuine receipts forwarded heavily on WhatsApp lose color saturation and edge fidelity, which can occasionally trigger false warnings. TruePay incorporates exceptions for known WhatsApp compression signatures to mitigate this.
- **Spliced Forgeries:** High-effort forgeries where a scammer edits a real, high-res phone screenshot natively on their device (preserving EXIF and format) remain difficult to detect via offline heuristics alone and rely heavily on the ELA and AI fallback.
- **Not Legal Proof:** TruePay's verdicts are probabilistic. A "Likely Fake" result indicates the presence of severe digital anomalies, but this tool is built for **fraud awareness and academic research**. Do not use it as the sole basis for legal action. Always verify transactions directly with your bank.
