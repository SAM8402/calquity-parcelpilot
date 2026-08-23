AUTHORITY_HIERARCHY = {
    "highest": 5,
    "high": 4,
    "medium": 3,
    "low": 1,
    "unknown": 0,
}


def get_reliability_label(metadata: dict) -> str:
    status = metadata.get("status", "")
    authority = metadata.get("authority", "unknown")

    if status == "DEPRECATED":
        return "DEPRECATED - use as context only, do NOT cite as current policy"
    if authority == "highest":
        return "CUSTOMER AGREEMENT - overrides general policy for this customer"
    if authority == "high":
        return "CURRENT - authoritative source"
    if authority == "medium":
        return "SUPPLEMENTARY - operations guide context"
    return "LOW AUTHORITY - treat with caution"


def resolve_conflicts(retrieved_docs: list) -> dict:
    if not retrieved_docs:
        return {
            "primary_source": None,
            "conflicts": [],
            "confidence": "none",
            "warning": "No sources found for this query.",
        }

    sorted_docs = sorted(
        retrieved_docs,
        key=lambda d: AUTHORITY_HIERARCHY.get(
            d.metadata.get("authority", "low"), 0
        ),
        reverse=True,
    )

    winner = sorted_docs[0]
    conflicts = []

    for doc in sorted_docs[1:]:
        doc_authority = doc.metadata.get("authority", "low")
        winner_authority = winner.metadata.get("authority", "low")
        if AUTHORITY_HIERARCHY.get(doc_authority, 0) < AUTHORITY_HIERARCHY.get(
            winner_authority, 0
        ):
            conflicts.append(
                {
                    "lower_source": doc.metadata.get("source_file", "unknown"),
                    "reason": f"Overridden by higher-authority source: {winner.metadata.get('source_file', 'unknown')}",
                }
            )

    winner_authority = winner.metadata.get("authority", "unknown")
    if winner_authority in ("highest", "high"):
        confidence = "high"
    elif winner_authority == "medium":
        confidence = "medium"
    else:
        confidence = "low"

    warning = None
    if confidence == "low":
        warning = "Only low-authority or deprecated sources found. Consider verifying with the team."
    if winner.metadata.get("status") == "DEPRECATED":
        warning = "The only matching source is DEPRECATED. This may not reflect current policy."

    return {
        "primary_source": winner,
        "conflicts": conflicts,
        "confidence": confidence,
        "warning": warning,
    }


def assess_answer_confidence(answer_text: str, sources: list) -> dict:
    has_customer_agreement = any(
        s.metadata.get("authority") == "highest" for s in sources
    )
    has_current_policy = any(
        s.metadata.get("authority") == "high" for s in sources
    )
    only_deprecated = all(
        s.metadata.get("status") == "DEPRECATED" for s in sources
    ) if sources else True

    confidence_score = 0
    if has_customer_agreement:
        confidence_score += 50
    if has_current_policy:
        confidence_score += 30
    if len(sources) >= 2:
        confidence_score += 10
    if not only_deprecated:
        confidence_score += 10

    recommendation = None
    if confidence_score < 40:
        recommendation = "Consider escalating to a human agent for verification."
    elif only_deprecated:
        recommendation = "Warning: Only deprecated sources available. Verify with current documentation."

    return {
        "confidence_score": min(confidence_score, 100),
        "has_customer_agreement": has_customer_agreement,
        "has_current_policy": has_current_policy,
        "only_deprecated": only_deprecated,
        "recommendation": recommendation,
    }
