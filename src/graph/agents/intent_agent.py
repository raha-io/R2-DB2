"""Intent expert agent — classifies, extracts a structured spec, and clarifies.

This subgraph runs the user message through:
    classify → extract_spec → clarify_or_continue
                                    │
                                    ├─ ask_user (interrupt) → extract_spec
                                    └─ END

The agent shares the parent ``AnalyticalAgentState`` so its outputs flow
directly into downstream nodes (``context_retrieve``, ``plan``, etc.).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from graph.agents._json import parse_json_object
from graph.agents._llm import get_llm
from graph.state import AnalyticalAgentState

logger = logging.getLogger(__name__)

MAX_CLARIFICATION_ROUNDS = 2

_VALID_INTENTS = {"new_analysis", "follow_up", "clarification", "off_topic"}


def _last_user_message(state: AnalyticalAgentState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return ""
    return messages[-1].get("content", "") or ""


def _conversation_text(state: AnalyticalAgentState, limit: int = 6) -> str:
    """Render the last ``limit`` messages as a plain transcript."""
    messages = state.get("messages", [])[-limit:]
    lines = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "") or ""
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def classify(state: AnalyticalAgentState) -> dict[str, Any]:
    """Classify the user's message into one of four intent labels."""
    llm = get_llm()
    last_message = _last_user_message(state)
    if not last_message:
        return {
            "intent": "off_topic",
            "error": "No messages provided",
            "intent_clarification_rounds": 0,
            "sql_retry_count": 0,
            "graph_step_count": 0,
            "sql_validation_errors": [],
            "error_node": None,
        }

    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are an intent classifier. Classify the user's message into exactly one of these categories:\n"
                    "- new_analysis: User wants a new data analysis, report, or query\n"
                    "- follow_up: User is asking a follow-up question about a previous analysis\n"
                    "- clarification: User is asking for clarification about something\n"
                    "- off_topic: Message is not related to data analysis\n\n"
                    "Respond with ONLY the category name, nothing else."
                )
            ),
            HumanMessage(content=last_message),
        ]
    )

    intent = response.content.strip().lower()
    if intent not in _VALID_INTENTS:
        intent = "new_analysis"

    logger.info("Classified intent: %s", intent)
    return {
        "intent": intent,
        "intent_clarification_rounds": state.get("intent_clarification_rounds", 0),
        "sql_retry_count": 0,
        "graph_step_count": 0,
        "sql_validation_errors": [],
        "error": None,
        "error_node": None,
    }


def extract_spec(state: AnalyticalAgentState) -> dict[str, Any]:
    """Extract a structured intent spec from the conversation so far."""
    llm = get_llm()
    transcript = _conversation_text(state)

    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are an analytics intent extractor. Read the conversation and produce a "
                    "structured spec describing what the user wants to know. Respond with ONLY valid JSON "
                    "matching this schema:\n"
                    "{\n"
                    '  "metric": string | null,            // what is being measured (e.g. "total orders")\n'
                    '  "dimensions": [string],             // group-by dimensions\n'
                    '  "filters": [string],                // human-readable filters\n'
                    '  "time_range": string | null,        // resolved or relative time range\n'
                    '  "granularity": string | null,       // day/week/month/...\n'
                    '  "entities": [string],               // tables/columns the user named or implied\n'
                    '  "ambiguities": [string]             // REQUIRED missing info that blocks SQL generation\n'
                    "}\n"
                    "You MUST list ambiguities when any of the following are missing or unclear:\n"
                    "- metric: what exactly should be measured (e.g. revenue, count, average)?\n"
                    "- time_range: what time period? If not specified, this IS an ambiguity.\n"
                    "- filters: are there important constraints the user hasn't stated?\n"
                    "- dimensions: how should results be grouped?\n"
                    "- entities: which specific table/entity is the user referring to?\n\n"
                    "Vague questions like 'show me data', 'top customers', 'the numbers' MUST have ambiguities.\n"
                    "A question is only clear when it specifies WHAT metric, over WHAT time range, and HOW to group it.\n"
                    "If everything is genuinely clear and specific, return an empty list."
                )
            ),
            HumanMessage(content=f"Conversation:\n{transcript}"),
        ]
    )

    spec = parse_json_object(response.content)
    if spec is None:
        logger.warning(
            "Intent spec extraction returned non-JSON (first 200 chars): %r",
            (response.content or "")[:200],
        )
        spec = {
            "metric": None,
            "dimensions": [],
            "filters": [],
            "time_range": None,
            "granularity": None,
            "entities": [],
            "ambiguities": [],
        }

    spec.setdefault("ambiguities", [])

    # Deterministic guard (first round of a new_analysis only): when key
    # fields are missing, ask the LLM to phrase contextual questions grounded
    # in the user's actual query instead of using canned strings. Skip for
    # follow_ups — they inherit metric/time_range context from the prior turn.
    rounds = state.get("intent_clarification_rounds", 0)
    intent = state.get("intent")
    if rounds == 0 and intent == "new_analysis":
        missing_fields = [
            field for field in ("metric", "time_range") if not spec.get(field)
        ]
        if missing_fields:
            contextual = _phrase_missing_field_questions(
                llm, transcript, missing_fields
            )
            if contextual:
                spec["ambiguities"] = list(
                    dict.fromkeys(contextual + spec.get("ambiguities", []))
                )

    logger.info(
        "Intent spec extracted (metric=%s, ambiguities=%d)",
        spec.get("metric"),
        len(spec.get("ambiguities") or []),
    )
    return {"intent_spec": spec}


_FIELD_GUIDANCE = {
    "metric": "what exactly should be measured (e.g. revenue, order count, average order value)",
    "time_range": "what time period the analysis should cover (e.g. last 30 days, Q1 2024, all time)",
}


def _phrase_missing_field_questions(
    llm: Any, transcript: str, missing_fields: list[str]
) -> list[str]:
    """Ask the LLM to produce contextual clarification questions for each missing field."""
    field_hints = "\n".join(
        f"- {field}: {_FIELD_GUIDANCE[field]}" for field in missing_fields
    )

    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You write short, specific clarification questions for an analytics assistant. "
                    "For each listed field, produce ONE question that references the user's actual "
                    "request so the question feels tailored, not generic. Respond with ONLY valid JSON "
                    "matching this schema:\n"
                    '{ "questions": [string, ...] }\n'
                    "Return exactly one question per field, in the same order as the fields given. "
                    "Do not repeat the field name; just ask the question naturally."
                )
            ),
            HumanMessage(
                content=(
                    f"Conversation:\n{transcript}\n\n"
                    f"Missing fields to clarify:\n{field_hints}"
                )
            ),
        ]
    )

    payload = parse_json_object(response.content)
    questions = payload.get("questions") if payload else None
    if not isinstance(questions, list):
        logger.warning(
            "Contextual clarification phrasing failed (first 200 chars): %r",
            (response.content or "")[:200],
        )
        return []

    return [str(q).strip() for q in questions if str(q).strip()]


def ask_user(state: AnalyticalAgentState) -> dict[str, Any]:
    """Pause execution and ask the user to fill in missing details."""
    spec = state.get("intent_spec") or {}
    questions = spec.get("ambiguities") or []
    rounds = state.get("intent_clarification_rounds", 0)

    user_reply = interrupt(
        {
            "type": "clarification",
            "question": "I need a bit more detail to answer this accurately.",
            "ambiguities": questions,
            "instructions": "Resume with a string containing the additional details.",
        }
    )

    reply_text = user_reply if isinstance(user_reply, str) else json.dumps(user_reply)
    logger.info("Received clarification reply (round %d)", rounds + 1)

    return {
        "messages": [{"role": "user", "content": reply_text}],
        "intent_clarification_rounds": rounds + 1,
    }


def _route_after_classify(state: AnalyticalAgentState) -> str:
    intent = state.get("intent")
    if intent in ("off_topic", "clarification"):
        return "exit"
    return "extract_spec"


def _route_after_spec(state: AnalyticalAgentState) -> str:
    spec = state.get("intent_spec") or {}
    ambiguities = spec.get("ambiguities") or []
    rounds = state.get("intent_clarification_rounds", 0)

    if ambiguities and rounds < MAX_CLARIFICATION_ROUNDS:
        return "ask_user"
    if ambiguities:
        logger.info(
            "Clarification budget exhausted (%d rounds); proceeding with best-effort spec",
            rounds,
        )
    return "exit"


def build_intent_agent() -> Any:
    """Compile the intent expert subgraph."""
    builder = StateGraph(AnalyticalAgentState)

    builder.add_node("classify", classify)
    builder.add_node("extract_spec", extract_spec)
    builder.add_node("ask_user", ask_user)

    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        _route_after_classify,
        {"extract_spec": "extract_spec", "exit": END},
    )
    builder.add_conditional_edges(
        "extract_spec",
        _route_after_spec,
        {"ask_user": "ask_user", "exit": END},
    )
    builder.add_edge("ask_user", "extract_spec")

    return builder.compile()
