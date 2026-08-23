# Product Note

## Additional Client Problem Addressed

### Problem 2: Trust and Reliability

I chose to prioritise trust and reliability because a confidently incorrect answer in a customer-facing logistics context — especially around cancellation fees, service credits, or SLA terms — would erode adoption faster than a missing feature would.

#### How it's addressed:

1. **Source authority hierarchy**: Every document chunk is tagged with an authority level. Customer-specific agreements (`highest`) always override general policies (`high`), which override deprecated docs (`low`). The agent is instructed to follow this hierarchy and cite its sources.

2. **Conflict detection**: When the vector search returns documents from different authority tiers, the reliability engine explicitly flags which source wins and why. This appears in the tool output so the LLM can reason about it transparently.

3. **Deprecated source warnings**: If the only matching source is a deprecated document (e.g., Support Policy v2), the system appends an explicit warning. The agent is instructed never to present deprecated information as current policy.

4. **Escalation on uncertainty**: When confidence is below the threshold (e.g., no high-authority source matches, or the question involves financial amounts or exceptions), the agent recommends human review rather than guessing.

5. **Historical ticket caveat**: Past ticket resolutions are treated as context only. The system prompt explicitly tells the agent they may contain incorrect information, preventing the common RAG failure of treating any retrieved text as ground truth.

---

## What I Would Build Next

### Priority 1: Proactive Issue Dashboard (Problem 1 — partially implemented)
The `detect_proactive_issues` tool already surfaces SLA breaches, recurring issues, and multi-customer patterns. Next step: a dedicated dashboard view (not just chat) with:
- Real-time ticket heatmaps by category and severity
- Automated alerts when unusual patterns emerge (spike detection)
- Drill-down from pattern → individual tickets

**Why it matters**: Reactive support (waiting for questions) only helps one customer at a time. Proactive detection prevents problems from escalating across the customer base.

### Priority 2: Feedback Loop for Answer Quality
Let support agents rate AI answers (👍/👎) with optional notes. Use this signal to:
- Fine-tune retrieval relevance
- Identify documents that need updating
- Track accuracy trends over time

**Why it matters**: Without measurable quality, you can't improve the system or justify expanding its role.

### Priority 3: Streaming Responses
Implement server-sent events (SSE) so the user sees the response building in real-time rather than waiting for the full completion. Show tool invocations as they happen.

**Why it matters**: A 10-second wait for a multi-tool query feels broken. Streaming with live tool indicators makes it feel fast and transparent.

### Priority 4: Conversation Summaries and Handoff
When the AI escalates to a human agent, generate a structured handoff note containing:
- Customer context (account, recent orders)
- What the AI found and what it couldn't answer
- Suggested next steps

**Why it matters**: Reduces the time a human agent spends re-asking the customer what they need.

### Priority 5: Document Version Management
Build an admin workflow to upload new document versions, auto-tag authority/status, and re-index without downtime.

**Why it matters**: Policies change frequently. The current system requires manual metadata tagging and re-ingestion.

---

## What I Intentionally Left Out

| Omission | Reason |
|----------|--------|
| **Production authentication (JWT/OAuth)** | Mocked for assessment scope; the data-layer access pattern is production-ready |
| **Streaming responses** | Would add complexity; demonstrated the core agent + tool pipeline first |
| **Persistent chat history (database-backed)** | In-memory is sufficient for demo; PostgreSQL-backed history is a straightforward follow-up |
| **Hosted production deployment** | Local/Docker ready; hosted URL is preferred for submission but left to the candidate environment |
| **Fine-tuned embeddings** | Default Google embeddings perform well for this document set |
| **Comprehensive CI test suite** | Smoke + edge verification scripts are included; full CI is a follow-up |

---

## Key Metric

**First-Contact Resolution Rate (FCR) via AI**

> *Percentage of customer support queries fully and correctly resolved by the AI agent without requiring human escalation.*

**Why this metric**:
- It directly measures whether the product is useful (does it actually resolve problems?)
- It accounts for both coverage (can the AI answer?) and accuracy (is the answer correct?)
- It's measurable: track queries that don't trigger escalation and sample-audit for correctness
- Target: 60–70% FCR in the first quarter, rising to 80%+ as the document base and feedback loop mature

**Supporting metrics**:
- Average tool chain length per query (are multi-step queries working?)
- Escalation rate by category (which areas need more documentation?)
- User satisfaction score (post-chat thumbs up/down)
