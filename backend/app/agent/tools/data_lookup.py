from typing import Optional

import duckdb
from langchain.tools import tool
from app.config import DB_PATH
from app.auth.context import get_current_user
from app.auth.models import UserRole
from app.auth.middleware import verify_user_access
from app.services.cache_service import cache_service


def _get_connection():
    if DB_PATH.exists():
        return duckdb.connect(str(DB_PATH), read_only=True)
    return None


def _enforce_account_scope(requested_account_id: Optional[str]) -> Optional[str]:
    """Force customer queries onto their own account; ignore LLM-supplied overrides."""
    user = get_current_user()
    if user is None:
        return requested_account_id
    if user.role == UserRole.CUSTOMER:
        return user.account_id
    if requested_account_id and not verify_user_access(user, requested_account_id):
        return "__DENIED__"
    return requested_account_id


@tool
def query_structured_data(
    query_type: str,
    parameters: dict,
    user_account_id: Optional[str] = None,
) -> str:
    """
    Query ParcelPilot operational data (accounts, orders, tickets).

    Args:
        query_type: One of 'order_lookup', 'account_info', 'ticket_search',
                    'order_stats', 'ticket_stats', 'credit_calculation'
        parameters: Dict with query-specific params, e.g. {"order_id": "ORD-1001"}
        user_account_id: If customer, results are filtered to this account only
    """
    user_account_id = _enforce_account_scope(user_account_id)
    if user_account_id == "__DENIED__":
        return "ACCESS DENIED: You are not authorised to view that account."

    cached = cache_service.get_data(query_type, parameters or {}, user_account_id)
    if isinstance(cached, str) and cached:
        return cached

    con = _get_connection()
    if con is None:
        return "Database not available. Please run the data ingestion script first."

    try:
        if query_type == "order_lookup":
            order_id = parameters.get("order_id", "")
            sql = "SELECT * FROM orders WHERE order_id = ?"
            params = [order_id]
            if user_account_id:
                sql += " AND account_id = ?"
                params.append(user_account_id)
            result = con.execute(sql, params).fetchdf()

        elif query_type == "account_info":
            account_id = parameters.get("account_id", user_account_id)
            user = get_current_user()
            if user and user.role == UserRole.CUSTOMER:
                account_id = user.account_id
            elif account_id and user and not verify_user_access(user, account_id):
                return "ACCESS DENIED: You can only view your own account."
            sql = "SELECT * FROM accounts WHERE account_id = ?"
            result = con.execute(sql, [account_id]).fetchdf()

        elif query_type == "ticket_search":
            conditions = []
            params = []
            if user_account_id:
                conditions.append("account_id = ?")
                params.append(user_account_id)
            if parameters.get("status"):
                conditions.append("lower(cast(status as varchar)) = lower(?)")
                params.append(parameters["status"])
            # Official pack has no severity column — map severity intent to subject keywords
            if parameters.get("severity"):
                sev = str(parameters["severity"]).lower()
                if sev in ("critical", "high"):
                    conditions.append(
                        "(lower(cast(subject as varchar)) LIKE '%fail%' "
                        "OR lower(cast(subject as varchar)) LIKE '%500%' "
                        "OR lower(cast(description as varchar)) LIKE '%fail%' "
                        "OR lower(cast(subject as varchar)) LIKE '%urgent%')"
                    )
            if parameters.get("category"):
                conditions.append(
                    "(lower(cast(subject as varchar)) LIKE ? OR lower(cast(description as varchar)) LIKE ?)"
                )
                like = f"%{parameters['category'].lower()}%"
                params.extend([like, like])
            if parameters.get("ticket_id"):
                conditions.append("ticket_id = ?")
                params.append(parameters["ticket_id"])
            if parameters.get("subject_contains"):
                conditions.append("lower(cast(subject as varchar)) LIKE ?")
                params.append(f"%{parameters['subject_contains'].lower()}%")

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            sql = f"SELECT * FROM tickets WHERE {where_clause} ORDER BY created_at DESC LIMIT 20"
            result = con.execute(sql, params).fetchdf()

        elif query_type == "order_stats":
            sql = """
                SELECT account_id, COUNT(*) as total_orders,
                       COUNT(CASE WHEN status = 'Delivered' THEN 1 END) as delivered,
                       COUNT(CASE WHEN status = 'Cancelled' THEN 1 END) as cancelled
                FROM orders
            """
            params = []
            if user_account_id:
                sql += " WHERE account_id = ?"
                params.append(user_account_id)
            sql += " GROUP BY account_id"
            result = con.execute(sql, params).fetchdf()

        elif query_type == "ticket_stats":
            # Official pack has no severity column — summarise by status + channel
            sql = """
                SELECT status, channel, COUNT(*) as count
                FROM tickets
            """
            params = []
            if user_account_id:
                sql += " WHERE account_id = ?"
                params.append(user_account_id)
            sql += " GROUP BY status, channel ORDER BY count DESC"
            result = con.execute(sql, params).fetchdf()

        elif query_type == "credit_calculation":
            order_id = parameters.get("order_id", "")
            sql = "SELECT * FROM orders WHERE order_id = ?"
            params = [order_id]
            if user_account_id:
                sql += " AND account_id = ?"
                params.append(user_account_id)
            result = con.execute(sql, params).fetchdf()
            if not result.empty:
                fee = result.iloc[0].get("shipment_fee_inr")
                note = (
                    f"\n\nCredit helper: shipment_fee_inr={fee}. "
                    "Default SOP credit = lower of INR 500 or 10% of fee "
                    "when delay > 2h past pickup window + carrier_fault. "
                    "Customer agreements may override threshold/amount."
                )
                out = result.to_string(index=False) + note
                cache_service.set_data(query_type, parameters or {}, user_account_id, out)
                return out
            return "No records found matching your query."

        else:
            return (
                f"Unknown query type: {query_type}. Available types: "
                "order_lookup, account_info, ticket_search, order_stats, "
                "ticket_stats, credit_calculation"
            )

        if result.empty:
            return "No records found matching your query."
        out = result.to_string(index=False)
        cache_service.set_data(query_type, parameters or {}, user_account_id, out)
        return out

    except Exception as e:
        return f"Query error: {str(e)}"
    finally:
        con.close()
