# ParcelPilot AI Support Agent

An AI-powered customer support system for **ParcelPilot**, a B2B logistics platform. Built with LangChain + Google Gemini for intelligent multi-step reasoning, ChromaDB for document retrieval, DuckDB for structured data queries, and Redis for response/tool caching.

## Live Prototype and Deployment

- **Deploy guide (Render):** see [`DEPLOY_RENDER.md`](./DEPLOY_RENDER.md) — same single-container pattern as [Gyansetu](https://github.com/SAM8402/Gyansetu) (`Dockerfile` + `render.yaml` + `$PORT`).
- After you deploy, put your URL here: `https://<your-service>.onrender.com`

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

## 🚀 Quick Start

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

**Deploy / default:** leave `REDIS_URL` empty — the app uses **fakeredis** in-process (Gyansetu-style). No Redis server on Render.

**Local (optional real Redis):**

```bash
docker run -d --name parcelpilot-redis -p 6379:6379 redis:7-alpine
# Or: docker compose up redis -d
```

```env
REDIS_URL=redis://localhost:6379/0
```

`/api/health` reports `cache_backend`: `fakeredis` or `redis`.

### 5. Run Backend

```bash
uvicorn app.main:app --reload --port 8000
```

### 6. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

> **WSL note:** If `npm install` corrupts packages on `/mnt/d/...` (SyntaxError in `next` binary), install/run from a Linux filesystem path instead, e.g. copy `frontend/` to `~/calquity-frontend`, then `npm install && npm run dev` there with `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`.

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

## 📋 Example Queries

| Query | What happens |
|-------|-------------|
| "Can Northstar cancel ORD-1001 without a fee?" | Multi-step: order lookup → agreement check → policy comparison |
| "A pickup is 3 hours late due to carrier fault. Credit?" | SOP lookup → credit eligibility calculation |
| "Show all open high-severity tickets" | Structured data query with filtering |
| "Escalate ticket TKT-003 to engineering" | Prepares action → shows confirmation dialog |
| "What issues are affecting multiple customers?" | Proactive detection (Ops role only) |

## 📁 Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Environment configuration
│   │   ├── setup_db.py          # One-time data setup
│   │   ├── agent/
│   │   │   ├── orchestrator.py  # Agent builder
│   │   │   ├── prompts.py       # System prompts
│   │   │   ├── reliability.py   # Source reliability engine
│   │   │   └── tools/           # Agent tools
│   │   ├── auth/                # Mock auth & access control
│   │   ├── data/                # Data ingestion pipelines
│   │   └── models/              # Pydantic schemas
│   └── data/                    # Raw data files
├── frontend/
│   └── src/
│       ├── app/                 # Next.js pages
│       └── components/          # React components
├── docker-compose.yml
├── ARCHITECTURE.md
└── PRODUCT_NOTE.md
```

## AI Tools Used

See **[AI_TOOL_USAGE.md](./AI_TOOL_USAGE.md)** for the submission statement.

- **Google Gemini 2.5 Flash** (+ fallback chain) — Agent reasoning and tool calling
- **Google `gemini-embedding-001`** — Document embeddings for ChromaDB
- **LangChain** — Agent orchestration and tools
- **Cache** — fakeredis by default; optional Redis when `REDIS_URL` is set
- **Cursor** — AI coding assistant used during development
