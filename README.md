# ParcelPilot AI Support Agent

An AI-powered customer support system for **ParcelPilot**, a B2B logistics platform. Built with LangChain + Google Gemini for intelligent multi-step reasoning, ChromaDB for document retrieval, DuckDB for structured data queries, and Redis for response/tool caching.

## Live Prototype

**Demo:** [https://calquity-parcelpilot.onrender.com](https://calquity-parcelpilot.onrender.com)

> First load after idle takes ~30-60s (Render free-tier cold start). Subsequent requests are fast.

## Features

- **Dual-context chatbot** — Customer-facing support + internal operations mode
- **3 Agent Tools** — Document search, structured data lookup, state-changing actions
- **Access control at data layer** — Customers only see their own account data
- **Source reliability engine** — 5-tier authority hierarchy with conflict detection
- **Confirmation before actions** — Escalations and updates require explicit user approval
- **Multi-step reasoning** — Chains tools to answer complex, cross-source queries
- **Proactive issue detection** — Surfaces recurring issues, SLA breaches, and patterns
- **Tool transparency UI** — Shows which tools the AI used for each response
- **Redis caching** — Speeds up repeated FAQ chats, document search, and data lookups (fakeredis on deploy; optional real Redis locally)

## Architecture

```
┌──────────────────┐     ┌──────────────────────────────────────┐
│   Next.js Chat   │────▶│          FastAPI Backend              │
│   (Frontend)     │     │                                      │
│                  │     │  LangChain Agent (Gemini)             │
│  • User Switcher │     │  Tools: docs / SQL / actions / ops    │
│  • Tool Display  │     │                                      │
│  • Confirmation  │     │  ChromaDB · DuckDB · cache (Redis/fakeredis) │
└──────────────────┘     └──────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| **LLM** | Google Gemini 2.5 Flash (+ fallback chain) |
| **Embeddings** | Google `gemini-embedding-001` (auto-fallback to local FastEmbed ONNX) |
| **Agent Framework** | LangChain with custom Gemini tool-calling loop |
| **Vector Database** | ChromaDB (in-process, zero-config) |
| **SQL Database** | DuckDB (embedded analytical engine) |
| **Cache** | fakeredis (default) / Redis (optional) |
| **Backend** | Python 3.11, FastAPI, uvicorn |
| **Frontend** | Next.js 14, React, Tailwind CSS |
| **Deploy** | Docker (multi-stage) on Render |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Google AI API key ([Get one here](https://aistudio.google.com/apikey))

### 1. Clone & Configure

```bash
git clone https://github.com/YOUR_USERNAME/parcelpilot-ai-support.git
cd parcelpilot-ai-support
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Ingest Data

Place the assessment data files (or keep them in `backend/AI Agent Assessment - Candidate Pack/`):
- PDFs → `backend/data/pdfs/`
- Excel → `backend/data/excel/`

`python -m app.setup_db` will auto-sync from the Candidate Pack folder if present.

```bash
# Ingest Excel data into DuckDB + PDFs into ChromaDB
python -m app.setup_db
```

### 4. Cache (Redis optional)

**Deploy / default:** leave `REDIS_URL` empty — the app uses **fakeredis** in-process. No Redis server on Render.

**Local (optional real Redis):**

```bash
docker compose --profile redis up redis -d
```

```env
REDIS_URL=redis://localhost:6379/0
```

`/api/health` reports `cache_backend`: `fakeredis` or `redis`.

### 5. Run Backend

```bash
cd backend
source venv/bin/activate   # Windows: venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

### 6. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 7. Open the App

Visit **http://localhost:3000** and start chatting!

Use the **User Switcher** in the top-right to switch between:

| User | Role | Access |
|------|------|--------|
| Alex (Northstar) | Customer | Own account data only |
| Jordan (LumenWorks) | Customer | Own account data only |
| Sam (Support) | Support Agent | All data, can escalate |
| Taylor (Ops) | Operations | Full access + proactive detection |

### Docker (Alternative)

```bash
docker-compose up --build
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Send message to AI agent |
| `POST` | `/api/confirm` | Confirm a pending action (escalate, update, etc.) |
| `POST` | `/api/reset` | Clear chat history for a session |
| `POST` | `/api/cache/clear` | Clear Redis caches (support/ops only) |
| `GET` | `/api/users` | List available mock users |
| `GET` | `/api/health` | Health check with service status |

## Example Queries

| Query | What happens |
|-------|-------------|
| "Can Northstar cancel ORD-1001 without a fee?" | Multi-step: order lookup → agreement check → policy comparison |
| "A pickup is 3 hours late due to carrier fault. Credit?" | SOP lookup → credit eligibility calculation |
| "Show all open high-severity tickets" | Structured data query with filtering |
| "Escalate ticket TKT-003 to engineering" | Prepares action → shows confirmation dialog |
| "What issues are affecting multiple customers?" | Proactive detection (Ops role only) |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point + static UI serving
│   │   ├── config.py            # Environment configuration
│   │   ├── setup_db.py          # One-time data setup
│   │   ├── agent/
│   │   │   ├── orchestrator.py  # Agent builder (Gemini tool-calling loop)
│   │   │   ├── prompts.py       # Role-scoped system prompts
│   │   │   ├── reliability.py   # 5-tier source reliability engine
│   │   │   ├── llm.py           # LLM provider setup + fallback chain
│   │   │   └── tools/
│   │   │       ├── document_search.py   # ChromaDB vector search
│   │   │       ├── data_lookup.py       # DuckDB SQL queries
│   │   │       ├── actions.py           # State-changing actions (2-phase)
│   │   │       └── proactive.py         # Issue detection (Ops only)
│   │   ├── auth/
│   │   │   ├── models.py        # User/role definitions
│   │   │   ├── middleware.py     # Access control helpers
│   │   │   └── context.py       # Current user context
│   │   ├── data/
│   │   │   ├── embeddings.py    # Google/local embedding provider
│   │   │   ├── vector_store.py  # ChromaDB client
│   │   │   ├── ingest_documents.py  # PDF → ChromaDB
│   │   │   └── ingest_excel.py      # Excel → DuckDB
│   │   └── models/
│   │       └── schemas.py       # Pydantic request/response models
│   ├── data/
│   │   ├── pdfs/                # Support policies, agreements, SOPs
│   │   └── excel/               # ParcelPilot assessment workbook
│   ├── tests/                   # Pytest test suite
│   └── scripts/
│       └── render_start.sh      # Render/Docker entrypoint
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── page.tsx         # Main chat page
│       │   └── layout.tsx       # Root layout
│       └── components/
│           ├── ChatWindow.tsx           # Chat message list + input
│           ├── MessageBubble.tsx        # Individual message display
│           ├── UserSwitcher.tsx         # Role/user selector
│           ├── ToolIndicator.tsx        # Shows tools used by AI
│           └── ConfirmationDialog.tsx   # Action confirmation modal
├── .github/workflows/ci.yml    # GitHub Actions CI
├── Dockerfile                   # Multi-stage production build
├── docker-compose.yml           # Local dev with optional Redis
├── render.yaml                  # Render Blueprint spec
├── ARCHITECTURE.md              # Technical architecture details
├── AI_TOOL_USAGE.md             # AI tool submission statement
└── DEPLOY_RENDER.md             # Render deployment guide
```

## Deployment (Render)

The app deploys as a **single Docker container** — Next.js static export is baked into the FastAPI image and served on the same origin.

### Option A — Blueprint (recommended)

1. Push this repo to GitHub
2. Render Dashboard → **New** → **Blueprint**
3. Connect the GitHub repo → apply `render.yaml`
4. Set **GOOGLE_API_KEY** (secret) when prompted
5. Wait for first build (~3-5 min for Node + pip + data ingestion)
6. Open `https://calquity-parcelpilot.onrender.com`

### Option B — Manual Web Service

1. Render Dashboard → **New** → **Web Service**
2. Connect repo, set:
   - **Runtime:** Docker
   - **Dockerfile path:** `./Dockerfile`
   - **Health check path:** `/api/health`
   - **Plan:** Free
3. Set environment variables:

```
GOOGLE_API_KEY=<your key>
GEMINI_MODEL=gemini-2.5-flash
LLM_FALLBACK_CHAIN=gemini-2.5-flash,gemini-2.5-flash-lite,gemini-2.0-flash,gemini-2.0-flash-lite,gemini-2.5-pro
EMBEDDING_MODEL=models/gemini-embedding-001
CORS_ORIGINS=["*"]
REDIS_URL=
```

4. Deploy → verify at `/api/health`

### Free-Tier Notes

- **512 MB RAM** — single worker, no torch
- **Cold starts** — ~30-60s after idle
- **Ephemeral disk** — DuckDB/ChromaDB rebuild on boot if lost
- **Redis** — not required; empty `REDIS_URL` uses fakeredis

## AI Tools Used

See **[AI_TOOL_USAGE.md](./AI_TOOL_USAGE.md)** for the submission statement.

- **Google Gemini 2.5 Flash** (+ fallback chain) — Agent reasoning and tool calling
- **Google `gemini-embedding-001`** — Document embeddings for ChromaDB
- **LangChain** — Agent orchestration and tools
- **Cursor** — AI coding assistant used during development

## License

This project was built for the CalQuity AI Engineer assessment.
