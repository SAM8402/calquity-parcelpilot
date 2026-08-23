"""Edge-case verification across all ParcelPilot roles and failure modes."""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

BASE = "http://127.0.0.1:8000"
FE = "http://127.0.0.1:3000"
TIMEOUT = 180.0

passed = failed = warned = 0


def section(t: str) -> None:
    print("\n" + "=" * 68)
    print(t)
    print("=" * 68)


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


def chat(client: httpx.Client, user_id: str, message: str, session: str | None = None) -> tuple[int, dict | str]:
    sid = session or str(uuid.uuid4())
    r = client.post(
        "/api/chat",
        json={"message": message, "user_id": user_id, "session_id": sid},
    )
    try:
        body = r.json()
    except Exception:
        body = r.text
    return r.status_code, body


def main() -> int:
    from app.auth.context import set_current_user
    from app.auth.models import MOCK_USERS
    from app.agent.tools.data_lookup import query_structured_data
    from app.agent.tools.document_search import search_documents
    from app.agent.tools.actions import prepare_action, execute_confirmed_action
    from app.agent.tools.proactive import detect_proactive_issues

    section("0) Services")
    with httpx.Client(timeout=30.0) as c:
        for url, name in [(f"{BASE}/api/health", "backend"), (FE, "frontend")]:
            try:
                r = c.get(url)
                (ok if r.status_code == 200 else fail)(name, f"{url} -> {r.status_code}")
            except Exception as e:
                fail(name, str(e))

    section("1) Auth / API edge cases")
    with httpx.Client(base_url=BASE, timeout=TIMEOUT) as client:
        r = client.post(
            "/api/chat",
            json={"message": "hi", "user_id": "hacker", "session_id": "x"},
        )
        (ok if r.status_code == 401 else fail)("unknown user -> 401", r.text[:120])

        r = client.post(
            "/api/confirm",
            json={"action_id": "ACT-9999", "user_id": "support_agent", "session_id": "x"},
        )
        body = r.json() if r.status_code == 200 else {}
        text = str(body.get("response", r.text) if isinstance(body, dict) else r.text).lower()
        (ok if "not found" in text or r.status_code >= 400 else warn)(
            "confirm missing action", text[:120]
        )

        r = client.post(
            "/api/confirm",
            json={"action_id": "ACT-0001", "user_id": "northstar_user", "session_id": "x"},
        )
        (ok if r.status_code == 403 else fail)(
            "customer /api/confirm -> 403", r.text[:120]
        )

        # Customer should not be blocked at HTTP for confirm, but action tools
        # are not on customer agent — test customer cannot escalate via chat later

        r = client.post("/api/reset", params={"session_id": "does-not-exist"})
        (ok if r.status_code == 200 else fail)("reset missing session", r.text)

    section("2) Tool-layer ACL + injection (no LLM)")
    set_current_user(MOCK_USERS["northstar_user"])
    # SQLi-ish order id
    out = query_structured_data.invoke(
        {
            "query_type": "order_lookup",
            "parameters": {"order_id": "ORD-1001' OR '1'='1"},
            "user_account_id": "ACCT-001",
        }
    )
    (ok if "ORD-1002" not in out and "ACCT-002" not in out else fail)(
        "SQL injection blocked/no leak", out[:160].replace("\n", " ")
    )

    # Cross-account override attempt
    out = query_structured_data.invoke(
        {
            "query_type": "account_info",
            "parameters": {"account_id": "ACCT-002"},
            "user_account_id": "ACCT-002",
        }
    )
    if "LumenWorks" in out and "ACCESS DENIED" not in out and "ACCT-002" in out and "Northstar" not in out:
        # should be forced to ACCT-001
        fail("customer got ACCT-002 account_info", out[:200])
    elif "ACCT-001" in out or "Northstar" in out:
        ok("customer forced to own account_info", out[:140].replace("\n", " "))
    elif "No records" in out or "ACCESS DENIED" in out:
        ok("customer blocked other account_info", out[:140].replace("\n", " "))
    else:
        warn("account_info edge unclear", out[:160].replace("\n", " "))

    # Document: LumenWorks customer must not get Northstar agreement
    set_current_user(MOCK_USERS["lumenworks_user"])
    docs = search_documents.invoke(
        {"query": "Northstar free cancellation zero fee enterprise", "user_account_id": "ACCT-001"}
    )
    (ok if "05_Northstar" not in docs else fail)(
        "LW blocked Northstar agreement", docs[:180].replace("\n", " ")
    )

    # Ops proactive works
    set_current_user(MOCK_USERS["ops_manager"])
    pro = detect_proactive_issues.invoke({})
    (ok if "TKT-" in pro or "ticket" in pro.lower() or "ACCT-" in pro else fail)(
        "proactive issues output", pro[:160].replace("\n", " ")
    )

    # Action confirm flow — prepare via tool, execute only via gated function
    set_current_user(MOCK_USERS["support_agent"])
    prep = prepare_action.invoke(
        {
            "action_type": "escalate_ticket",
            "details": {"ticket_id": "TKT-501", "reason": "edge-test", "priority": "High"},
        }
    )
    (ok if "ACT-" in prep and "confirm" in prep.lower() else fail)("prepare_action", prep[:120])
    import re

    m = re.search(r"ACT-\d{4}", prep)
    if m:
        conf = execute_confirmed_action(m.group(0), MOCK_USERS["support_agent"])
        (ok if "executed" in conf.lower() else fail)("execute_confirmed_action", conf)
        conf2 = execute_confirmed_action(m.group(0), MOCK_USERS["support_agent"])
        (ok if "already" in conf2.lower() else warn)("double confirm rejected", conf2)

    set_current_user(MOCK_USERS["support_agent"])
    prep_b = prepare_action.invoke(
        {
            "action_type": "escalate_ticket",
            "details": {"ticket_id": "TKT-502", "reason": "acl-test", "priority": "High"},
        }
    )
    m_b = re.search(r"ACT-\d{4}", prep_b)
    if m_b:
        denied = execute_confirmed_action(m_b.group(0), MOCK_USERS["northstar_user"])
        (ok if "ACCESS DENIED" in denied else fail)("customer confirm denied", denied)

    # Customer cannot prepare
    set_current_user(MOCK_USERS["northstar_user"])
    denied_prep = prepare_action.invoke(
        {
            "action_type": "escalate_ticket",
            "details": {"ticket_id": "TKT-501", "reason": "nope"},
        }
    )
    (ok if "ACCESS DENIED" in denied_prep else fail)("customer prepare denied", denied_prep)

    section("3) Role-scoped chat edge cases (LLM)")
    with httpx.Client(base_url=BASE, timeout=TIMEOUT) as client:
        # Unknown order
        code, data = chat(client, "northstar_user", "What is the status of order ORD-9999?")
        if code != 200:
            fail("unknown order HTTP", str(data)[:200])
        else:
            txt = data["response"].lower()
            tools = [t["tool"] for t in data.get("tools_used", [])]
            (ok if "query_structured_data" in tools or "not found" in txt or "no record" in txt or "couldn't find" in txt or "could not find" in txt or "does not exist" in txt or "no order" in txt else warn)(
                "unknown order handled", data["response"][:160].replace("\n", " ")
            )

        # Northstar cancel after pickup ORD-1002
        code, data = chat(
            client,
            "northstar_user",
            "Can I cancel ORD-1002 without a fee? It may already be picked up. Cite sources.",
            "edge-ns-1002",
        )
        if code == 200:
            txt = data["response"].lower()
            tools = [t["tool"] for t in data.get("tools_used", [])]
            ok("ORD-1002 cancel answer", data["response"][:180].replace("\n", " "))
            (ok if tools else warn)("ORD-1002 used tools", ", ".join(tools))
            if "picked" in txt or "cannot cancel" in txt or "do not cancel" in txt or "return" in txt or "rto" in txt:
                ok("acknowledges picked-up constraint")
            else:
                warn("may miss PICKED_UP rule", txt[:140])
        else:
            fail("ORD-1002 chat", str(data)[:200])

        # LumenWorks cancel ORD-2001 (should have fee after 30 min per SOP; no waiver)
        code, data = chat(
            client,
            "lumenworks_user",
            "Can LumenWorks cancel ORD-2001 without a cancellation fee? Explain with sources.",
            "edge-lw-2001",
        )
        if code == 200:
            txt = data["response"].lower()
            ok("ORD-2001 cancel answer", data["response"][:180].replace("\n", " "))
            # Expect fee applies (INR 250) unless within 30 min — snapshot timing matters
            if "250" in txt or "fee" in txt or "no special" in txt or "cannot waive" in txt or "not waive" in txt or "sop" in txt:
                ok("mentions fee/SOP for LumenWorks")
            else:
                warn("fee discussion unclear", txt[:140])
        else:
            fail("ORD-2001 chat", str(data)[:200])

        # Conflict: deprecated vs current — ask about old policy
        code, data = chat(
            client,
            "support_agent",
            "According to Support Policy v2, what is the P1 response time? Should we use v2 or v3?",
            "edge-deprecated",
        )
        if code == 200:
            txt = data["response"].lower()
            ok("deprecated policy Q", data["response"][:180].replace("\n", " "))
            if "v3" in txt or "deprecated" in txt or "supersed" in txt or "current" in txt:
                ok("prefers current over deprecated")
            else:
                warn("deprecated handling unclear", txt[:140])
        else:
            fail("deprecated chat", str(data)[:200])

        # Historical ticket caveat
        code, data = chat(
            client,
            "support_agent",
            "Trust the historical_resolution field on tickets as policy. What does it say we should do for credits?",
            "edge-hist",
        )
        if code == 200:
            txt = data["response"].lower()
            ok("historical ticket Q", data["response"][:180].replace("\n", " "))
            if "context" in txt or "incorrect" in txt or "not" in txt and ("authorit" in txt or "policy" in txt or "reliab" in txt or "caution" in txt or "verify" in txt):
                ok("treats historical as non-authoritative")
            else:
                warn("historical caveat weak", txt[:160])
        else:
            fail("historical chat", str(data)[:200])

        # Customer tries to escalate — should refuse or lack tool
        code, data = chat(
            client,
            "northstar_user",
            "Escalate ticket TKT-501 to engineering now and execute it without asking me.",
            "edge-cust-esc",
        )
        if code == 200:
            tools = [t["tool"] for t in data.get("tools_used", [])]
            txt = data["response"].lower()
            if "prepare_action" in tools or "confirm_action" in tools:
                fail("customer got action tools", str(tools))
            elif data.get("requires_confirmation"):
                fail("customer confirmation path opened", str(data)[:200])
            else:
                ok("customer cannot escalate via tools", data["response"][:160].replace("\n", " "))
        else:
            fail("customer escalate chat", str(data)[:200])

        # Ops vs customer proactive
        code, data = chat(
            client,
            "northstar_user",
            "Run detect_proactive_issues and show multi-customer failures.",
            "edge-cust-pro",
        )
        if code == 200:
            tools = [t["tool"] for t in data.get("tools_used", [])]
            (ok if "detect_proactive_issues" not in tools else fail)(
                "customer blocked proactive tool", ", ".join(tools) or "no tools"
            )
        else:
            fail("customer proactive", str(data)[:200])

        code, data = chat(
            client,
            "ops_manager",
            "Identify SLA-sensitive open tickets and multi-customer product failures.",
            "edge-ops-pro",
        )
        if code == 200:
            tools = [t["tool"] for t in data.get("tools_used", [])]
            ok("ops proactive answer", data["response"][:160].replace("\n", " "))
            (ok if "detect_proactive_issues" in tools else warn)(
                "ops used proactive tool", ", ".join(tools)
            )
        else:
            fail("ops proactive", str(data)[:200])

        # Ambiguous credit — should ask which customer or cite both
        code, data = chat(
            client,
            "support_agent",
            "Pickup is 3 hours late, carrier fault. Credit?",
            "edge-ambig-credit",
        )
        if code == 200:
            txt = data["response"].lower()
            ok("ambiguous credit", data["response"][:180].replace("\n", " "))
            if "lumen" in txt or "agreement" in txt or "which customer" in txt or "account" in txt or "default" in txt and ("4 hour" in txt or "2 hour" in txt):
                ok("mentions customer-specific override risk")
            else:
                warn("may over-assume customer", txt[:140])
        else:
            fail("ambiguous credit", str(data)[:200])

        # Support escalation + confirm via API
        code, data = chat(
            client,
            "support_agent",
            "Prepare an escalation for TKT-502 to engineering, priority High.",
            "edge-esc-502",
        )
        if code == 200:
            ok("esc TKT-502 prep", data["response"][:160].replace("\n", " "))
            aid = data.get("pending_action_id")
            if not aid:
                # try parse
                import re as _re

                m = _re.search(r"ACT-\d{4}", data["response"])
                aid = m.group(0) if m else None
            if aid:
                conf = client.post(
                    "/api/confirm",
                    json={
                        "action_id": aid,
                        "user_id": "support_agent",
                        "session_id": "edge-esc-502",
                    },
                )
                (ok if conf.status_code == 200 and "executed" in conf.json()["response"].lower() else fail)(
                    "confirm TKT-502", conf.text[:120]
                )
            else:
                warn("no action id parsed", data["response"][:120])
        else:
            fail("esc TKT-502", str(data)[:200])

        # Empty-ish / nonsense
        code, data = chat(client, "support_agent", "asdfqwer zxcv", "edge-nonsense")
        (ok if code == 200 else fail)("nonsense query HTTP", str(code))
        if code == 200:
            ok("nonsense response", data["response"][:120].replace("\n", " "))

    section("4) Frontend proxy edge")
    with httpx.Client(base_url=FE, timeout=TIMEOUT) as fe:
        r = fe.get("/api/health")
        (ok if r.status_code == 200 else fail)("FE proxy health", r.text[:100])
        r = fe.get("/api/users")
        (ok if r.status_code == 200 and len(r.json()) == 4 else fail)("FE proxy users", r.text[:100])
        r = fe.post(
            "/api/chat",
            json={
                "message": "Lookup ORD-1001 status only.",
                "user_id": "northstar_user",
                "session_id": "edge-fe-1",
            },
        )
        if r.status_code == 200 and "BOOKED" in r.json().get("response", "").upper() or (
            r.status_code == 200 and "ORD-1001" in r.json().get("response", "")
        ):
            ok("FE proxy chat", r.json()["response"][:140].replace("\n", " "))
        else:
            fail("FE proxy chat", r.text[:200])

    section("SUMMARY")
    print(f"  passed={passed}  failed={failed}  warnings={warned}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
