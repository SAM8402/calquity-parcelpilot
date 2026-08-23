from typing import Optional

from langchain.tools import tool
from app.data.vector_store import search_with_metadata
from app.agent.reliability import get_reliability_label, resolve_conflicts
from app.auth.context import get_current_user
from app.auth.models import UserRole
from app.services.cache_service import cache_service


@tool
def search_documents(query: str, user_account_id: Optional[str] = None) -> str:
    """
    Search ParcelPilot policy documents, SOPs, product documentation,
    and customer agreements. Returns relevant excerpts with source
    attribution and authority level.

    Args:
        query: Natural language search query about ParcelPilot policies, SOPs, or agreements
        user_account_id: If customer, filters to their agreement only
    """
    # Enforce account scope at the tool layer (do not trust model-supplied IDs)
    user = get_current_user()
    if user and user.role == UserRole.CUSTOMER:
        user_account_id = user.account_id

    scope = user_account_id or "all"
    cached = cache_service.get_docs(query, scope)
    if isinstance(cached, str) and cached:
        return cached

    filter_dict = None
    if user_account_id:
        filter_dict = {
            "$or": [
                {"doc_type": {"$in": ["policy", "sop", "operations_guide"]}},
                {"customer_account_id": user_account_id},
            ]
        }

    try:
        results = search_with_metadata(query, k=4, filter_dict=filter_dict)
    except Exception as e:
        # Never fall back to unfiltered retrieval for customers
        user = get_current_user()
        if user and user.role == UserRole.CUSTOMER:
            return (
                "Document search temporarily unavailable with account filters. "
                f"Please retry. ({type(e).__name__})"
            )
        try:
            results = search_with_metadata(query, k=4)
        except Exception as e2:
            return f"Document search error: {e2}"

    if not results:
        return "No relevant documents found."

    # Customers must never receive another customer's agreement chunks
    if user and user.role == UserRole.CUSTOMER:
        filtered = []
        for doc, score in results:
            cust = doc.metadata.get("customer_account_id")
            if cust and cust != user.account_id:
                continue
            filtered.append((doc, score))
        results = filtered

    if not results:
        return "No relevant documents found for your account."

    docs = [doc for doc, _score in results]
    conflict_info = resolve_conflicts(docs)

    formatted = []
    for doc, score in results:
        reliability = get_reliability_label(doc.metadata)
        relevance = f"{(1 - score) * 100:.0f}%" if isinstance(score, float) else "N/A"
        formatted.append(
            f"[Source: {doc.metadata.get('source_file', 'unknown')} | "
            f"Authority: {doc.metadata.get('authority', 'unknown')} | "
            f"Status: {doc.metadata.get('status', 'N/A')} | "
            f"Relevance: {relevance} | "
            f"Reliability: {reliability}]\n{doc.page_content}"
        )

    result_text = "\n\n---\n\n".join(formatted)

    if conflict_info.get("warning"):
        result_text += f"\n\nWARNING: {conflict_info['warning']}"
    if conflict_info.get("conflicts"):
        conflict_notes = "; ".join(
            f"{c['lower_source']}: {c['reason']}" for c in conflict_info["conflicts"]
        )
        result_text += f"\n\nSOURCE CONFLICTS DETECTED: {conflict_notes}"
    result_text += f"\n\nCONFIDENCE: {conflict_info.get('confidence', 'unknown').upper()}"

    cache_service.set_docs(query, scope, result_text)
    return result_text
