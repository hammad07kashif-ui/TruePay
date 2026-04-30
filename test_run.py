"""
test_run.py - TruePay automated test against Real.jpeg and Fake.png
"""
import os, sys, io

# Force UTF-8 output so Greek/Unicode chars in notes don't crash on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(__file__))

from engine import analyse

SEP = "=" * 54

def test_image(fname):
    path = os.path.join(os.path.dirname(__file__), fname)
    print(f"\n[TEST] {fname}")
    print("-" * 54)
    try:
        r = analyse(path, api_key="")
        o = r.ocr
        f = r.forensics
        print(f"  Platform        : {r.platform}")
        print(f"  Amount          : {o.amount or '[not found]'}")
        print(f"  Date            : {o.date or '[not found]'}")
        print(f"  Time            : {o.time_val or '[not found]'}")
        print(f"  Transaction ID  : {o.txn_id or '[not found]'}")
        print(f"  IBAN            : {o.iban or '[not found]'}")
        print(f"  Confirmation    : {o.confirmation or '[not found]'}")
        print(f"  Missing Fields  : {', '.join(o.missing_fields) if o.missing_fields else 'None'}")
        print()
        print(f"  Suspicion Score : {f.score}/100  {'(low = good)' if f.score < 35 else '(SUSPICIOUS)' if f.score < 65 else '(HIGH - FAKE)'}")
        print(f"    - ELA          : {f.ela_score} pts")
        print(f"    - Noise        : {f.noise_score} pts")
        print(f"    - Edge Density : {f.edge_score} pts")
        print(f"    - EXIF         : {f.exif_score} pts")
        print(f"    - Heuristics   : {f.heuristic_score} pts")
        print(f"    - Bank Profile : {f.profile_score} pts")
        print()
        print(f"  Forensic Notes:")
        for note in f.notes:
            print(f"    * {note}")
        print()
        if r.visual.error:
            print(f"  AI Layer        : Skipped - {r.visual.error}")
        else:
            print(f"  AI Verdict      : {r.visual.verdict}")
        print()
        print(f"  >> FINAL VERDICT  : {r.final_verdict}")
        print(f"  >> CONFIDENCE     : {r.confidence}%")
        print(f"  >> INTERNET USED  : {r.internet_used}")
    except Exception as e:
        import traceback
        print(f"  ERROR: {e}")
        traceback.print_exc()
    print("-" * 54)


if __name__ == "__main__":
    print(SEP)
    print("  TRUEPAY v2.0 -- AUTOMATED TEST RUN")
    print("  Images: Real.jpeg + Fake.png (offline mode)")
    print(SEP)

    test_image("Real.jpeg")
    test_image("Fake.png")

    print()
    print(SEP)
    print("  Test complete.")
    print(SEP)
