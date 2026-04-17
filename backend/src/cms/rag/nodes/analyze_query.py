"""`analyze_query` — the graph's first node, and the codebase's first LLM call.

One structured-output call: intent, ranked department candidates, entities,
and rewritten search queries (build.md §0.3.2). Split into two functions so
the LLM call is mockable without touching LangChain internals:

- `analyze_query_core(query)` — the actual call, a plain `str -> QueryAnalysis`
  function with no `GraphState` dependency. This is what `cms-analyze` calls
  directly (steps.md: "every prompt tweak is a 5-second re-run") and what
  tests monkeypatch.
- `analyze_query(state)` — the graph node: spreads `analyze_query_core`'s
  result into a partial `GraphState` update.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.db.repositories.departments import list_department_descriptions
from cms.llm.chat.openai_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.rag.state import GraphState
from cms.schemas.query_analysis import QueryAnalysis

logger = logging.getLogger(__name__)


# Memoised for the process lifetime: `departments.py`'s own docstring notes the
# taxonomy "change[s] through a migration, not through the API," so a process
# never needs to see it change underneath a running server. A module global
# rather than `@lru_cache` because the loader is now a coroutine, and caching a
# coroutine hands every caller after the first an already-awaited object.
_department_block: str | None = None


def reset_department_prompt_block() -> None:
    """Drop the memoised taxonomy — the `cache_clear()` equivalent, for tests."""
    global _department_block
    _department_block = None


async def _department_prompt_block() -> str:
    """'- warranty (Warranty): Warranty coverage, claims...' per department."""
    global _department_block
    if _department_block is not None:
        return _department_block

    try:
        departments = await list_department_descriptions()
    except Exception:
        logger.exception("Failed to load department descriptions for the classifier prompt")
        raise
    _department_block = "\n".join(
        f"- {d['id']} ({d['name']}): {d['description']}" for d in departments
    )
    return _department_block


async def analyze_query_core(query: str) -> QueryAnalysis:
    """Classify `query` into a `QueryAnalysis` — the codebase's first
    `.with_structured_output()` call.
    """
    settings = get_settings()
    prompt = load_prompt("analyze_query")
    # method="function_calling": the default "json_schema" mode enforces
    # OpenAI's strict structured-output rule that every property must appear
    # in the schema's "required" array, which `entities`/`search_queries`
    # (declared with `default_factory`, so pydantic marks them optional)
    # fail — a 400 from OpenAI, not a validation error we control. Tool-calling
    # mode tolerates optional/default fields and is otherwise equivalent here.
    model = get_chat_model(settings.openai_model_cheap).with_structured_output(
        QueryAnalysis, method="function_calling"
    )
    chain = prompt | model

    try:
        return await chain.ainvoke(
            {"query": query, "departments": await _department_prompt_block()}
        )
    except Exception:
        logger.exception("analyze_query failed for query %r", query)
        raise


@traceable(name="analyze_query")
async def analyze_query(state: GraphState) -> dict:
    """The graph node: `analyze_query_core` plus the `GraphState` mapping.

    `department`/`dept_confidence` are copied out of `QueryAnalysis` as a
    convenience view of `department_candidates[0]` — see that schema's
    docstring for why they aren't derived from state directly.
    """
    analysis = await analyze_query_core(state["query"])
    return {
        "intent": analysis.intent,
        "department_candidates": [c.model_dump() for c in analysis.department_candidates],
        "department": analysis.department,
        "dept_confidence": analysis.dept_confidence,
        "entities": analysis.entities,
        "search_queries": analysis.search_queries,
    }
