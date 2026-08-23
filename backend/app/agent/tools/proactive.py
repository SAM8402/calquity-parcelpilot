import duckdb
from langchain.tools import tool
from app.config import DB_PATH


@tool
def detect_proactive_issues() -> str:
    """
    Scan ticket and order data for recurring, urgent, or unusual patterns.
    Returns a summary of issues requiring attention.
    """
    if not DB_PATH.exists():
        return "Database not available. Run data ingestion first."

    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        analyses = []

        try:
            open_tickets = con.execute("""
                SELECT ticket_id, account_id, status, subject, channel,
                       assigned_to, created_at, last_customer_message_at
                FROM tickets
                WHERE lower(cast(status as varchar)) NOT IN ('resolved', 'closed')
                ORDER BY created_at ASC
                LIMIT 20
            """).fetchdf()
            if not open_tickets.empty:
                analyses.append("=== OPEN TICKETS (oldest first) ===")
                analyses.append(open_tickets.to_string(index=False))
        except Exception as e:
            analyses.append(f"(open tickets query skipped: {e})")

        try:
            recurring = con.execute("""
                SELECT lower(subject) as subject_key,
                       COUNT(*) as count,
                       COUNT(DISTINCT account_id) as affected_accounts,
                       string_agg(DISTINCT cast(account_id as varchar), ', ') as account_list,
                       string_agg(DISTINCT cast(ticket_id as varchar), ', ') as ticket_ids
                FROM tickets
                WHERE lower(cast(status as varchar)) NOT IN ('closed', 'resolved')
                GROUP BY lower(subject)
                HAVING COUNT(*) >= 2 OR COUNT(DISTINCT account_id) > 1
                ORDER BY count DESC
            """).fetchdf()
            if not recurring.empty:
                analyses.append("\n=== RECURRING / SIMILAR OPEN SUBJECTS ===")
                analyses.append(recurring.to_string(index=False))
        except Exception as e:
            analyses.append(f"(recurring subjects query skipped: {e})")

        try:
            multi_customer = con.execute("""
                SELECT
                    CASE
                        WHEN lower(subject) LIKE '%fail%' OR lower(description) LIKE '%fail%'
                            OR lower(subject) LIKE '%500%' OR lower(description) LIKE '%error%'
                            THEN 'product_failure'
                        WHEN lower(subject) LIKE '%upload%' OR lower(description) LIKE '%csv%'
                            THEN 'bulk_upload'
                        WHEN lower(subject) LIKE '%cancel%' OR lower(description) LIKE '%cancel%'
                            THEN 'cancellation'
                        WHEN lower(subject) LIKE '%credit%' OR lower(description) LIKE '%credit%'
                            OR lower(subject) LIKE '%delay%' OR lower(description) LIKE '%late%'
                            THEN 'delay_credit'
                        ELSE 'other'
                    END AS issue_theme,
                    COUNT(DISTINCT account_id) as customer_count,
                    COUNT(*) as total_tickets,
                    string_agg(DISTINCT cast(account_id as varchar), ', ') as accounts
                FROM tickets
                WHERE lower(cast(status as varchar)) NOT IN ('closed', 'resolved')
                GROUP BY 1
                HAVING COUNT(DISTINCT account_id) > 1
                ORDER BY customer_count DESC
            """).fetchdf()
            if not multi_customer.empty:
                analyses.append("\n=== ISSUES AFFECTING MULTIPLE CUSTOMERS ===")
                analyses.append(multi_customer.to_string(index=False))
        except Exception as e:
            analyses.append(f"(multi-customer query skipped: {e})")

        try:
            delayed = con.execute("""
                SELECT order_id, account_id, carrier, status,
                       pickup_window_end, pickup_actual_at,
                       shipment_fee_inr, carrier_fault, customer_fault, notes
                FROM orders
                WHERE carrier_fault = TRUE
                   OR (pickup_actual_at IS NOT NULL AND pickup_actual_at > pickup_window_end)
                   OR lower(cast(status as varchar)) LIKE '%delay%'
                ORDER BY account_id
            """).fetchdf()
            if not delayed.empty:
                analyses.append("\n=== ORDERS WITH DELAY / CARRIER FAULT SIGNALS ===")
                analyses.append(delayed.to_string(index=False))
        except Exception as e:
            analyses.append(f"(order anomaly query skipped: {e})")

        try:
            cancel_pending = con.execute("""
                SELECT order_id, account_id, status, booked_at,
                       pickup_window_start, cancellation_requested_at,
                       shipment_fee_inr, notes
                FROM orders
                WHERE cancellation_requested_at IS NOT NULL
                ORDER BY cancellation_requested_at
            """).fetchdf()
            if not cancel_pending.empty:
                analyses.append("\n=== ORDERS WITH CANCELLATION REQUESTS ===")
                analyses.append(cancel_pending.to_string(index=False))
        except Exception as e:
            analyses.append(f"(cancellation query skipped: {e})")

        if not analyses:
            return "No proactive issues detected at this time."

        return "\n".join(analyses)

    finally:
        con.close()
