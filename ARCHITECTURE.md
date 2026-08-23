# Architecture Note

## Agent Design

The system uses a **custom Gemini tool-calling loop** (compatible with LangChain tools) with Google Gemini as the reasoning LLM (primary + fallback model/API-key chain). The agent is built dynamically per-request, with the system prompt and available tools scoped to the authenticated user's role.

### Role-Based Agent Construction

| Role | Available Tools | System Prompt Context |
|------|----------------|----------------------|
| **Customer** | `search_documents`, `query_structured_data` | Scoped to own account_id, cannot see other customers |
| **Support Agent** | Above + `prepare_action`, `list_pending_actions` (confirm via UI `/api/confirm`) | Full data access, can escalate |
| **Operations** | All above + `detect_proactive_issues` | Full access, strategic analysis |

The agent uses a manual `bind_tools` loop (not AgentExecutor) so every `ToolMessage` includes a valid tool name — this avoids a Gemini API failure mode with empty `function_response.name`. Intermediate tool steps are returned so the frontend can display tool usage transparency.

### Multi-Step Reasoning

For complex queries (e.g., "Can Northstar cancel ORD-1001 without a fee?"), the agent autonomously chains multiple tools:

1. `query_structured_data(order_lookup, {order_id: "ORD-1001"})` → Gets order details + account
2. `search_documents("Northstar cancellation policy")` → Finds enterprise agreement
3. `search_documents("cancellation fee policy SOP")` → Gets general cancellation SOP
4. Agent reasons: agreement overrides general policy → provides answer with citations

## Tool Design

### Tool 1: Document Search (`search_documents`)
- **Implementation**: ChromaDB vector similarity search with metadata filtering
- **Embeddings**: Google `models/gemini-embedding-001`
- **Chunking**: `RecursiveCharacterTextSplitter` with 1000-char chunks, 200-char overlap
- **Filtering**: Customers see only general docs + their own agreement; internal users see everything
- **Output enrichment**: Each result annotated with source file, authority level, status, and reliability label

### Tool 2: Structured Data Lookup (`query_structured_data`)
- **Implementation**: DuckDB parameterised SQL queries
- **Query types**: `order_lookup`, `account_info`, `ticket_search`, `order_stats`, `ticket_stats`, `credit_calculation`
- **Access control**: Enforced at SQL WHERE clause level — customer queries always include `AND account_id = ?`
- **Security**: Uses parameterised queries to prevent injection

### Tool 3: State-Changing Actions (`prepare_action` + UI confirm)
- **Pattern**: Two-phase commit — `prepare_action` stages the action; execution happens only via `/api/confirm` after explicit user approval (not available as an agent tool, so the model cannot self-confirm)
- **Action types**: `escalate_ticket`, `update_ticket_status`, `create_followup_task`, `apply_service_credit`
- **Frontend integration**: `ChatWindow` detects pending actions and surfaces a `ConfirmationDialog` modal

## Document and Structured-Data Handling

### PDFs → Vector Database
Each PDF is ingested with rich metadata:
```
{
  "source_file": "05_Northstar_Logistics_Enterprise_Agreement.pdf",
  "doc_type": "customer_agreement",
  "customer": "Northstar Logistics",
  "customer_account_id": "ACC-001",
  "authority": "highest",
  "status": "CURRENT"
}
```
This metadata enables both access-control filtering and source reliability reasoning.

### Excel → SQL Database
The assessment workbook's sheets are loaded into DuckDB as individual tables (`accounts`, `orders`, `tickets`). DuckDB was chosen for:
- Zero-config, in-process analytical engine
- Full SQL support including aggregations
- No separate database server needed

## Source Reliability and Conflict Handling

The system implements a 5-tier authority hierarchy:

| Tier | Authority | Score | Example |
|------|-----------|-------|---------|
| 1 | `highest` | 5 | Customer-specific enterprise agreements |
| 2 | `high` | 4 | Current policies (v3), SOPs (v4) |
| 3 | `medium` | 3 | Operations guides |
| 4 | `low` | 1 | Deprecated documents (v2) |
| 5 | `unknown` | 0 | Untagged sources |

**Conflict resolution**: When multiple sources are retrieved for the same query, the `resolve_conflicts()` function:
1. Sorts by authority score
2. Identifies the winning source
3. Lists overridden sources with explanations
4. Computes a confidence level
5. Generates warnings when only deprecated or low-authority sources match

**Uncertainty handling**: The agent is instructed to:
- Never fabricate data
- Suggest escalation when confidence is low
- Explicitly warn when citing deprecated sources
- Note when customer agreements override general policy

## Major Technical Trade-offs

| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| LLM | Gemini 2.0 Flash | GPT-4o | Free tier, fast, good function calling |
| Vector DB | ChromaDB (local) | Pinecone (hosted) | Zero-config, no external dependency |
| SQL Engine | DuckDB | PostgreSQL | Embedded, analytical, no server needed |
| Auth | Mock (in-memory) | JWT/OAuth | Simplified for assessment; production pattern shown |
| Frontend | Next.js + Tailwind | Vanilla React | App Router, API proxying, production-ready |
| Actions | In-memory mock | Real DB writes | Assessment scope; pattern supports real implementation |
