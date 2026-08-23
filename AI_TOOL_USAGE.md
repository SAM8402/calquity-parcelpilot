# AI Tool Usage

Brief statement for the CalQuity AI Engineer assessment submission.

## Tools used

| Tool | How it was used |
|------|-----------------|
| **Cursor** (Composer / Auto) | Primary AI coding assistant for scaffolding FastAPI + Next.js, agent tools, access-control hardening, Redis caching, verification scripts, and iterative debugging against the official candidate data pack. |
| **Google Gemini** (`gemini-2.5-flash` + fallbacks) | Runtime LLM for agent reasoning and tool calling in the ParcelPilot support system. |
| **Google `gemini-embedding-001`** | Document embeddings for ChromaDB RAG over the supplied PDFs. |

## How AI coding assistance was applied

- Translated the assessment requirements into a concrete architecture (agent + tools + ACL + reliability).
- Implemented and refined LangChain tool-calling with Gemini, including confirmation gating and role-scoped tools.
- Built ingestion pipelines for the official Excel/PDF pack and aligned IDs (`ACCT-001`, `ORD-1001`, snapshot time).
- Wrote smoke / edge-case verification scripts and used them to find and fix ACL, confirmation, and schema issues.
- Human judgment remained on product decisions (which extra client problem to prioritise, what to leave out, demo scope).

I did not paste proprietary ParcelPilot source code into tools beyond the candidate pack provided for the assessment.
