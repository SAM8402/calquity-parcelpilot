"""Comprehensive ParcelPilot verification suite."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import duckdb
import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

BASE = "http://127.0.0.1:8000"
TIMEOUT = 180.0
passed = 0
failed = 0
warned = 0


def section(title: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def ok(label: str, detail: str = "") -> None:
    global passed
    passed += 1
    print(f"  PASS  {label}" + (f" — {detail}" if detail else ""))


def warn(label: str, detail: str = "") -> None:
    global warned
    warned += 1
    print(f"  WARN  {label}" + (f" — {detail}" if detail else ""))


def fail(label: str, detail: str = "") -> None:
    global failed
    failed += 1
    print(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))


def main() -> int:
    from app.auth.context import set_current_user
    from app.auth.models import MOCK_USERS
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
    from app.data.vector_store import search_with_metadata
    from app.agent.tools.data_lookup import query_structured_data
    from app.agent.tools.document_search import search_documents

    section("A) Artifacts & config")
    pdfs = list(PDF_DIR.glob("*.pdf"))
    xlsx = list(EXCEL_DIR.glob("*.xlsx"))
    (ok if len(pdfs) >= 6 else fail)("PDF pack", f"{len(pdfs)} files")
    (ok if xlsx else fail)("Excel pack", xlsx[0].name if xlsx else "missing")
    (ok if GOOGLE_API_KEY else fail)("GOOGLE_API_KEY", "set" if GOOGLE_API_KEY else "empty")
    ok("GEMINI_MODEL", GEMINI_MODEL)
    ok("EMBEDDING_MODEL", EMBEDDING_MODEL)
    ok("fallback models", str(fallback_models()[:3]))
    ok("CORS", json.dumps(CORS_ORIGINS))
    (ok if DB_PATH.exists() else fail)("DuckDB", str(DB_PATH))
    (ok if CHROMA_DIR.exists() else fail)("ChromaDB", str(CHROMA_DIR))

    section("B) DuckDB schema & sample IDs")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        for t in ("accounts", "orders", "tickets"):
            (ok if t in tables else fail)(f"table {t}", "present" if t in tables else "missing")
        ord_row = con.execute(
            "SELECT order_id, account_id, status FROM orders WHERE order_id='ORD-1001'"
        ).fetchone()
        if ord_row and ord_row[1] == "ACCT-001":
            ok("ORD-1001", f"{ord_row}")
        else:
            fail("ORD-1001", str(ord_row))
        acct = con.execute(
            "SELECT account_id, account_name FROM accounts WHERE account_id='ACCT-001'"
        ).fetchone()
        (ok if acct else fail)("ACCT-001", str(acct))
        tkt = con.execute("SELECT count(*) FROM tickets").fetchone()[0]
        ok("ticket count", str(tkt))
    finally:
        con.close()

    section("C) Tool-layer access control (no LLM)")
    # Northstar customer must only see own account
    set_current_user(MOCK_USERS["northstar_user"])
    ns_orders = query_structured_data.invoke(
        {
            "query_type": "order_lookup",
            "parameters": {"order_id": "ORD-2001"},
            "user_account_id": "ACCT-002",  # malicious override attempt
        }
    )
    if "No records found" in ns_orders or "ACCESS DENIED" in ns_orders:
        ok("customer cannot read other-account order", ns_orders[:120].replace("\n", " "))
    else:
        fail("customer leaked other-account order", ns_orders[:200])

    ns_own = query_structured_data.invoke(
        {
            "query_type": "order_lookup",
            "parameters": {"order_id": "ORD-1001"},
            "user_account_id": "ACCT-001",
        }
    )
    (ok if "ORD-1001" in ns_own else fail)("customer can read own order", ns_own[:120].replace("\n", " "))

    # Support can see all
    set_current_user(MOCK_USERS["support_agent"])
    all_tickets = query_structured_data.invoke(
        {"query_type": "ticket_search", "parameters": {"status": "open"}, "user_account_id": None}
    )
    (ok if "TKT-" in all_tickets else fail)("support ticket search", all_tickets[:120].replace("\n", " "))

    section("D) Vector retrieval")
    try:
        hits = search_with_metadata("Northstar cancellation fee waiver", k=3)
        if hits:
            sources = [d.metadata.get("source_file") for d, _ in hits]
            ok("vector search hits", str(sources))
            if any("Northstar" in (s or "") for s in sources):
                ok("Northstar agreement retrieved")
            else:
                warn("Northstar agreement not top hit", str(sources))
        else:
            fail("vector search", "no hits")
    except Exception as e:
        fail("vector search", str(e))

    set_current_user(MOCK_USERS["lumenworks_user"])
    docs = search_documents.invoke(
        {"query": "Northstar free cancellation enterprise terms", "user_account_id": "ACCT-001"}
    )
    if "05_Northstar" in docs and "LumenWorks" not in docs:
        # filtered — may still mention Northstar in query text only
        warn("doc filter check", "review: " + docs[:160].replace("\n", " "))
    if "05_Northstar" in docs:
        fail("customer retrieved other agreement", docs[:200].replace("\n", " "))
    else:
        ok("customer blocked other agreement", docs[:160].replace("\n", " "))

    section("E) HTTP API health + chat flows")
    with httpx.Client(base_url=BASE, timeout=TIMEOUT) as client:
        h = client.get("/api/health")
        (ok if h.status_code == 200 and h.json().get("db_available") else fail)(
            "GET /api/health", h.text[:200]
        )
        users = client.get("/api/users")
        (ok if users.status_code == 200 and len(users.json()) >= 4 else fail)(
            "GET /api/users", str(len(users.json()) if users.status_code == 200 else users.text)
        )

        def chat(user_id: str, message: str, session: str) -> dict | None:
            r = client.post(
                "/api/chat",
                json={"message": message, "user_id": user_id, "session_id": session},
            )
            if r.status_code != 200:
                fail(f"chat[{user_id}]", f"{r.status_code}: {r.text[:350]}")
                return None
            return r.json()

        t0 = time.time()
        data = chat(
            "northstar_user",
            "Can Northstar cancel ORD-1001 without a cancellation fee? Explain why with sources.",
            "full-ns-1",
        )
        if data:
            tools = [t["tool"] for t in data.get("tools_used", [])]
            text = data["response"].lower()
            ok(f"ORD-1001 answer ({time.time()-t0:.1f}s)", data["response"][:180].replace("\n", " "))
            if "query_structured_data" in tools and "search_documents" in tools:
                ok("multi-step tools", ", ".join(tools))
            else:
                warn("expected both data+docs tools", ", ".join(tools) or "none")
            if "fee" in text or "cancel" in text:
                ok("answer discusses cancellation")
            else:
                warn("answer content unexpected", text[:120])

        data = chat(
            "lumenworks_user",
            "Show me all open tickets and orders for ACCT-001 Northstar Logistics.",
            "full-lw-acl",
        )
        if data:
            text = data["response"].lower()
            if "ord-1001" in text and ("acct-001" in text or "northstar") and "cannot" not in text and "can't" not in text and "not authorised" not in text and "not authorized" not in text and "restricted" not in text:
                fail("possible ACL leak in chat", data["response"][:250].replace("\n", " "))
            else:
                ok("ACL chat refusal", data["response"][:180].replace("\n", " "))

        data = chat(
            "support_agent",
            "A pickup is three hours late because of carrier fault. Should the customer get a service credit? Cite the SOP.",
            "full-sup-credit",
        )
        if data:
            tools = [t["tool"] for t in data.get("tools_used", [])]
            ok("credit query", data["response"][:180].replace("\n", " "))
            (ok if "search_documents" in tools else warn)("used document search", ", ".join(tools))

        data = chat(
            "support_agent",
            "Escalate ticket TKT-501 to engineering with high priority. Prepare the escalation for confirmation.",
            "full-sup-esc",
        )
        if data:
            ok("escalation prep", data["response"][:180].replace("\n", " "))
            if data.get("requires_confirmation") or "confirm" in data["response"].lower():
                ok("confirmation required", f"pending={data.get('pending_action_id')}")
                aid = data.get("pending_action_id")
                if aid:
                    conf = client.post(
                        "/api/confirm",
                        json={
                            "action_id": aid,
                            "user_id": "support_agent",
                            "session_id": "full-sup-esc",
                        },
                    )
                    if conf.status_code == 200 and "executed" in conf.json()["response"].lower():
                        ok("confirm executed", conf.json()["response"][:120])
                    else:
                        fail("confirm", conf.text[:200])
            else:
                fail("confirmation missing", data["response"][:200])

        data = chat(
            "ops_manager",
            "What recurring or multi-customer issues need attention right now?",
            "full-ops-1",
        )
        if data:
            tools = [t["tool"] for t in data.get("tools_used", [])]
            ok("ops proactive", data["response"][:180].replace("\n", " "))
            (ok if "detect_proactive_issues" in tools else warn)(
                "detect_proactive_issues used", ", ".join(tools) or "none"
            )

        # session reset
        reset = client.post("/api/reset", params={"session_id": "full-ns-1"})
        (ok if reset.status_code == 200 else fail)("session reset", reset.text)

    section("SUMMARY")
    print(f"  passed={passed}  failed={failed}  warnings={warned}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
