"""List Gemini models that support embeddings for the configured API key."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import API_KEYS, GOOGLE_API_KEY, EMBEDDING_MODEL

try:
    import google.generativeai as genai
except ImportError:
    print("google-generativeai not installed; trying REST...")
    genai = None

key = GOOGLE_API_KEY or (API_KEYS[0] if API_KEYS else "")
if not key:
    print("No GOOGLE_API_KEY")
    sys.exit(1)

print("current EMBEDDING_MODEL:", EMBEDDING_MODEL)
print("key suffix:", key[-6:])

if genai:
    genai.configure(api_key=key)
    print("\nModels with embedContent:")
    for m in genai.list_models():
        methods = getattr(m, "supported_generation_methods", []) or []
        if "embedContent" in methods:
            print(" ", m.name)
else:
    import urllib.request
    import json
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    print("\nModels with embedContent:")
    for m in data.get("models", []):
        methods = m.get("supportedGenerationMethods", [])
        if "embedContent" in methods:
            print(" ", m.get("name"))
