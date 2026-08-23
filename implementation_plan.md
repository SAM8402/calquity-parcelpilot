# ParcelPilot AI Support Agent — Full Implementation Guide

> **Assessment for:** CalQuity AI Engineer Role  
> **Project:** Build an AI-powered customer support system for ParcelPilot (B2B logistics platform)

---

## High-Level Summary

You must build **at least one AI chatbot** (customer-facing OR internal ops) that:
- Answers natural-language queries using a supplied data pack (PDFs + Excel)
- Enforces access control at the data layer
- Has **≥ 3 distinct tools** (document search, structured-data lookup, state-changing action)
- Requires **user confirmation** before state-changing actions
- Handles **multi-step** reasoning across multiple tools/sources
- Exposes a **chat UI** that shows which tool is being used
- Is **hosted** (highly preferred)

---

## Phase 0 — Project Setup & Data Preparation

### Step 0.1: Initialise the Repository

```
CalQuity/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py          # FastAPI entry point
│   │   ├── config.py        # Env vars, API keys
│   │   ├── agent/           # Agent orchestration
│   │   │   ├── orchestrator.py
│   │   │   ├── prompts.py
│   │   │   └── tools/
│   │   │       ├── document_search.py
│   │   │       ├── data_lookup.py
│   │   │       └── actions.py
│   │   ├── auth/            # Mock auth & access control
│   │   │   ├── middleware.py
│   │   │   └── models.py
│   │   ├── data/            # Data ingestion & storage
│   │   │   ├── ingest_documents.py
│   │   │   ├── ingest_excel.py
│   │   │   └── vector_store.py
│   │   └── models/          # Pydantic schemas
│   │       ├── schemas.py
│   │       └── responses.py
│   ├── data/                # Raw data files
│   │   ├── pdfs/
│   │   └── excel/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # React/Next.js chat UI
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── ToolIndicator.tsx
│   │   │   └── ConfirmationDialog.tsx
│   │   ├── hooks/
│   │   └── pages/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── ARCHITECTURE.md
├── PRODUCT_NOTE.md
└── README.md
```

### Step 0.2: Choose Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **LLM** | OpenAI GPT-4o / GPT-4o-mini | Best function-calling support, reliable tool use |
| **Agent Framework** | LangChain / LangGraph | Multi-step orchestration, tool routing, state machines |
| **Vector DB** | ChromaDB (local) or Pinecone (hosted) | Document retrieval via embeddings |
| **Embeddings** | OpenAI `text-embedding-3-small` | Cost-effective, high quality |
| **Structured Data** | SQLite or DuckDB | Query Excel data with SQL |
| **Backend API** | FastAPI (Python) | Async, streaming, Pydantic validation |
| **Frontend** | Next.js + Tailwind | Modern React chat UI |
| **Hosting** | Vercel (frontend) + Railway/Render (backend) | Free tier friendly |

### Step 0.3: Install Dependencies

```bash
# Backend
pip install fastapi uvicorn langchain langchain-openai chromadb
pip install openpyxl pandas pydantic python-dotenv
pip install pypdf tiktoken sqlalchemy duckdb

# Frontend
npx -y create-next-app@latest frontend --typescript --tailwind --app --eslint
cd frontend && npm install
```

---

## Phase 1 — Data Ingestion Pipeline

### Step 1.1: Ingest PDF Documents

Each PDF must be:
1. **Parsed** into text chunks
2. **Tagged with metadata** (document name, version, freshness, authority level)
3. **Embedded** and stored in a vector database

```python
# backend/app/data/ingest_documents.py

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

DOCUMENT_METADATA = {
    "01_Support_Policy_v3_CURRENT.pdf": {
        "doc_type": "policy",
        "version": "v3",
        "status": "CURRENT",
        "authority": "high",        # Current policy = high authority
        "freshness": "current",
    },
    "02_Support_Policy_v2_DEPRECATED.pdf": {
        "doc_type": "policy",
        "version": "v2",
        "status": "DEPRECATED",
        "authority": "low",         # Deprecated = low authority
        "freshness": "outdated",
    },
    "03_Cancellation_and_Service_Credit_SOP_v4.pdf": {
        "doc_type": "sop",
        "version": "v4",
        "status": "CURRENT",
        "authority": "high",
    },
    "04_Product_Operations_Guide_and_Known_Issues.pdf": {
        "doc_type": "operations_guide",
        "status": "CURRENT",
        "authority": "medium",
    },
    "05_Northstar_Logistics_Enterprise_Agreement.pdf": {
        "doc_type": "customer_agreement",
        "customer": "Northstar Logistics",
        "authority": "highest",     # Customer agreements OVERRIDE general policy
    },
    "06_LumenWorks_Service_Agreement.pdf": {
        "doc_type": "customer_agreement",
        "customer": "LumenWorks",
        "authority": "highest",
    },
}

def ingest_all_documents(pdf_dir: str, persist_dir: str):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " "]
    )
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    all_docs = []
    for filename, meta in DOCUMENT_METADATA.items():
        loader = PyPDFLoader(f"{pdf_dir}/{filename}")
        pages = loader.load()
        chunks = splitter.split_documents(pages)
        for chunk in chunks:
            chunk.metadata.update(meta)
            chunk.metadata["source_file"] = filename
        all_docs.extend(chunks)
    
    vectorstore = Chroma.from_documents(
        documents=all_docs,
        embedding=embeddings,
        persist_directory=persist_dir,
        collection_name="parcelpilot_docs"
    )
    return vectorstore
```

> [!IMPORTANT]
> **Source Reliability Hierarchy** (critical for trust):
> 1. **Customer-specific agreements** → override everything for that customer
> 2. **CURRENT policies & SOPs** → general truth
> 3. **Operations guides** → supplementary context
> 4. **DEPRECATED documents** → context only, flag if used
> 5. **Historical ticket resolutions** → lowest authority, may be wrong

### Step 1.2: Ingest Excel Structured Data

Load the Excel workbook into a queryable database (SQLite/DuckDB).

```python
# backend/app/data/ingest_excel.py

import pandas as pd
import duckdb

def ingest_excel_to_db(excel_path: str, db_path: str):
    xls = pd.ExcelFile(excel_path)
    
    # Read the README sheet first for snapshot time
    readme = pd.read_excel(xls, sheet_name="README")
    
    con = duckdb.connect(db_path)
    
    for sheet_name in xls.sheet_names:
        if sheet_name == "README":
            continue
        df = pd.read_excel(xls, sheet_name=sheet_name)
        table_name = sheet_name.lower().replace(" ", "_")
        con.execute(f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM df")
        print(f"Loaded {len(df)} rows into table: {table_name}")
    
    con.close()
    return db_path
```

> [!TIP]
> Expected tables from the Excel: `accounts`, `orders`, `tickets` (possibly more). Inspect all sheets.

---

## Phase 2 — Access Control & Authentication

### Step 2.1: Define User Roles & Mock Auth

```python
# backend/app/auth/models.py

from pydantic import BaseModel
from enum import Enum
from typing import Optional

class UserRole(str, Enum):
    CUSTOMER = "customer"           # Can only see own account data
    SUPPORT_AGENT = "support_agent" # Can see all data, read-only
    OPERATIONS = "operations"       # Can see all data + take actions

class User(BaseModel):
    user_id: str
    name: str
    role: UserRole
    account_id: Optional[str] = None  # Set for customer users

# Mock users for demonstration
MOCK_USERS = {
    "northstar_user": User(
        user_id="northstar_user",
        name="Alex (Northstar Logistics)",
        role=UserRole.CUSTOMER,
        account_id="ACC-001"  # Northstar's account ID
    ),
    "lumenworks_user": User(
        user_id="lumenworks_user",
        name="Jordan (LumenWorks)",
        role=UserRole.CUSTOMER,
        account_id="ACC-002"
    ),
    "support_agent": User(
        user_id="support_agent",
        name="Sam (ParcelPilot Support)",
        role=UserRole.SUPPORT_AGENT,
        account_id=None
    ),
    "ops_manager": User(
        user_id="ops_manager",
        name="Taylor (ParcelPilot Ops)",
        role=UserRole.OPERATIONS,
        account_id=None
    ),
}
```

### Step 2.2: Enforce Access at the Data Layer

> [!CAUTION]
> Access control **MUST** be enforced at the tool/data layer, NOT in prompts. The assessment explicitly states this.

```python
# backend/app/auth/middleware.py

def get_data_filter(user: User) -> dict:
    """Returns SQL WHERE clause / filter dict based on user role."""
    if user.role == UserRole.CUSTOMER:
        return {"account_id": user.account_id}  # Only their data
    elif user.role == UserRole.SUPPORT_AGENT:
        return {}  # All data, read-only
    elif user.role == UserRole.OPERATIONS:
        return {}  # All data + write access
    return {"account_id": "__NONE__"}  # Deny by default

def can_take_actions(user: User) -> bool:
    return user.role in [UserRole.OPERATIONS, UserRole.SUPPORT_AGENT]

def get_document_filter(user: User) -> dict:
    """Filter documents by user context."""
    if user.role == UserRole.CUSTOMER:
        # Customers see: general policies + their own agreement
        return {
            "allowed_doc_types": ["policy", "sop"],
            "customer_agreement": user.account_id,
        }
    return {}  # Internal users see everything
```

---

## Phase 3 — Agent Tools (Minimum 3 Required)

### Tool 1: Document Search & Retrieval

```python
# backend/app/agent/tools/document_search.py

from langchain.tools import tool
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

@tool
def search_documents(query: str, user_account_id: str = None) -> str:
    """
    Search ParcelPilot's policy documents, SOPs, product guides,
    and customer agreements. Returns relevant excerpts with source
    attribution and authority level.
    
    Args:
        query: Natural language search query
        user_account_id: If customer, filters to their agreement only
    """
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = Chroma(
        persist_directory="./chroma_db",
        embedding_function=embeddings,
        collection_name="parcelpilot_docs"
    )
    
    # Build metadata filter
    filter_dict = {}
    if user_account_id:
        # Customer: only general docs + their own agreement
        filter_dict = {
            "$or": [
                {"doc_type": {"$in": ["policy", "sop", "operations_guide"]}},
                {"customer": user_account_id}
            ]
        }
    
    results = vectorstore.similarity_search_with_score(
        query, k=5, filter=filter_dict if filter_dict else None
    )
    
    # Format results with source reliability
    formatted = []
    for doc, score in results:
        reliability = _get_reliability_label(doc.metadata)
        formatted.append(
            f"[Source: {doc.metadata['source_file']} | "
            f"Authority: {doc.metadata.get('authority', 'unknown')} | "
            f"Status: {doc.metadata.get('status', 'N/A')} | "
            f"Reliability: {reliability}]\n{doc.page_content}"
        )
    
    return "\n\n---\n\n".join(formatted) if formatted else "No relevant documents found."

def _get_reliability_label(metadata: dict) -> str:
    if metadata.get("status") == "DEPRECATED":
        return "⚠️ DEPRECATED — use as context only, do NOT cite as current policy"
    if metadata.get("authority") == "highest":
        return "✅ CUSTOMER AGREEMENT — overrides general policy for this customer"
    if metadata.get("authority") == "high":
        return "✅ CURRENT — authoritative source"
    return "ℹ️ SUPPLEMENTARY"
```

### Tool 2: Structured Data Lookup & Calculation

```python
# backend/app/agent/tools/data_lookup.py

import duckdb
from langchain.tools import tool

@tool
def query_structured_data(
    query_type: str,
    parameters: dict,
    user_account_id: str = None
) -> str:
    """
    Query ParcelPilot's operational data (accounts, orders, tickets).
    
    Args:
        query_type: One of 'order_lookup', 'account_info', 'ticket_search',
                    'order_stats', 'ticket_stats', 'credit_calculation'
        parameters: Dict with query-specific params, e.g. {"order_id": "ORD-1001"}
        user_account_id: If customer, results are filtered to this account only
    """
    con = duckdb.connect("./parcelpilot.duckdb", read_only=True)
    
    try:
        if query_type == "order_lookup":
            order_id = parameters.get("order_id")
            sql = f"SELECT * FROM orders WHERE order_id = '{order_id}'"
            if user_account_id:
                sql += f" AND account_id = '{user_account_id}'"
            result = con.execute(sql).fetchdf()
            
        elif query_type == "account_info":
            account_id = parameters.get("account_id", user_account_id)
            if user_account_id and account_id != user_account_id:
                return "ACCESS DENIED: You can only view your own account."
            sql = f"SELECT * FROM accounts WHERE account_id = '{account_id}'"
            result = con.execute(sql).fetchdf()
            
        elif query_type == "ticket_search":
            filters = []
            if user_account_id:
                filters.append(f"account_id = '{user_account_id}'")
            if parameters.get("status"):
                filters.append(f"status = '{parameters['status']}'")
            if parameters.get("severity"):
                filters.append(f"severity = '{parameters['severity']}'")
            where = " AND ".join(filters) if filters else "1=1"
            sql = f"SELECT * FROM tickets WHERE {where} ORDER BY created_at DESC LIMIT 20"
            result = con.execute(sql).fetchdf()
        
        elif query_type == "credit_calculation":
            # Calculate service credits based on order data + policy rules
            order_id = parameters.get("order_id")
            sql = f"SELECT * FROM orders WHERE order_id = '{order_id}'"
            if user_account_id:
                sql += f" AND account_id = '{user_account_id}'"
            result = con.execute(sql).fetchdf()
            # Return raw data — the LLM applies policy rules from document search
            
        else:
            return f"Unknown query type: {query_type}"
        
        if result.empty:
            return "No records found matching your query."
        return result.to_string(index=False)
        
    finally:
        con.close()
```

> [!WARNING]
> In production, use parameterised queries to prevent SQL injection. The above is simplified for the assessment.

### Tool 3: State-Changing Actions (with Confirmation)

```python
# backend/app/agent/tools/actions.py

from langchain.tools import tool
from datetime import datetime
import json

# In-memory action log (mocked)
ACTION_LOG = []

@tool
def prepare_action(
    action_type: str,
    details: dict,
    requires_confirmation: bool = True
) -> str:
    """
    Prepare a state-changing action for user confirmation.
    The action is NOT executed until the user explicitly confirms.
    
    Args:
        action_type: One of 'escalate_ticket', 'update_ticket_status',
                     'create_followup_task', 'apply_service_credit'
        details: Action-specific details
        requires_confirmation: Always True for state-changing actions
    """
    action = {
        "action_id": f"ACT-{len(ACTION_LOG) + 1:04d}",
        "action_type": action_type,
        "details": details,
        "status": "PENDING_CONFIRMATION",
        "prepared_at": datetime.now().isoformat(),
    }
    
    ACTION_LOG.append(action)
    
    # Format confirmation message
    if action_type == "escalate_ticket":
        summary = (
            f"📋 **Escalation Prepared**\n"
            f"- Ticket: {details.get('ticket_id', 'N/A')}\n"
            f"- Reason: {details.get('reason', 'N/A')}\n"
            f"- Priority: {details.get('priority', 'Normal')}\n\n"
            f"⚠️ **Please confirm to proceed with this escalation.**"
        )
    elif action_type == "update_ticket_status":
        summary = (
            f"📋 **Ticket Update Prepared**\n"
            f"- Ticket: {details.get('ticket_id', 'N/A')}\n"
            f"- New Status: {details.get('new_status', 'N/A')}\n"
            f"- Note: {details.get('note', 'N/A')}\n\n"
            f"⚠️ **Please confirm to apply this update.**"
        )
    elif action_type == "create_followup_task":
        summary = (
            f"📋 **Follow-up Task Prepared**\n"
            f"- Related Ticket: {details.get('ticket_id', 'N/A')}\n"
            f"- Task: {details.get('description', 'N/A')}\n"
            f"- Assigned To: {details.get('assigned_to', 'Unassigned')}\n\n"
            f"⚠️ **Please confirm to create this task.**"
        )
    else:
        summary = f"Action prepared: {json.dumps(action, indent=2)}\n\n⚠️ **Please confirm.**"
    
    return summary


@tool
def confirm_action(action_id: str) -> str:
    """Execute a previously prepared action after user confirmation."""
    for action in ACTION_LOG:
        if action["action_id"] == action_id:
            if action["status"] != "PENDING_CONFIRMATION":
                return f"Action {action_id} is already {action['status']}."
            action["status"] = "EXECUTED"
            action["executed_at"] = datetime.now().isoformat()
            return f"✅ Action {action_id} ({action['action_type']}) has been executed successfully."
    return f"Action {action_id} not found."
```

---

## Phase 4 — Agent Orchestration

### Step 4.1: Build the Agent with LangGraph

```python
# backend/app/agent/orchestrator.py

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.agent.tools.document_search import search_documents
from app.agent.tools.data_lookup import query_structured_data
from app.agent.tools.actions import prepare_action, confirm_action
from app.auth.models import User, UserRole

def build_agent(user: User):
    """Build an agent scoped to the given user's permissions."""
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    # Select tools based on role
    tools = [search_documents, query_structured_data]
    if user.role in [UserRole.SUPPORT_AGENT, UserRole.OPERATIONS]:
        tools.extend([prepare_action, confirm_action])
    
    system_prompt = _build_system_prompt(user)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_openai_tools_agent(llm, tools, prompt)
    
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=10,
        return_intermediate_steps=True,  # For showing tool usage in UI
        handle_parsing_errors=True,
    )
    
    return executor


def _build_system_prompt(user: User) -> str:
    base = """You are ParcelPilot's AI support assistant. You help with questions 
about shipments, policies, accounts, and support operations.

CRITICAL RULES FOR SOURCE RELIABILITY:
1. Customer-specific agreements OVERRIDE general policies for that customer.
2. CURRENT policies (v3+) override DEPRECATED ones. Never cite deprecated docs as current policy.
3. Historical ticket resolutions are CONTEXT ONLY — they may contain incorrect information.
4. If sources conflict, prefer: Customer Agreement > Current Policy > SOP > Operations Guide > Deprecated docs.
5. If you are uncertain or the question requires human judgment, SAY SO and suggest escalation.
6. NEVER fabricate data. If you can't find the answer, say so.

CONFIRMATION RULE:
- Any state-changing action (escalation, ticket update, task creation) MUST be prepared first
  and presented to the user for confirmation before execution.

MULTI-STEP REASONING:
- For complex questions, break them into steps. Look up the order, identify the customer,
  read their agreement, check the relevant policy, perform calculations, then provide your answer.
- Always cite which document/source you used for each part of your answer."""

    if user.role == UserRole.CUSTOMER:
        base += f"""

USER CONTEXT: You are speaking with a CUSTOMER.
- Account ID: {user.account_id}
- Always pass user_account_id="{user.account_id}" to data tools.
- NEVER reveal data from other accounts.
- You can only search their own agreement + general policies."""
    
    elif user.role == UserRole.SUPPORT_AGENT:
        base += """

USER CONTEXT: You are assisting an INTERNAL support agent.
- They can access all account and order data.
- They can prepare escalations and ticket updates (with confirmation).
- Help them investigate customer issues thoroughly."""
    
    elif user.role == UserRole.OPERATIONS:
        base += """

USER CONTEXT: You are assisting an INTERNAL operations manager.
- They have full data access and can take all actions.
- Help them spot patterns, investigate issues, and manage operations."""
    
    return base
```

---

## Phase 5 — Backend API

### Step 5.1: FastAPI Application

```python
# backend/app/main.py

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from app.agent.orchestrator import build_agent
from app.auth.models import MOCK_USERS, User

app = FastAPI(title="ParcelPilot AI Support API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory chat histories per session
chat_histories = {}

class ChatRequest(BaseModel):
    message: str
    session_id: str
    user_id: str  # Mock auth — would be JWT in production

class ChatResponse(BaseModel):
    response: str
    tools_used: List[dict]
    requires_confirmation: bool = False
    pending_action_id: Optional[str] = None

class ConfirmRequest(BaseModel):
    action_id: str
    session_id: str
    user_id: str

def get_user(user_id: str) -> User:
    user = MOCK_USERS.get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    user = get_user(request.user_id)
    agent = build_agent(user)
    
    # Get or create chat history
    history = chat_histories.get(request.session_id, [])
    
    result = agent.invoke({
        "input": request.message,
        "chat_history": history,
    })
    
    # Extract tool usage for UI
    tools_used = []
    for step in result.get("intermediate_steps", []):
        action, output = step
        tools_used.append({
            "tool": action.tool,
            "input": str(action.tool_input)[:200],
            "output": str(output)[:500],
        })
    
    # Update chat history
    from langchain_core.messages import HumanMessage, AIMessage
    history.append(HumanMessage(content=request.message))
    history.append(AIMessage(content=result["output"]))
    chat_histories[request.session_id] = history
    
    # Check if response contains a pending action
    requires_confirmation = "Please confirm" in result["output"]
    
    return ChatResponse(
        response=result["output"],
        tools_used=tools_used,
        requires_confirmation=requires_confirmation,
    )

@app.get("/api/users")
async def list_users():
    """List available mock users for the demo."""
    return [
        {"id": uid, "name": u.name, "role": u.role.value}
        for uid, u in MOCK_USERS.items()
    ]

@app.get("/api/health")
async def health():
    return {"status": "healthy"}
```

---

## Phase 6 — Frontend Chat UI

### Step 6.1: Chat Interface Components

Build a Next.js chat interface that:
- Allows user/role switching (for demo)
- Shows messages in a conversation thread
- Displays a **tool indicator** showing which tools are being used
- Shows a **confirmation dialog** for state-changing actions

Key components:

| Component | Purpose |
|---|---|
| `ChatWindow.tsx` | Main chat container with message list + input |
| `MessageBubble.tsx` | Individual message with markdown rendering |
| `ToolIndicator.tsx` | Shows active tool name + brief input/output |
| `ConfirmationDialog.tsx` | Modal for confirming state-changing actions |
| `UserSwitcher.tsx` | Dropdown to switch between mock users |

### Step 6.2: Core Chat Logic

```typescript
// frontend/src/hooks/useChat.ts

interface Message {
  role: "user" | "assistant";
  content: string;
  tools_used?: ToolUsage[];
  requires_confirmation?: boolean;
}

interface ToolUsage {
  tool: string;
  input: string;
  output: string;
}

export function useChat(userId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const sessionId = useRef(crypto.randomUUID());

  const sendMessage = async (content: string) => {
    setMessages(prev => [...prev, { role: "user", content }]);
    setIsLoading(true);

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: content,
        session_id: sessionId.current,
        user_id: userId,
      }),
    });

    const data = await res.json();
    setMessages(prev => [
      ...prev,
      {
        role: "assistant",
        content: data.response,
        tools_used: data.tools_used,
        requires_confirmation: data.requires_confirmation,
      },
    ]);
    setIsLoading(false);
  };

  return { messages, sendMessage, isLoading };
}
```

---

## Phase 7 — Trust & Reliability (Problem 2)

### Step 7.1: Source Conflict Resolution Logic

Embed this into the agent's reasoning pipeline:

```python
# backend/app/agent/reliability.py

AUTHORITY_HIERARCHY = {
    "highest": 5,  # Customer agreements
    "high": 4,     # Current policies & SOPs
    "medium": 3,   # Operations guides
    "low": 1,      # Deprecated docs
}

def resolve_conflicts(retrieved_docs: list) -> dict:
    """
    When multiple documents provide conflicting information,
    return the resolution with explanation.
    """
    # Group by topic / question relevance
    # Rank by authority score
    # If customer agreement exists → it wins
    # If only DEPRECATED source matches → flag with warning
    # If no source matches confidently → recommend escalation
    
    sorted_docs = sorted(
        retrieved_docs,
        key=lambda d: AUTHORITY_HIERARCHY.get(d.metadata.get("authority", "low"), 0),
        reverse=True
    )
    
    winner = sorted_docs[0] if sorted_docs else None
    conflicts = []
    
    for doc in sorted_docs[1:]:
        if doc.metadata.get("authority") != winner.metadata.get("authority"):
            conflicts.append({
                "lower_source": doc.metadata["source_file"],
                "reason": f"Overridden by higher-authority source: {winner.metadata['source_file']}"
            })
    
    return {
        "primary_source": winner,
        "conflicts": conflicts,
        "confidence": "high" if winner and winner.metadata.get("authority") in ["highest", "high"] else "medium",
    }
```

### Step 7.2: Uncertainty Detection & Escalation

Add rules to the agent prompt and post-processing:

- If confidence is below a threshold → append "I'm not fully certain. Consider verifying with the team."
- If the only matching source is DEPRECATED → explicitly warn
- If the query involves exceptions, custom terms, or financial amounts above a threshold → recommend human review

---

## Phase 8 — Proactive Issue Detection (Problem 1)

### Step 8.1: Analytics Dashboard Queries

Build agent tools or a separate dashboard view for internal users:

```python
@tool
def detect_proactive_issues() -> str:
    """
    Scan ticket and order data for recurring, urgent, or unusual patterns.
    Returns a summary of issues requiring attention.
    """
    con = duckdb.connect("./parcelpilot.duckdb", read_only=True)
    
    analyses = []
    
    # 1. Tickets approaching/exceeding SLA
    sla_breaches = con.execute("""
        SELECT ticket_id, account_id, severity, created_at, 
               CURRENT_TIMESTAMP - created_at as age
        FROM tickets 
        WHERE status NOT IN ('Resolved', 'Closed')
        ORDER BY severity ASC, created_at ASC
        LIMIT 10
    """).fetchdf()
    
    # 2. Recurring issues (same category, multiple customers)
    recurring = con.execute("""
        SELECT category, COUNT(*) as count, 
               COUNT(DISTINCT account_id) as affected_accounts
        FROM tickets
        WHERE status != 'Closed'
        GROUP BY category
        HAVING COUNT(*) > 2
        ORDER BY count DESC
    """).fetchdf()
    
    # 3. High severity open tickets
    critical = con.execute("""
        SELECT * FROM tickets
        WHERE severity IN ('Critical', 'High')
        AND status NOT IN ('Resolved', 'Closed')
    """).fetchdf()
    
    con.close()
    
    return format_proactive_report(sla_breaches, recurring, critical)
```

---

## Phase 9 — Deployment & Hosting

### Step 9.1: Docker Setup

```yaml
# docker-compose.yml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./backend/data:/app/data
  
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend
```

### Step 9.2: Deployment Options

| Platform | Backend | Frontend | Free Tier? |
|---|---|---|---|
| **Railway** | ✅ FastAPI container | ❌ | Yes (limited) |
| **Render** | ✅ FastAPI container | ✅ Static site | Yes |
| **Vercel** | ❌ (use for frontend only) | ✅ Next.js | Yes |
| **Fly.io** | ✅ Docker | ✅ Docker | Yes (limited) |
| **Recommended** | Railway or Render | Vercel | — |

---

## Phase 10 — Submission Deliverables

### Checklist

| # | Deliverable | Status |
|---|---|---|
| 1 | **Public GitHub Repo** with clear README | ☐ |
| 2 | **Hosted Application** URL | ☐ |
| 3 | **Demo Video** (~5 min): architecture + demo + decisions | ☐ |
| 4 | **Architecture Note** (`ARCHITECTURE.md`) | ☐ |
| 5 | **Product Note** (`PRODUCT_NOTE.md`) | ☐ |
| 6 | **AI Tool Usage** statement | ☐ |
| 7 | **Google Form** submission | ☐ |

### Architecture Note Outline (`ARCHITECTURE.md`)

```markdown
# Architecture Note

## Agent Design
- LangChain agent with OpenAI function calling
- Role-based system prompt injection
- Multi-step reasoning with intermediate step tracking

## Tool Design
- Document Search (ChromaDB vector retrieval with metadata filtering)
- Structured Data Lookup (DuckDB SQL queries with account-scoped filters)
- State-Changing Actions (prepare → confirm → execute pattern)

## Document & Data Handling
- PDFs chunked with RecursiveCharacterTextSplitter (1000 chars, 200 overlap)
- Metadata-enriched embeddings with authority/freshness tags
- Excel data loaded into DuckDB for SQL-based querying

## Source Reliability & Conflict Handling
- 5-tier authority hierarchy
- Customer agreements override general policy
- Deprecated sources flagged with warnings
- Uncertainty detection triggers escalation recommendations

## Trade-offs
- ChromaDB (local) vs Pinecone (hosted) — chose local for simplicity
- Mock auth vs JWT — mock for assessment, production-ready pattern shown
- DuckDB vs PostgreSQL — DuckDB for zero-config, in-process analytics
```

### Product Note Outline (`PRODUCT_NOTE.md`)

```markdown
# Product Note

## Additional Problem Addressed
Problem 2: Trust & Reliability
- Source authority hierarchy ensures customer agreements override general policies
- Deprecated document detection prevents citing outdated information
- Confidence scoring triggers escalation recommendations
- Historical tickets treated as context only with explicit warnings

## What I Would Build Next
1. Real-time webhook integration for live ticket/order updates
2. Feedback loop: support agents rate AI answers to fine-tune retrieval
3. Multi-language support for international customers
4. Automated SLA monitoring with Slack/email alerts
5. RAG evaluation pipeline (RAGAS) for continuous quality measurement

## What I Intentionally Left Out
- Production authentication (JWT/OAuth) — mocked for assessment
- Streaming responses — would add for production UX
- Persistent chat history (database-backed)
- Rate limiting and abuse prevention

## Key Metric
**First-contact resolution rate via AI**: Percentage of support requests
fully resolved by the AI without human escalation. Target: 60-70%.
```

---

## Quick Reference — Example Test Queries

Use these to validate your implementation:

| Query | Expected Behaviour |
|---|---|
| *"Can Northstar cancel ORD-1001 without a cancellation fee?"* | Multi-step: lookup order → find Northstar's agreement → check cancellation policy → compare → answer with citation |
| *"A pickup is three hours late because of carrier fault. Should I get a service credit?"* | Search SOP for credit policy → check carrier-fault rules → calculate eligibility |
| *"Show me all open high-severity tickets"* | Structured data query → filter by severity + status |
| *"Escalate ticket TKT-XXX to engineering"* | Prepare action → show confirmation → wait for user OK → execute |
| *"What's LumenWorks' SLA for critical issues?"* (asked by Northstar user) | Access control: should NOT reveal LumenWorks data to Northstar user |

---

> [!IMPORTANT]
> **Key Differentiators That Will Make Your Submission Stand Out:**
> 1. **Source reliability handling** — don't just retrieve, reason about trust
> 2. **Data-layer access control** — not just prompt instructions
> 3. **Clean tool indicator UI** — show the user what's happening step by step
> 4. **Thoughtful product note** — show you think like a product engineer, not just a coder
> 5. **Hosted & working** — a live demo URL dramatically improves your submission
