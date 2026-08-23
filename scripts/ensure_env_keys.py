"""Ensure CalQuity-required non-secret keys exist in root .env."""
from pathlib import Path

env = Path(__file__).resolve().parents[1] / ".env"
text = env.read_text()
additions = []
if "EMBEDDING_MODEL=" not in text:
    additions.append("EMBEDDING_MODEL=models/text-embedding-004")
if "NEXT_PUBLIC_API_URL=" not in text:
    additions.append("NEXT_PUBLIC_API_URL=http://localhost:8000")
if additions:
    env.write_text(text.rstrip() + "\n\n# CalQuity additions\n" + "\n".join(additions) + "\n")
    print("added:", additions)
else:
    print("no changes needed")
print("has GEMINI_MODEL:", "GEMINI_MODEL=" in text)
print("has LLM_FALLBACK_CHAIN:", "LLM_FALLBACK_CHAIN=" in text)
print("has GOOGLE_API_KEY:", "GOOGLE_API_KEY=" in text)
