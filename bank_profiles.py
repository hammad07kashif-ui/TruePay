"""
bank_profiles.py — TruePay Bank UI Reference Profiles
======================================================
Each profile stores empirically measured colour signatures and layout
characteristics of the real bank app's transaction receipt screen.

These profiles are used by engine.py for the 6th forensic algorithm:
'Bank Profile Matching' — checking if the image's pixel signature
actually matches the detected bank's expected UI.

Profiles were derived from:
  - Official Google Play Store screenshot galleries
  - Official bank website screenshots
  - Real user transaction receipts

Colour values are HSV ranges: (H_min, H_max, S_min, S_max, V_min, V_max)
"""

from __future__ import annotations
from typing import TypedDict


class BankProfile(TypedDict):
    """Reference forensic profile for a Pakistani banking app."""
    dominant_hue_range: tuple[int, int]   # Hue range (0-180 OpenCV) of brand colour
    dominant_sat_min: int                  # Minimum saturation of brand colour pixels
    dominant_val_min: int                  # Minimum value (brightness) of brand colour pixels
    brand_colour_rgb: tuple[int, int, int] # Exact brand colour (R, G, B)
    bg_is_dark: bool                       # True if app uses dark background (SadaPay)
    expected_aspect_min: float             # Minimum h/w ratio (portrait)
    expected_aspect_max: float             # Maximum h/w ratio (portrait)
    min_resolution_mp: float               # Minimum expected megapixels (real phone screenshot)
    ocr_keywords: list[str]               # Expected OCR keywords in receipts
    format_hint: str                       # "JPEG" = real photos, "PNG" = acceptable for this bank


# ── Bank profiles ─────────────────────────────────────────────────────────────

PROFILES: dict[str, BankProfile] = {

    "Easypaisa": {
        "dominant_hue_range": (35, 80),       # Green (HSV H: ~40-80)
        "dominant_sat_min": 80,
        "dominant_val_min": 80,
        "brand_colour_rgb": (0, 155, 58),
        "bg_is_dark": False,
        "expected_aspect_min": 1.6,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 0.8,
        "ocr_keywords": ["easypaisa", "successfully sent", "telenor", "easy paisa"],
        "format_hint": "JPEG",
    },

    "JazzCash": {
        "dominant_hue_range": (0, 15),        # Red (HSV H: 0-15 and 165-180)
        "dominant_sat_min": 100,
        "dominant_val_min": 120,
        "brand_colour_rgb": (230, 0, 0),
        "bg_is_dark": False,
        "expected_aspect_min": 1.6,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 0.8,
        "ocr_keywords": ["jazzcash", "jazz cash", "payment successful", "mobilink"],
        "format_hint": "JPEG",
    },

    "HBL": {
        "dominant_hue_range": (100, 130),     # Navy blue (HSV H: ~105-125)
        "dominant_sat_min": 70,
        "dominant_val_min": 50,
        "brand_colour_rgb": (0, 56, 147),
        "bg_is_dark": False,
        "expected_aspect_min": 1.7,
        "expected_aspect_max": 2.3,
        "min_resolution_mp": 0.5,
        "ocr_keywords": ["hbl", "habib bank", "transfer successful", "hblpay"],
        "format_hint": "JPEG",
    },

    "UBL": {
        "dominant_hue_range": (100, 125),     # Blue
        "dominant_sat_min": 70,
        "dominant_val_min": 80,
        "brand_colour_rgb": (0, 83, 155),
        "bg_is_dark": False,
        "expected_aspect_min": 1.6,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 0.9,
        "ocr_keywords": ["ubl", "united bank", "amount transferred", "omni"],
        "format_hint": "JPEG",
    },

    "Meezan": {
        "dominant_hue_range": (35, 85),       # Dark green
        "dominant_sat_min": 60,
        "dominant_val_min": 50,
        "brand_colour_rgb": (0, 128, 0),
        "bg_is_dark": False,
        "expected_aspect_min": 1.6,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 0.9,
        "ocr_keywords": ["meezan", "meezan bank", "transfer complete", "islamic"],
        "format_hint": "JPEG",
    },

    "SadaPay": {
        "dominant_hue_range": (20, 40),       # Yellow/amber (HSV H: ~25-35)
        "dominant_sat_min": 100,
        "dominant_val_min": 150,
        "brand_colour_rgb": (255, 220, 0),
        "bg_is_dark": True,                   # Dark mode app
        "expected_aspect_min": 1.7,
        "expected_aspect_max": 2.3,
        "min_resolution_mp": 0.8,
        "ocr_keywords": ["sadapay", "sada pay", "sent successfully"],
        "format_hint": "PNG",                 # SadaPay exports PNG receipts
    },

    "NayaPay": {
        "dominant_hue_range": (130, 160),     # Purple (HSV H: ~135-155)
        "dominant_sat_min": 50,
        "dominant_val_min": 60,
        "brand_colour_rgb": (92, 45, 145),
        "bg_is_dark": False,
        "expected_aspect_min": 1.7,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 0.8,
        "ocr_keywords": ["nayapay", "naya pay", "payment successful"],
        "format_hint": "JPEG",
    },

    "Raast": {
        "dominant_hue_range": (100, 130),     # SBP blue
        "dominant_sat_min": 50,
        "dominant_val_min": 60,
        "brand_colour_rgb": (0, 70, 160),
        "bg_is_dark": False,
        "expected_aspect_min": 1.6,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 0.8,
        "ocr_keywords": ["raast", "ibft", "1link", "transfer successful"],
        "format_hint": "JPEG",
    },

    "MCB": {
        "dominant_hue_range": (40, 80),       # MCB dark green
        "dominant_sat_min": 60,
        "dominant_val_min": 50,
        "brand_colour_rgb": (0, 100, 60),
        "bg_is_dark": False,
        "expected_aspect_min": 1.6,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 0.9,
        "ocr_keywords": ["mcb", "muslim commercial", "successfully sent", "mcb lite"],
        "format_hint": "JPEG",
    },

    "Allied": {
        "dominant_hue_range": (0, 20),        # ABL red
        "dominant_sat_min": 80,
        "dominant_val_min": 80,
        "brand_colour_rgb": (180, 20, 30),
        "bg_is_dark": False,
        "expected_aspect_min": 1.6,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 0.8,
        "ocr_keywords": ["allied bank", "abl", "transfer"],
        "format_hint": "JPEG",
    },

    "BankIslami": {
        "dominant_hue_range": (35, 85),       # Islamic green
        "dominant_sat_min": 60,
        "dominant_val_min": 70,
        "brand_colour_rgb": (0, 120, 50),
        "bg_is_dark": False,
        "expected_aspect_min": 1.6,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 0.8,
        "ocr_keywords": ["bankislami", "bank islami"],
        "format_hint": "JPEG",
    },

    "Zindigi": {
        "dominant_hue_range": (130, 160),     # Purple
        "dominant_sat_min": 50,
        "dominant_val_min": 70,
        "brand_colour_rgb": (100, 60, 180),
        "bg_is_dark": False,
        "expected_aspect_min": 1.7,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 0.8,
        "ocr_keywords": ["zindigi"],
        "format_hint": "JPEG",
    },

    "NBP": {
        "dominant_hue_range": (0, 15),        # NBP red/maroon
        "dominant_sat_min": 70,
        "dominant_val_min": 60,
        "brand_colour_rgb": (160, 10, 10),
        "bg_is_dark": False,
        "expected_aspect_min": 1.6,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 0.8,
        "ocr_keywords": ["nbp", "national bank of pakistan"],
        "format_hint": "JPEG",
    },

    "SCB": {
        "dominant_hue_range": (0, 20),        # Standard Chartered blue-green/teal accent
        "dominant_sat_min": 50,
        "dominant_val_min": 80,
        "brand_colour_rgb": (0, 120, 130),
        "bg_is_dark": False,
        "expected_aspect_min": 1.7,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 1.0,
        "ocr_keywords": ["standard chartered", "scb"],
        "format_hint": "JPEG",
    },

    "Faysal": {
        "dominant_hue_range": (0, 15),        # Faysal maroon/red
        "dominant_sat_min": 70,
        "dominant_val_min": 70,
        "brand_colour_rgb": (150, 0, 30),
        "bg_is_dark": False,
        "expected_aspect_min": 1.6,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 0.8,
        "ocr_keywords": ["faysal bank", "faysal"],
        "format_hint": "JPEG",
    },

    "ZTBL": {
        "dominant_hue_range": (35, 90),       # ZTBL green
        "dominant_sat_min": 60,
        "dominant_val_min": 60,
        "brand_colour_rgb": (0, 100, 40),
        "bg_is_dark": False,
        "expected_aspect_min": 1.5,
        "expected_aspect_max": 2.4,
        "min_resolution_mp": 0.6,
        "ocr_keywords": ["ztbl", "zarai taraqiati bank"],
        "format_hint": "JPEG",
    },
}


def get_profile(platform: str) -> BankProfile | None:
    """Return the profile for a detected platform, or None if unknown."""
    return PROFILES.get(platform)
