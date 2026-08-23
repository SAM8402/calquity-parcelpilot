"""One-time setup script to ingest all data into DuckDB and ChromaDB."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shutil import copy2
from app.data.ingest_excel import ingest_excel_to_db
from app.config import GOOGLE_API_KEY, PDF_DIR, EXCEL_DIR, BASE_DIR


def sync_candidate_pack():
    """Copy official assessment files into data/pdfs and data/excel if present."""
    pack = BASE_DIR / "AI Agent Assessment - Candidate Pack"
    if not pack.exists():
        return False
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    EXCEL_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for pdf in pack.glob("*.pdf"):
        copy2(pdf, PDF_DIR / pdf.name)
        copied += 1
    for xlsx in pack.glob("*.xlsx"):
        copy2(xlsx, EXCEL_DIR / xlsx.name)
        copied += 1
    print(f"  Synced {copied} files from candidate pack → data/")
    return copied > 0


def setup():
    print("=" * 60)
    print("ParcelPilot AI Support Agent — Data Setup")
    print("=" * 60)

    print("\n[0/2] Syncing official candidate pack (if present)...")
    sync_candidate_pack()

    # Step 1: Excel → DuckDB
    print("\n[1/2] Ingesting Excel data into DuckDB...")
    result = ingest_excel_to_db()
    if result:
        print("  Excel data ingested successfully")
    else:
        print("  No Excel files found — place them in backend/data/excel/")

    # Step 2: PDFs → ChromaDB
    print("\n[2/2] Ingesting PDF documents into ChromaDB...")
    pdfs_exist = list(PDF_DIR.glob("*.pdf")) if PDF_DIR.exists() else []

    if not pdfs_exist:
        print(f"  No PDFs found in {PDF_DIR}")
        print("  Place assessment PDFs in backend/data/pdfs/ and re-run.")
    elif not GOOGLE_API_KEY:
        print("  GOOGLE_API_KEY not set in .env")
        print("  Set it and re-run, or run: python -m app.data.ingest_documents")
    else:
        try:
            from app.data.ingest_documents import ingest_all_documents
            ingest_all_documents()
            print("  PDF documents ingested successfully")
        except Exception as e:
            print(f"  PDF ingestion failed: {e}")
            print("  Run manually: python -m app.data.ingest_documents")

    print("\n" + "=" * 60)
    print("Setup complete! Start the server with:")
    print("  uvicorn app.main:app --reload --port 8000")
    print("=" * 60)


if __name__ == "__main__":
    setup()
