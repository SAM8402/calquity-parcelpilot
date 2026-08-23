import sys
import re
import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.orchestrator import build_agent
from app.auth.models import MOCK_USERS, User
from app.models.schemas import ChatRequest, ChatResponse, ConfirmRequest, UserResponse
from app.config import CORS_ORIGINS, DB_PATH, CHROMA_DIR, GEMINI_MODEL
from app.services.cache_service import cache_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini tool schema conversion drops JSON-Schema keys LangChain emits
# (title / anyOf / default). Harmless — silence the spam on Render.
logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle events."""
    logger.info("=" * 60)
    logger.info("ParcelPilot AI Support Agent - Starting")
    logger.info("=" * 60)
    logger.info(f"Model: {GEMINI_MODEL}")
    logger.info(f"DuckDB: {'Found' if DB_PATH.exists() else 'Missing — run setup_db.py'}")
    logger.info(f"ChromaDB: {'Found' if CHROMA_DIR.exists() else 'Missing — run ingest_documents.py'}")
    logger.info(f"Mock users: {list(MOCK_USERS.keys())}")
    redis_ok = cache_service.connect()
    logger.info(
        "Cache: %s (backend=%s)",
        "ready" if redis_ok else "unavailable",
        cache_service.backend,
    )
    try:
        from app.data.embeddings import get_embeddings, read_active_backend

        _, emb_backend = get_embeddings()
        logger.info(
            "Embeddings: active=%s stored=%s",
            emb_backend,
            read_active_backend() or "none",
        )
    except Exception as e:
        logger.warning("Embeddings not ready yet: %s", e)
    yield
    cache_service.disconnect()
    logger.info("ParcelPilot AI Support Agent - Shutting down")


app = FastAPI(
    title="ParcelPilot AI Support API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    # Wildcard origin cannot be combined with credentials (Starlette rule)
    allow_credentials="*" not in CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    """Log request duration for observability."""
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    if request.url.path.startswith("/api/"):
        logger.info(f"{request.method} {request.url.path} — {duration:.2f}s")
    return response


# In-memory chat histories per user+session (prevents cross-user bleed)
chat_histories: dict[str, list] = {}
# Reuse agents per user (LLM bind_tools is expensive); always refresh ACL context
_agent_cache: dict[str, object] = {}


def _history_key(user_id: str, session_id: str) -> str:
    return f"{user_id}::{session_id}"


def _get_agent(user: User):
    from app.auth.context import set_current_user

    agent = _agent_cache.get(user.user_id)
    if agent is None:
        agent = build_agent(user)
        _agent_cache[user.user_id] = agent
    else:
        set_current_user(user)
    return agent


def get_user(user_id: str) -> User:
    user = MOCK_USERS.get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail=f"Unknown user: {user_id}")
    return user


def _invoke_agent(agent, message: str, history: list) -> dict:
    """Invoke agent with retries for known Gemini tool-call glitches."""
    last_err: Exception | None = None
    attempts = [
        history,
        history,
        [],  # last resort: no prior messages (avoids bad tool_response leftovers)
    ]
    for i, hist in enumerate(attempts):
        try:
            return agent.invoke({
                "input": message,
                "chat_history": hist,
            })
        except Exception as e:
            last_err = e
            err = str(e)
            if "function_response.name" in err or "Name cannot be empty" in err:
                logger.warning(
                    "Gemini tool-name glitch (attempt %d/%d): %s",
                    i + 1,
                    len(attempts),
                    e,
                )
                continue
            raise
    assert last_err is not None
    raise last_err


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    user = get_user(request.user_id)
    history_key = _history_key(request.user_id, request.session_id)
    history = chat_histories.get(history_key, [])

    # Cache only fresh-session FAQ-style turns (no prior context)
    use_cache = len(history) == 0
    if use_cache:
        cached = cache_service.get_chat(
            user.user_id, user.role.value, user.account_id, request.message
        )
        if isinstance(cached, dict) and cached.get("response"):
            history.append(HumanMessage(content=request.message))
            history.append(AIMessage(content=cached["response"]))
            chat_histories[history_key] = history
            return ChatResponse(
                response=cached["response"],
                tools_used=cached.get("tools_used") or [],
                requires_confirmation=False,
                pending_action_id=None,
                from_cache=True,
            )

    agent = _get_agent(user)

    try:
        result = _invoke_agent(agent, request.message, history)
    except Exception as e:
        logger.error(f"Agent error for user {request.user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    tools_used = []
    for step in result.get("intermediate_steps", []):
        action, output = step
        tools_used.append({
            "tool": action.tool,
            "input": str(action.tool_input)[:200],
            "output": str(output)[:500],
        })

    history.append(HumanMessage(content=request.message))
    history.append(AIMessage(content=result["output"]))
    chat_histories[history_key] = history

    requires_confirmation = "Please confirm" in result["output"]
    pending_action_id = None
    if requires_confirmation:
        for tool_step in tools_used:
            match = re.search(r"ACT-\d{4}", tool_step.get("output", ""))
            if match:
                pending_action_id = match.group(0)
                break

    payload = {
        "response": result["output"],
        "tools_used": tools_used,
        "requires_confirmation": requires_confirmation,
        "pending_action_id": pending_action_id,
    }

    if use_cache and not requires_confirmation:
        cache_service.set_chat(
            user.user_id, user.role.value, user.account_id, request.message, payload
        )

    return ChatResponse(**payload, from_cache=False)


@app.post("/api/confirm", response_model=ChatResponse)
async def confirm(request: ConfirmRequest):
    user = get_user(request.user_id)
    from app.auth.middleware import can_take_actions
    from app.agent.tools.actions import execute_confirmed_action

    if not can_take_actions(user):
        raise HTTPException(
            status_code=403,
            detail="Only support/operations users can confirm actions.",
        )

    logger.info(f"Confirming action {request.action_id} by {user.name}")
    result = execute_confirmed_action(request.action_id, user)

    if result.startswith("ACCESS DENIED"):
        raise HTTPException(status_code=403, detail=result)

    history = chat_histories.get(_history_key(request.user_id, request.session_id), [])
    history.append(HumanMessage(content=f"Confirm action {request.action_id}"))
    history.append(AIMessage(content=result))
    chat_histories[_history_key(request.user_id, request.session_id)] = history

    return ChatResponse(
        response=result,
        tools_used=[{"tool": "confirm_action", "input": request.action_id, "output": result}],
        requires_confirmation=False,
        from_cache=False,
    )


@app.post("/api/reset")
async def reset_session(session_id: str = "", user_id: str = ""):
    """Reset chat history for a session. Useful for demo purposes."""
    if user_id and session_id:
        key = _history_key(user_id, session_id)
        if key in chat_histories:
            del chat_histories[key]
            return {"status": "session_cleared", "session_id": session_id, "user_id": user_id}
    if session_id:
        keys = [k for k in chat_histories if k.endswith(f"::{session_id}") or k == session_id]
        for k in keys:
            del chat_histories[k]
        if keys:
            return {"status": "session_cleared", "session_id": session_id, "keys": len(keys)}
    return {"status": "no_session_found"}


@app.post("/api/cache/clear")
async def clear_cache(user_id: str = ""):
    """Clear Redis caches (support/ops only)."""
    user = get_user(user_id) if user_id else None
    from app.auth.middleware import can_take_actions

    if user is None or not can_take_actions(user):
        raise HTTPException(status_code=403, detail="Only support/operations can clear cache.")

    n = 0
    n += cache_service.delete_pattern("chat:*")
    n += cache_service.delete_pattern("docs:*")
    n += cache_service.delete_pattern("data:*")
    return {"status": "cleared", "keys_removed": n, "by": user.user_id}


@app.get("/api/users")
async def list_users():
    return [
        UserResponse(id=uid, name=u.name, role=u.role.value)
        for uid, u in MOCK_USERS.items()
    ]


@app.get("/api/health")
async def health():
    from app.data.embeddings import read_active_backend

    return {
        "status": "healthy",
        "version": "1.0.0",
        "model": GEMINI_MODEL,
        "db_available": DB_PATH.exists(),
        "vectorstore_available": CHROMA_DIR.exists(),
        "redis_available": cache_service.available,
        "cache_backend": cache_service.backend,
        "embedding_backend": read_active_backend() or "unknown",
    }


def _register_static_ui(app: FastAPI, static_dir: Path) -> None:
    """Serve Next.js static export without shadowing /api/* routes.

    Mounting StaticFiles at ``/`` intercepts every path (including POST /api/chat)
    on production; use explicit asset mounts + GET-only SPA fallback instead.
    """
    if not static_dir.is_dir() or not (static_dir / "index.html").is_file():
        return

    next_dir = static_dir / "_next"
    if next_dir.is_dir():
        app.mount(
            "/_next",
            StaticFiles(directory=str(next_dir)),
            name="next_static",
        )

    for item in static_dir.iterdir():
        if item.name in {"_next", "index.html"}:
            continue
        if item.is_dir():
            app.mount(
                f"/{item.name}",
                StaticFiles(directory=str(item)),
                name=f"static_{item.name}",
            )

    @app.get("/")
    async def serve_index():
        return FileResponse(static_dir / "index.html")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="Not found")
        candidate = static_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        nested = static_dir / full_path / "index.html"
        if nested.is_file():
            return FileResponse(nested)
        return FileResponse(static_dir / "index.html")


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_register_static_ui(app, STATIC_DIR)
