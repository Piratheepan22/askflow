# backend/app/agent.py
"""
AskFlow tool-calling agent.

Architecture
Search is handled in two layers:

1. PLANNING (outside the agent loop): a single, structured-output LLM call
   decides whether the user's question needs live web search and, if so,
   decomposes it into independent sub-queries. This runs BEFORE the
   tool-calling agent starts, so query decomposition doesn't depend on the
   agent choosing to batch correctly mid-reasoning.

2. RETRIEVAL: all planned sub-queries are executed in parallel and the
   combined results are injected directly into the agent's input. The
   agent's own `web_search` tool remains available as a fallback (with a
   code-enforced call budget) for anything still missing, but normal turns
   shouldn't need it.

This keeps the number of agent iterations low and predictable, independent
of how reliably the underlying model follows batching instructions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from langchain_groq import ChatGroq
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from tavily import TavilyClient

from app.database import SessionLocal
from app.models import Note
from app.config import settings
from app.rag import search_chunks

logger = logging.getLogger(__name__)

tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)

# Execution limits
MAX_ITERATIONS = 8           # tool-call/response cycles per turn
MAX_EXECUTION_TIME = 45      # seconds per turn
MAX_WEB_SEARCH_CALLS = 2     # fallback budget for the agent's own web_search tool
MAX_PLANNED_QUERIES = 4      # cap on sub-queries from the planning step
AGENT_RETRIES = 3
AGENT_RETRY_BACKOFF_SECONDS = 1.5


# Shared retrieval helper (used by both the planner pre-fetch and the
# agent-facing web_search tool, so there's one code path for Tavily calls)

async def _run_web_queries(queries: list[str]) -> str:
    async def run_one(query: str) -> str:
        try:
            response = await asyncio.to_thread(
                tavily_client.search, query, max_results=3
            )
            results = response.get("results", [])
            if not results:
                return f"[{query}]: No results found."
            body = "\n\n".join(
                f"{r['title']}\n{r['content'][:400]}\nSource: {r['url']}"
                for r in results
            )
            return f"[{query}]:\n{body}"
        except Exception as e:
            return f"[{query}]: Error searching — {e}"

    outcomes = await asyncio.gather(*(run_one(q) for q in queries))
    return "\n\n---\n\n".join(outcomes)


# Search planning — runs once, outside the agent loop

_SEARCH_PLANNER_SYSTEM_PROMPT = """You are a query planning module for a search agent.

Given a user's message, decide whether it needs a live web search to answer well
(current events, prices, scores, or anything that may have changed since training).

If yes, break it into 1-4 focused, independent sub-queries that together cover
every distinct piece of information needed (e.g. semifinal AND final results;
each side of a comparison). If no search is needed, return an empty list.

Respond with ONLY a JSON object — no markdown fences, no commentary — in exactly
this shape:
{"needs_search": true, "queries": ["...", "..."]}
"""


async def plan_search(message: str) -> list[str]:
    """Decide whether `message` needs web search and decompose it into
    sub-queries, in a single deterministic call outside the agent loop.

    Returns an empty list if no search is needed, or if planning fails —
    in the failure case the agent's own web_search tool is still available
    as a fallback, so this is safe to fail open."""
    try:
        response = await llm.ainvoke([
            ("system", _SEARCH_PLANNER_SYSTEM_PROMPT),
            ("human", message),
        ])
        match = re.search(r"\{.*\}", response.content.strip(), re.DOTALL)
        if not match:
            return []
        data = json.loads(match.group(0))
        if not data.get("needs_search"):
            return []
        queries = [
            q.strip() for q in data.get("queries", [])
            if isinstance(q, str) and q.strip()
        ]
        return queries[:MAX_PLANNED_QUERIES]
    except Exception as e:
        logger.warning("Search planning failed, deferring to agent tool: %s", e)
        return []


# Stateless tools

@tool
def get_current_time() -> str:
    """Return the current date and time. Use this if the user asks what time or date it is."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression, e.g. '2 + 2 * 5'."""
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        return "Error: only numbers and + - * / ( ) are allowed."
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"Error: {e}"


@tool
def save_note(text: str) -> str:
    """Save a short note to the database for the user."""
    db = SessionLocal()
    try:
        note = Note(text=text)
        db.add(note)
        db.commit()
        db.refresh(note)
        return f"Saved note #{note.id}: {text}"
    except Exception as e:
        db.rollback()
        return f"Error saving note: {e}"
    finally:
        db.close()


@tool
def list_notes() -> str:
    """List every note the user has saved."""
    db = SessionLocal()
    try:
        notes = db.query(Note).all()
        if not notes:
            return "No notes saved yet."
        return "\n".join(f"#{n.id}: {n.text}" for n in notes)
    except Exception as e:
        return f"Error listing notes: {e}"
    finally:
        db.close()


@tool
def delete_note(note_id: int) -> str:
    """Delete a saved note by its id number. Use this when the user asks to remove or delete a note."""
    db = SessionLocal()
    try:
        note = db.get(Note, note_id)
        if not note:
            return f"No note found with id {note_id}."
        db.delete(note)
        db.commit()
        return f"Deleted note #{note_id}."
    except Exception as e:
        db.rollback()
        return f"Error deleting note: {e}"
    finally:
        db.close()


@tool
def search_documents(query: str) -> str:
    """Search the user's uploaded documents for information relevant to the query.
    Use this when the user asks about content from a file they uploaded."""
    try:
        chunks = search_chunks(query)
        if not chunks:
            return "No uploaded documents found, or nothing relevant to that query."
        return "\n\n---\n\n".join(chunks)
    except Exception as e:
        return f"Error searching documents: {e}"


# Stateful tool: web_search (fallback path — primary path is plan_search
# + _run_web_queries, called directly from run_agent before the agent starts)

def build_web_search_tool():
    """Factory returning a web_search tool with a per-run call budget.

    This is the agent's fallback: normal turns get their search results
    injected into the input before the agent runs (see run_agent), so the
    agent shouldn't need to call this at all. It exists for cases where the
    planner decided no search was needed but the agent discovers otherwise,
    or where something is still missing after the pre-fetch.
    """
    calls_made = 0

    @tool
    async def web_search(queries: list[str]) -> str:
        """Search the web for information that is time-sensitive or not in your
        training data. Relevant search results for the user's question may
        already be included above in your input — check there first.

        Only call this if something you need is genuinely missing. If you do
        call it, batch every distinct piece of information you still need
        into ONE call's `queries` list — you have a budget of at most two
        calls this turn.
        """
        nonlocal calls_made
        calls_made += 1

        if calls_made > MAX_WEB_SEARCH_CALLS:
            return (
                "Search budget for this turn is used up. Do not call "
                "web_search again — answer the user now using the "
                "information already gathered, noting anything you "
                "couldn't confirm."
            )
        return await _run_web_queries(queries)

    return web_search


def build_tools() -> list:
    """Fresh tool list per agent run — web_search carries per-run state,
    so this must be called once per turn and the SAME list reused for both
    the agent and the AgentExecutor (see build_agent_executor)."""
    return [
        calculator,
        save_note,
        list_notes,
        delete_note,
        get_current_time,
        build_web_search_tool(),
        search_documents,
    ]

# Prompt

def build_prompt() -> ChatPromptTemplate:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    system = (
        f"You are AskFlow, a concise, friendly assistant. Today's date is {today}.\n\n"
        "Tool use policy:\n"
        "- Only call a tool when it's actually needed; answer directly for "
        "simple conversational questions.\n"
        "- Use the calculator tool for any arithmetic instead of computing "
        "it yourself.\n"
        "- Relevant web search results may already be included in the "
        "user's message below. Use them if present. Only call web_search "
        "yourself if something you need is genuinely missing, and if you "
        "do, batch every remaining sub-query into one call.\n"
        "- You have a limited number of tool-call steps this turn. Spend "
        "them deliberately — as soon as you have enough to give a useful, "
        "honest answer, stop calling tools and answer.\n"
        "- When you use a tool, incorporate its result into a clear final "
        "answer; do not just repeat the raw tool output."
    )
    return ChatPromptTemplate.from_messages([
        ("system", system),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])


# LLM

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=settings.GROQ_API_KEY,
    temperature=0,
    max_tokens=3000,
)


# Agent executor

def build_agent_executor() -> AgentExecutor:
    # Build tools ONCE and pass the same list to both the agent and the
    # executor — otherwise you get two web_search closures with two
    # independent counters, and the call budget silently stops working.
    tools = build_tools()
    return AgentExecutor(
        agent=create_tool_calling_agent(llm, tools, build_prompt()),
        tools=tools,
        verbose=getattr(settings, "DEBUG", False),
        max_iterations=MAX_ITERATIONS,
        max_execution_time=MAX_EXECUTION_TIME,
        handle_parsing_errors=True,
        early_stopping_method="generate",
    )



async def run_agent(message: str, history: list) -> str:
    """Run one agent turn.

    Search is planned and executed in parallel BEFORE the agent starts
    (see module docstring). Results are folded into the agent's input so
    the tool-calling loop typically doesn't need to search at all.
    """
    search_queries = await plan_search(message)
    augmented_input = message

    if search_queries:
        logger.info("Search plan for this turn: %s", search_queries)
        search_context = await _run_web_queries(search_queries)
        augmented_input = (
            f"{message}\n\n"
            "[Web search results gathered for this question — use them if "
            "relevant; only call web_search yourself if something is still "
            "missing]\n"
            f"{search_context}"
        )

    last_error: Exception | None = None
    for attempt in range(AGENT_RETRIES):
        try:
            executor = build_agent_executor()
            result = await executor.ainvoke({
                "input": augmented_input,
                "chat_history": history,
            })
            return result["output"]
        except Exception as e:
            last_error = e
            is_transient = "JSON" in str(e) or "parse" in str(e).lower()
            if is_transient and attempt < AGENT_RETRIES - 1:
                logger.warning(
                    "Transient tool-call parsing error (attempt %d/%d): %s",
                    attempt + 1, AGENT_RETRIES, e,
                )
                await asyncio.sleep(AGENT_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            break

    # Full detail goes to server-side logs only — never into a user-facing string.
    logger.error("Agent failed after retries: %s: %s", type(last_error).__name__, last_error)

    error_text = str(last_error).lower()
    if "rate_limit" in error_text or "429" in error_text:
        return ("I'm getting a lot of requests right now and hit a temporary limit. "
                "Please try again in a few minutes.")
    if "timeout" in error_text or "timed out" in error_text:
        return "That took longer than expected. Please try again."

    return "Sorry, I'm having trouble processing requests right now. Please try again shortly."








# async def run_agent(message: str, history: list) -> str:
#     """Run one agent turn.

#     Search is planned and executed in parallel BEFORE the agent starts
#     (see module docstring). Results are folded into the agent's input so
#     the tool-calling loop typically doesn't need to search at all.
#     """
#     search_queries = await plan_search(message)
#     augmented_input = message

#     if search_queries:
#         logger.info("Search plan for this turn: %s", search_queries)
#         search_context = await _run_web_queries(search_queries)
#         augmented_input = (
#             f"{message}\n\n"
#             "[Web search results gathered for this question — use them if "
#             "relevant; only call web_search yourself if something is still "
#             "missing]\n"
#             f"{search_context}"
#         )

#     last_error: Exception | None = None
#     for attempt in range(AGENT_RETRIES):
#         try:
#             executor = build_agent_executor()
#             result = await executor.ainvoke({
#                 "input": augmented_input,
#                 "chat_history": history,
#             })
#             return result["output"]
#         except Exception as e:
#             last_error = e
#             is_transient = "JSON" in str(e) or "parse" in str(e).lower()
#             if is_transient and attempt < AGENT_RETRIES - 1:
#                 logger.warning(
#                     "Transient tool-call parsing error (attempt %d/%d): %s",
#                     attempt + 1, AGENT_RETRIES, e,
#                 )
#                 await asyncio.sleep(AGENT_RETRY_BACKOFF_SECONDS * (attempt + 1))
#                 continue
#             break

#     logger.error("Agent failed after retries: %s", last_error)
#     return (
#         "Sorry, I ran into a problem processing that request. "
#         f"({type(last_error).__name__}: {last_error})"
#     )