from langchain.tools import tool
from datetime import datetime
import json
from typing import Optional

from app.auth.context import get_current_user
from app.auth.middleware import can_take_actions
from app.auth.models import User

ACTION_LOG: list[dict] = []


@tool
def prepare_action(
    action_type: str,
    details: dict,
    requires_confirmation: bool = True,
) -> str:
    """
    Prepare a state-changing action for user confirmation.
    The action is NOT executed until the user explicitly confirms in the UI.
    Do NOT attempt to execute or confirm the action yourself.

    Args:
        action_type: One of 'escalate_ticket', 'update_ticket_status',
                     'create_followup_task', 'apply_service_credit'
        details: Action-specific details dict
        requires_confirmation: Always True for state-changing actions
    """
    user = get_current_user()
    if user is None or not can_take_actions(user):
        return "ACCESS DENIED: Only support/operations staff can prepare actions."

    action = {
        "action_id": f"ACT-{len(ACTION_LOG) + 1:04d}",
        "action_type": action_type,
        "details": details,
        "status": "PENDING_CONFIRMATION",
        "prepared_at": datetime.now().isoformat(),
        "prepared_by": user.user_id,
        "prepared_by_role": user.role.value,
    }
    ACTION_LOG.append(action)

    if action_type == "escalate_ticket":
        summary = (
            f"Escalation Prepared\n"
            f"- Ticket: {details.get('ticket_id', 'N/A')}\n"
            f"- Reason: {details.get('reason', 'N/A')}\n"
            f"- Priority: {details.get('priority', 'Normal')}\n"
            f"- Action ID: {action['action_id']}\n\n"
            f"Please confirm to proceed with this escalation."
        )
    elif action_type == "update_ticket_status":
        summary = (
            f"Ticket Update Prepared\n"
            f"- Ticket: {details.get('ticket_id', 'N/A')}\n"
            f"- New Status: {details.get('new_status', 'N/A')}\n"
            f"- Note: {details.get('note', 'N/A')}\n"
            f"- Action ID: {action['action_id']}\n\n"
            f"Please confirm to apply this update."
        )
    elif action_type == "create_followup_task":
        summary = (
            f"Follow-up Task Prepared\n"
            f"- Related Ticket: {details.get('ticket_id', 'N/A')}\n"
            f"- Task: {details.get('description', 'N/A')}\n"
            f"- Assigned To: {details.get('assigned_to', 'Unassigned')}\n"
            f"- Action ID: {action['action_id']}\n\n"
            f"Please confirm to create this task."
        )
    elif action_type == "apply_service_credit":
        summary = (
            f"Service Credit Prepared\n"
            f"- Order: {details.get('order_id', 'N/A')}\n"
            f"- Amount: {details.get('amount', 'N/A')}\n"
            f"- Reason: {details.get('reason', 'N/A')}\n"
            f"- Action ID: {action['action_id']}\n\n"
            f"Please confirm to apply this service credit."
        )
    else:
        summary = (
            f"Action prepared: {json.dumps(action, indent=2)}\n\n"
            f"Please confirm."
        )

    return summary


def execute_confirmed_action(action_id: str, user: User) -> str:
    """Execute a prepared action after explicit UI confirmation (HTTP only)."""
    if not can_take_actions(user):
        return "ACCESS DENIED: Only support/operations staff can confirm actions."

    for action in ACTION_LOG:
        if action["action_id"] != action_id:
            continue
        if action["status"] != "PENDING_CONFIRMATION":
            return f"Action {action_id} is already {action['status']}."
        owner = action.get("prepared_by")
        if owner and owner != user.user_id and user.role.value != "operations":
            return (
                f"ACCESS DENIED: Action {action_id} was prepared by {owner}. "
                "Only the preparer or operations can confirm it."
            )
        action["status"] = "EXECUTED"
        action["executed_at"] = datetime.now().isoformat()
        action["executed_by"] = user.user_id
        return (
            f"Action {action_id} ({action['action_type']}) has been "
            f"executed successfully."
        )
    return f"Action {action_id} not found."


@tool
def list_pending_actions() -> str:
    """List actions awaiting confirmation for the current user (ops sees all)."""
    user = get_current_user()
    if user is None or not can_take_actions(user):
        return "ACCESS DENIED."

    pending = [a for a in ACTION_LOG if a["status"] == "PENDING_CONFIRMATION"]
    if user.role.value != "operations":
        pending = [a for a in pending if a.get("prepared_by") == user.user_id]

    if not pending:
        return "No pending actions."
    lines = []
    for a in pending:
        lines.append(
            f"- {a['action_id']}: {a['action_type']} "
            f"(prepared by {a.get('prepared_by', '?')} at {a['prepared_at']})"
        )
    return "\n".join(lines)
