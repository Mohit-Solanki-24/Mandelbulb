"""
agent_bridge.py
---------------
Thin bridge between the Streamlit UI and the backend agent pipeline.

Exposes one function:

    query(question: str) -> AgentResult

AgentResult is a dataclass containing:
  - text      (str)              : Customer-friendly plain-text fallback
  - intent    (str)              : Detected intent label (used for UI branching)
  - order     (dict | None)      : Parsed order data, if any
  - products  (list[dict])       : Product list (search results or alternatives)
  - source    (dict | None)      : Source product/order for alternatives flow
  - error     (str | None)       : Error description for failure states

This module does NOT modify any backend files.  It calls the existing
planner → dispatcher → response_builder pipeline and additionally extracts
the raw structured data from dispatcher results for rich UI rendering.

Intent labels produced:
  "order_found"         – get_order returned a valid order
  "order_not_found"     – get_order returned None
  "product_found"       – get_product returned a valid product (1-step)
  "product_not_found"   – get_product returned None
  "search_results"      – search_products returned results
  "search_empty"        – search_products returned empty list
  "alternatives"        – 2-step chain: source + alternatives
  "unsupported"         – planner could not map the question
  "needs_order_id"      – order intent detected but no ID provided
  "error"               – unexpected failure
"""

from __future__ import annotations

import sys
import os
import traceback
import logging
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so the backend modules import cleanly
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from planner import plan
from dispatcher import execute_plan
from response_builder import build_response

logger = logging.getLogger(__name__)

# Sentinel tool names (must match dispatcher.py)
_S_UNSUPPORTED   = "__unsupported__"
_S_NEEDS_ORDER   = "__needs_order_id__"


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    """Structured result returned by query()."""
    text:     str                   # plain-text customer response (always set)
    intent:   str                   # intent label for UI branching
    order:    Optional[dict] = None # parsed order dict (order_found intent)
    products: list[dict]    = field(default_factory=list)   # product list
    source:   Optional[dict]= None  # source product/order for alternatives
    error:    Optional[str] = None  # error message (failure intents)
    tool_calls: list[dict]  = field(default_factory=list) # raw dispatcher results


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _tools(results: list[dict]) -> list[str]:
    return [r.get("tool", "") for r in results]

def _first(results: list[dict], name: str) -> Optional[dict]:
    return next((r for r in results if r.get("tool") == name), None)


def _classify(results: list[dict], text: str) -> AgentResult:
    """
    Classify dispatcher results into an AgentResult with the correct intent
    and extracted structured data.
    """
    if not results:
        return AgentResult(text=text, intent="error", error="Empty dispatcher results.")

    seq = _tools(results)

    # ── Sentinels ──────────────────────────────────────────────────────────
    if _S_UNSUPPORTED in seq:
        return AgentResult(text=text, intent="unsupported")

    if _S_NEEDS_ORDER in seq:
        return AgentResult(text=text, intent="needs_order_id")

    # ── 3-step: get_order → get_product → search_products  (alternatives from order) ────
    if seq == ["get_order", "get_product", "search_products"]:
        ord_r  = _first(results, "get_order")
        prod_r = _first(results, "get_product")
        srch_r = _first(results, "search_products")
        if ord_r and ord_r.get("success"):
            if prod_r and prod_r.get("success"):
                prods = srch_r["data"] if srch_r and srch_r.get("success") else []
                return AgentResult(
                    text=text, intent="alternatives",
                    source=prod_r["data"], products=prods,
                    order=ord_r["data"]
                )
            # Order succeeded but product failed
            return AgentResult(text=text, intent="order_found", order=ord_r["data"])
        # Order itself not found
        return AgentResult(text=text, intent="order_not_found",
                           error=ord_r.get("error") if ord_r else None)

    # ── 2-step: get_order → search_products  (alternatives from order) ────
    if seq == ["get_order", "search_products"]:
        ord_r  = _first(results, "get_order")
        srch_r = _first(results, "search_products")
        if ord_r and ord_r.get("success"):
            prods = srch_r["data"] if srch_r and srch_r.get("success") else []
            return AgentResult(
                text=text, intent="alternatives",
                source=ord_r["data"], products=prods,
            )
        # order itself not found
        return AgentResult(text=text, intent="order_not_found",
                           error=ord_r.get("error") if ord_r else None)

    # ── 2-step: get_product → search_products  (cheaper alternatives) ─────
    if seq == ["get_product", "search_products"]:
        prod_r = _first(results, "get_product")
        srch_r = _first(results, "search_products")
        if prod_r and prod_r.get("success"):
            prods = srch_r["data"] if srch_r and srch_r.get("success") else []
            return AgentResult(
                text=text, intent="alternatives",
                source=prod_r["data"], products=prods,
            )
        return AgentResult(text=text, intent="product_not_found",
                           error=prod_r.get("error") if prod_r else None)

    # ── 2-step: get_order + get_product  (ambiguous) ──────────────────────
    if seq == ["get_order", "get_product"]:
        ord_r  = _first(results, "get_order")
        prod_r = _first(results, "get_product")
        ord_ok  = ord_r  and ord_r.get("success")
        prod_ok = prod_r and prod_r.get("success")
        if ord_ok and prod_ok:
            return AgentResult(
                text=text, intent="order_found",
                order=ord_r["data"],
                products=[prod_r["data"]],
            )
        if ord_ok:
            return AgentResult(text=text, intent="order_found", order=ord_r["data"])
        if prod_ok:
            return AgentResult(text=text, intent="product_found",
                               products=[prod_r["data"]])
        return AgentResult(text=text, intent="error", error="Both lookups failed.")

    # ── Single-step: get_order ─────────────────────────────────────────────
    ord_r = _first(results, "get_order")
    if ord_r is not None:
        if ord_r.get("success"):
            return AgentResult(text=text, intent="order_found", order=ord_r["data"])
        return AgentResult(text=text, intent="order_not_found",
                           error=ord_r.get("error"))

    # ── Single-step: get_product ───────────────────────────────────────────
    prod_r = _first(results, "get_product")
    if prod_r is not None:
        if prod_r.get("success"):
            return AgentResult(text=text, intent="product_found",
                               products=[prod_r["data"]])
        return AgentResult(text=text, intent="product_not_found",
                           error=prod_r.get("error"))

    # ── Single-step: search_products ──────────────────────────────────────
    srch_r = _first(results, "search_products")
    if srch_r is not None:
        if srch_r.get("success"):
            return AgentResult(text=text, intent="search_results",
                               products=srch_r["data"])
        return AgentResult(text=text, intent="search_empty")

    # ── Fallback ───────────────────────────────────────────────────────────
    return AgentResult(text=text, intent="error", error="Unrecognised tool sequence.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_FALLBACK = (
    "⚠️  I'm sorry, something went wrong while processing your request.\n\n"
    "Please try again in a moment."
)

def query(question: str) -> AgentResult:
    """
    Run the full agent pipeline and return a structured AgentResult.

    Never raises. Always returns an AgentResult with at minimum a valid
    .text and .intent field.

    Args:
        question (str): Raw user question string.

    Returns:
        AgentResult: Contains the plain-text response plus rich structured data.
    """
    if not isinstance(question, str) or not question.strip():
        return AgentResult(
            text=(
                "🤔 It looks like your message was empty. "
                "Could you please rephrase your question?"
            ),
            intent="unsupported",
        )

    q = question.strip()

    try:
        execution_plan = plan(q)
    except Exception:
        logger.error("planner.plan() failed:\n%s", traceback.format_exc())
        return AgentResult(text=_FALLBACK, intent="error",
                           error="Planner failure.")

    try:
        results = execute_plan(execution_plan)
        for p_step, r_step in zip(execution_plan, results):
            if "args" not in r_step:
                r_step["args"] = p_step.get("args", {})
    except Exception:
        logger.error("dispatcher.execute_plan() failed:\n%s", traceback.format_exc())
        return AgentResult(text=_FALLBACK, intent="error",
                           error="Dispatcher failure.")

    try:
        text = build_response(results)
    except Exception:
        logger.error("response_builder.build_response() failed:\n%s",
                     traceback.format_exc())
        text = _FALLBACK

    res = _classify(results, text or _FALLBACK)
    res.tool_calls = results
    return res
