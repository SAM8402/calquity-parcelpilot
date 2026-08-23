"""Gemini-compatible tool-calling agent (manual loop).

Avoids AgentExecutor/Gemini bugs where ToolMessage names can be empty.
Exposes the same `.invoke({input, chat_history})` shape used by main.py.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from app.agent.llm import get_llm
from app.agent.tools.document_search import search_documents
from app.agent.tools.data_lookup import query_structured_data
from app.agent.tools.actions import prepare_action, list_pending_actions
from app.agent.tools.proactive import detect_proactive_issues
from app.agent.prompts import build_system_prompt
from app.auth.models import User, UserRole
from app.auth.context import set_current_user

logger = logging.getLogger(__name__)


def _clean_content(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts)
    return str(content)


class ToolCallingAgent:
    """Minimal tool-calling agent with an AgentExecutor-compatible invoke()."""

    def __init__(self, llm, tools, system_prompt: str, max_iterations: int = 10):
        self.llm = llm.bind_tools(tools)
        self.tools = {t.name: t for t in tools}
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations

    def invoke(self, inputs: dict) -> dict:
        user_input = inputs.get("input", "")
        history = list(inputs.get("chat_history") or [])

        messages = [SystemMessage(content=self.system_prompt)]
        messages.extend(history)
        messages.append(HumanMessage(content=user_input))

        intermediate_steps = []

        for step_i in range(self.max_iterations):
            ai = self.llm.invoke(messages)
            tool_calls = getattr(ai, "tool_calls", None) or []

            # Normalize content for history
            text = _clean_content(getattr(ai, "content", ""))
            if not tool_calls:
                if text.strip():
                    return {
                        "output": text,
                        "intermediate_steps": intermediate_steps,
                    }
                # Model returned empty text after tools — force a final synthesis
                if intermediate_steps:
                    final = self.llm.invoke(
                        messages
                        + [
                            HumanMessage(
                                content=(
                                    "Using only the tool results above, write the final "
                                    "user-facing answer now. Do not call tools."
                                )
                            )
                        ]
                    )
                    return {
                        "output": _clean_content(getattr(final, "content", ""))
                        or "I gathered data but could not format a final answer. Please retry.",
                        "intermediate_steps": intermediate_steps,
                    }
                return {
                    "output": "I could not produce an answer.",
                    "intermediate_steps": intermediate_steps,
                }

            messages.append(ai)

            for tc in tool_calls:
                name = (tc.get("name") or "").strip()
                args = tc.get("args") or {}
                call_id = tc.get("id") or f"call_{step_i}_{name or 'unknown'}"

                if not name or name not in self.tools:
                    logger.warning("Skipping invalid tool call: %s", tc)
                    messages.append(
                        ToolMessage(
                            content=f"Unknown or empty tool name: {name!r}",
                            tool_call_id=call_id,
                            name=name or "unknown_tool",
                        )
                    )
                    continue

                try:
                    observation = self.tools[name].invoke(args)
                except Exception as e:
                    observation = f"Tool error ({name}): {e}"

                intermediate_steps.append(
                    (
                        SimpleNamespace(tool=name, tool_input=args),
                        observation,
                    )
                )
                messages.append(
                    ToolMessage(
                        content=str(observation),
                        tool_call_id=call_id,
                        name=name,
                    )
                )

        # Exhausted iterations — ask model for a final answer without tools
        final = self.llm.invoke(
            messages
            + [
                HumanMessage(
                    content=(
                        "Stop calling tools. Give your best final answer now "
                        "using the tool results already gathered."
                    )
                )
            ]
        )
        return {
            "output": _clean_content(getattr(final, "content", ""))
            or "Reached the tool-call limit before finishing.",
            "intermediate_steps": intermediate_steps,
        }


def build_agent(user: User) -> ToolCallingAgent:
    """Build an agent scoped to the given user's permissions."""
    set_current_user(user)
    llm = get_llm(temperature=0)

    tools = [search_documents, query_structured_data]

    if user.role in (UserRole.SUPPORT_AGENT, UserRole.OPERATIONS):
        # confirm_action is intentionally NOT an agent tool — execution only via /api/confirm
        tools.extend([prepare_action, list_pending_actions])

    if user.role == UserRole.OPERATIONS:
        tools.append(detect_proactive_issues)

    return ToolCallingAgent(
        llm=llm,
        tools=tools,
        system_prompt=build_system_prompt(user),
        max_iterations=10,
    )
