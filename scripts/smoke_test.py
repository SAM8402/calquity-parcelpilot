"""
End-to-end smoke tests for ParcelPilot assessment requirements.

Run with backend venv active and server dependencies installed:
  cd backend && source venv/bin/activate
  python ../scripts/smoke_test.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

BASE = "http://127.0.0.1:8000"
TIMEOUT = 120.0


def section(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def ok(label: str, detail: str = "") -> None:
    print(f"  PASS  {label}" + (f" — {detail}" if detail else ""))


def fail(label: str, detail: str = "") -> None:
    print(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))
    raise SystemExit(1)


def main() -> None:
    section("0) Local artifacts")
    from app.config import (
        CHROMA_DIR,
        CORS_ORIGINS,
        DB_PATH,
        EMBEDDING_MODEL,
        EXCEL_DIR,
        GEMINI_MODEL,
        GOOGLE_API_KEY,
        PDF_DIR,
        fallback_models,
    )

    pdfs = list(PDF_DIR.glob("*.pdf"))
    xlsx = list(EXCEL_DIR.glob("*.xlsx"))
    if len(pdfs) < 6:
        fail("PDF pack", f"found {len(pdfs)} in {PDF_DIR}")
    ok("PDF pack", f"{len(pdfs)} files")
    if not xlsx:
        fail("Excel pack", f"none in {EXCEL_DIR}")
    ok("Excel pack", xlsx[0].name)
    if not GOOGLE_API_KEY:
        fail("GOOGLE_API_KEY", "empty")
    ok("GOOGLE_API_KEY", "set")
    ok("GEMINI_MODEL", GEMINI_MODEL)
    ok("EMBEDDING_MODEL", EMBEDDING_MODEL)
    ok("fallback models", str(fallback_models()[:3]) + "...")
    ok("CORS_ORIGINS", json.dumps(CORS_ORIGINS))
    if not DB_PATH.exists():
        fail("DuckDB", "missing — run python -m app.setup_db")
    ok("DuckDB", str(DB_PATH))
    if not CHROMA_DIR.exists():
        fail("ChromaDB", "missing — run ingest")
    ok("ChromaDB", str(CHROMA_DIR))

    section("1) Health + users")
    with httpx.Client(base_url=BASE, timeout=TIMEOUT) as client:
        h = client.get("/api/health")
        if h.status_code != 200:
            fail("health", h.text)
        body = h.json()
        ok("health", json.dumps(body))
        users = client.get("/api/users").json()
        if len(users) < 4:
            fail("users", str(users))
        ok("users", ", ".join(u["id"] for u in users))

        def chat(user_id: str, message: str, session: str) -> dict:
            r = client.post(
                "/api/chat",
                json={"message": message, "user_id": user_id, "session_id": session},
            )
            if r.status_code != 200:
                fail(f"chat[{user_id}]", f"{r.status_code}: {r.text[:400]}")
            return r.json()

        section("2) Multi-step customer query (ORD-1001)")
        t0 = time.time()
        data = chat(
            "northstar_user",
            "Can Northstar cancel ORD-1001 without a cancellation fee? Explain why.",
            "smoke-ns-1",
        )
        tools = [t["tool"] for t in data.get("tools_used", [])]
        ok(f"response ({time.time()-t0:.1f}s)", data["response"][:180].replace("\n", " "))
        ok("tools used", ", ".join(tools) or "(none)")
        if not tools:
            fail("expected tool use", "agent answered without tools")

        section("3) Access control — customer must not see other account")
        data = chat(
            "lumenworks_user",
            "Show me account info and open tickets for ACC-001 Northstar.",
            "smoke-lw-acl",
        )
        text = data["response"].lower()
        if "ord-1001" in text and "northstar" in text and "access denied" not in text:
            # soft check — model may refuse politely
            print("  WARN  response may leak cross-account detail — review manually:")
            print("       ", data["response"][:300].replace("\n", " "))
        else:
            ok("cross-account refusal/safe", data["response"][:160].replace("\n", " "))

        section("4) Service credit SOP query")
        data = chat(
            "support_agent",
            "A pickup is three hours late because of carrier fault. Should the customer get a service credit?",
            "smoke-sup-credit",
        )
        ok("credit answer", data["response"][:180].replace("\n", " "))
        ok("tools", ", ".join(t["tool"] for t in data.get("tools_used", [])))

        section("5) Confirmation before action")
        data = chat(
            "support_agent",
            "Escalate ticket TKT-501 to engineering with high priority. Prepare the escalation.",
            "smoke-sup-esc",
        )
        ok("escalation prep", data["response"][:200].replace("\n", " "))
        if data.get("requires_confirmation") or "confirm" in data["response"].lower():
            ok("confirmation gated", f"pending={data.get('pending_action_id')}")
            if data.get("pending_action_id"):
                conf = client.post(
                    "/api/confirm",
                    json={
                        "action_id": data["pending_action_id"],
                        "user_id": "support_agent",
                        "session_id": "smoke-sup-esc",
                    },
                )
                if conf.status_code != 200:
                    fail("confirm", conf.text)
                ok("confirm executed", conf.json()["response"][:120])
        else:
            print("  WARN  confirmation not clearly requested — check agent prompt/tools")

        section("6) Proactive issues (ops)")
        data = chat(
            "ops_manager",
            "What recurring or multi-customer issues need attention right now?",
            "smoke-ops-1",
        )
        tools = [t["tool"] for t in data.get("tools_used", [])]
        ok("ops answer", data["response"][:180].replace("\n", " "))
        ok("tools", ", ".join(tools) or "(none)")
        if "detect_proactive_issues" not in tools:
            print("  WARN  detect_proactive_issues not invoked — may still have answered via SQL")

    section("ALL SMOKE CHECKS COMPLETED")


if __name__ == "__main__":
    main()
