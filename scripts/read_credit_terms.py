from pathlib import Path
from pypdf import PdfReader

pack = Path(__file__).resolve().parents[1] / "backend" / "AI Agent Assessment - Candidate Pack"
for name in [
    "03_Cancellation_and_Service_Credit_SOP_v4.pdf",
    "06_LumenWorks_Service_Agreement.pdf",
    "01_Support_Policy_v3_CURRENT.pdf",
]:
    print("=" * 70, name)
    text = "\n".join((p.extract_text() or "") for p in PdfReader(pack / name).pages)
    for line in text.splitlines():
        low = line.lower()
        if any(
            k in low
            for k in (
                "credit",
                "late",
                "delay",
                "pickup",
                "hour",
                "carrier",
                "fault",
                "threshold",
                "window",
            )
        ):
            print(line)
    print("\n--- FULL ---\n")
    print(text)
    print()
