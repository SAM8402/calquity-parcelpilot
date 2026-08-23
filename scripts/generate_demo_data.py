"""
Generate a local ParcelPilot assessment-style data pack for development/testing.

Prefer the official Google Drive candidate pack when available:
https://drive.google.com/drive/folders/1iPwLSAOjh1qBzVj6ywWP5iBhTpLDR3C-

This synthetic pack mirrors the expected filenames, authority tiers, and
example IDs (ORD-1001, ACC-001/002) so the agent can be exercised end-to-end.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "backend" / "data" / "pdfs"
EXCEL_DIR = ROOT / "backend" / "data" / "excel"

SNAPSHOT = datetime(2025, 6, 15, 12, 0, 0)


DOCS: dict[str, list[str]] = {
    "01_Support_Policy_v3_CURRENT.pdf": [
        "ParcelPilot Support Policy v3 — CURRENT",
        "Effective date: 2025-01-01. This policy supersedes v2.",
        "SLA: Critical tickets — response within 1 hour; High — 4 hours; Medium — 1 business day.",
        "Cancellations: Standard accounts may cancel up to 2 hours before pickup with a 10% fee.",
        "Enterprise agreements may override cancellation fees — always check the customer agreement.",
        "Service credits for carrier fault delays: 15% of shipping fee when delay exceeds 2 hours.",
        "Escalations to engineering require a ticket ID and clear reproduction steps.",
    ],
    "02_Support_Policy_v2_DEPRECATED.pdf": [
        "ParcelPilot Support Policy v2 — DEPRECATED",
        "Do not use for current decisions. Kept for historical context only.",
        "Old rule: cancellations within 4 hours of pickup always incur a 25% fee.",
        "Old SLA: Critical response within 4 hours (outdated).",
        "This document is superseded by Support Policy v3.",
    ],
    "03_Cancellation_and_Service_Credit_SOP_v4.pdf": [
        "Cancellation and Service Credit SOP v4",
        "Step 1: Identify order status and pickup window.",
        "Step 2: Check customer agreement for fee waivers.",
        "Step 3: If carrier fault delay > 2 hours, calculate credit = 15% of shipping_fee.",
        "Step 4: If delay > 6 hours due to carrier fault, credit = 50% of shipping_fee.",
        "Pickup late by carrier: eligible for service credit per SOP; document fault evidence.",
        "Fee waiver: only when agreement grants free cancellation or ops manager approves exception.",
    ],
    "04_Product_Operations_Guide_and_Known_Issues.pdf": [
        "Product Operations Guide and Known Issues",
        "Known issue KI-14: Carrier Partner X tracking lag of up to 90 minutes after pickup.",
        "Known issue KI-22: Label reprint failures for multi-parcel orders on weekends.",
        "Ops guidance: If multiple customers report the same carrier delay, open a bridge ticket.",
        "Do not promise credits for customer-caused delays (incorrect address, no-show).",
    ],
    "05_Northstar_Logistics_Enterprise_Agreement.pdf": [
        "Northstar Logistics Enterprise Agreement — Account ACC-001",
        "Customer: Northstar Logistics. Agreement overrides general ParcelPilot policy.",
        "Cancellation: Northstar may cancel any order up to pickup time with ZERO cancellation fee.",
        "Service credits: carrier-fault delays over 1 hour qualify for 25% shipping fee credit.",
        "Dedicated support SLA: Critical response within 30 minutes.",
        "ORD-1001 and other Northstar orders are covered by these enterprise terms.",
    ],
    "06_LumenWorks_Service_Agreement.pdf": [
        "LumenWorks Service Agreement — Account ACC-002",
        "Customer: LumenWorks. Agreement overrides general ParcelPilot policy for ACC-002.",
        "Cancellation: free cancellation only if requested 6+ hours before pickup; otherwise 10% fee.",
        "Service credits: standard SOP rates apply (no enhanced credit).",
        "Support SLA: Critical response within 2 hours.",
    ],
}


def write_pdf(path: Path, lines: list[str]) -> None:
    """Write a minimal single-page PDF without external PDF libraries."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Escape PDF string specials
    content_lines = []
    y = 750
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        for chunk in _wrap(safe, 85):
            content_lines.append(f"BT /F1 11 Tf 50 {y} Td ({chunk}) Tj ET")
            y -= 16
            if y < 50:
                break
        y -= 8
        if y < 50:
            break
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")
    objs: list[bytes] = []
    objs.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objs.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objs.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objs.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode()
        + stream
        + b"\nendstream\nendobj\n"
    )
    objs.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    path.write_bytes(bytes(out))


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    rows: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if len(trial) <= width:
            cur = trial
        else:
            if cur:
                rows.append(cur)
            cur = w
    if cur:
        rows.append(cur)
    return rows or [""]


def write_excel(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    readme = pd.DataFrame(
        {
            "key": ["dataset_snapshot_time", "notes"],
            "value": [
                SNAPSHOT.isoformat(),
                "Synthetic local pack for CalQuity development. Replace with official Drive pack for submission.",
            ],
        }
    )
    accounts = pd.DataFrame(
        [
            {
                "account_id": "ACC-001",
                "account_name": "Northstar Logistics",
                "tier": "Enterprise",
                "status": "Active",
            },
            {
                "account_id": "ACC-002",
                "account_name": "LumenWorks",
                "tier": "Standard",
                "status": "Active",
            },
            {
                "account_id": "ACC-003",
                "account_name": "BrightParcel Co",
                "tier": "Standard",
                "status": "Active",
            },
        ]
    )
    orders = pd.DataFrame(
        [
            {
                "order_id": "ORD-1001",
                "account_id": "ACC-001",
                "status": "Scheduled",
                "carrier": "PartnerX",
                "pickup_at": (SNAPSHOT + timedelta(hours=4)).isoformat(),
                "shipping_fee": 200.0,
                "weight_kg": 12.5,
                "origin": "Mumbai",
                "destination": "Delhi",
            },
            {
                "order_id": "ORD-1002",
                "account_id": "ACC-001",
                "status": "In Transit",
                "carrier": "PartnerY",
                "pickup_at": (SNAPSHOT - timedelta(hours=6)).isoformat(),
                "shipping_fee": 150.0,
                "weight_kg": 8.0,
                "origin": "Pune",
                "destination": "Bengaluru",
            },
            {
                "order_id": "ORD-2001",
                "account_id": "ACC-002",
                "status": "Delayed",
                "carrier": "PartnerX",
                "pickup_at": (SNAPSHOT - timedelta(hours=3)).isoformat(),
                "shipping_fee": 120.0,
                "weight_kg": 5.2,
                "origin": "Chennai",
                "destination": "Hyderabad",
            },
            {
                "order_id": "ORD-3001",
                "account_id": "ACC-003",
                "status": "Delivered",
                "carrier": "PartnerZ",
                "pickup_at": (SNAPSHOT - timedelta(days=2)).isoformat(),
                "shipping_fee": 90.0,
                "weight_kg": 3.0,
                "origin": "Ahmedabad",
                "destination": "Jaipur",
            },
        ]
    )
    tickets = pd.DataFrame(
        [
            {
                "ticket_id": "TKT-001",
                "account_id": "ACC-001",
                "order_id": "ORD-1002",
                "severity": "High",
                "status": "Open",
                "category": "Tracking Delay",
                "created_at": (SNAPSHOT - timedelta(hours=5)).isoformat(),
                "summary": "Tracking not updating for 4 hours",
                "resolution_notes": "Previous agent said credits are automatic — VERIFY; may be incorrect.",
            },
            {
                "ticket_id": "TKT-002",
                "account_id": "ACC-002",
                "order_id": "ORD-2001",
                "severity": "Critical",
                "status": "Open",
                "category": "Pickup Late",
                "created_at": (SNAPSHOT - timedelta(hours=3)).isoformat(),
                "summary": "Pickup 3 hours late — carrier fault suspected",
                "resolution_notes": "",
            },
            {
                "ticket_id": "TKT-003",
                "account_id": "ACC-003",
                "order_id": "ORD-3001",
                "severity": "Medium",
                "status": "Open",
                "category": "Tracking Delay",
                "created_at": (SNAPSHOT - timedelta(hours=2)).isoformat(),
                "summary": "Tracking lag after weekend pickup",
                "resolution_notes": "",
            },
            {
                "ticket_id": "TKT-004",
                "account_id": "ACC-001",
                "order_id": "ORD-1001",
                "severity": "Low",
                "status": "Open",
                "category": "Cancellation Inquiry",
                "created_at": (SNAPSHOT - timedelta(hours=1)).isoformat(),
                "summary": "Asking if ORD-1001 can be cancelled without fee",
                "resolution_notes": "",
            },
            {
                "ticket_id": "TKT-005",
                "account_id": "ACC-002",
                "order_id": "ORD-2001",
                "severity": "High",
                "status": "Open",
                "category": "Tracking Delay",
                "created_at": (SNAPSHOT - timedelta(hours=4)).isoformat(),
                "summary": "Second Tracking Delay report from LumenWorks",
                "resolution_notes": "",
            },
            {
                "ticket_id": "TKT-006",
                "account_id": "ACC-003",
                "order_id": None,
                "severity": "High",
                "status": "Open",
                "category": "Label Reprint",
                "created_at": (SNAPSHOT - timedelta(hours=6)).isoformat(),
                "summary": "Label reprint failed for multi-parcel order",
                "resolution_notes": "",
            },
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        readme.to_excel(writer, sheet_name="README", index=False)
        accounts.to_excel(writer, sheet_name="accounts", index=False)
        orders.to_excel(writer, sheet_name="orders", index=False)
        tickets.to_excel(writer, sheet_name="tickets", index=False)


def main() -> None:
    print("Generating synthetic ParcelPilot data pack...")
    for name, lines in DOCS.items():
        out = PDF_DIR / name
        write_pdf(out, lines)
        print(f"  wrote {out}")
    xlsx = EXCEL_DIR / "ParcelPilot_Assessment_Data.xlsx"
    write_excel(xlsx)
    print(f"  wrote {xlsx}")
    print("Done. Snapshot time:", SNAPSHOT.isoformat())


if __name__ == "__main__":
    main()
