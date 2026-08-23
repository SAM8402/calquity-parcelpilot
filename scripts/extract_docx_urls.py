"""Extract full hyperlinks from the assessment docx relationships."""
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
docx = ROOT / "CalQuity AI Engineer — Job Description & AI Agent Assessment.docx"

with zipfile.ZipFile(docx) as z:
    rels = z.read("word/_rels/document.xml.rels").decode("utf-8", errors="ignore")
    xml = z.read("word/document.xml").decode("utf-8", errors="ignore")

print("=== ALL Relationship Targets ===")
for m in re.finditer(r'Target="([^"]+)"', rels):
    print(m.group(1))

print("\n=== hyperlink r:id mappings in document ===")
# Find w:hyperlink elements
ns = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
root = ET.fromstring(xml)
for hl in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}hyperlink"):
    rid = hl.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    texts = [
        t.text or ""
        for t in hl.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
    ]
    print(f"rId={rid} text={' '.join(texts).strip()}")
