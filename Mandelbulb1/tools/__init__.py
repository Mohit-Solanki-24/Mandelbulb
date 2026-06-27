"""
tools/__init__.py
-----------------
Package initialiser for the tools layer.

Exports all three tool functions and registers them in TOOL_REGISTRY —
a centralised dictionary that maps tool names to their callable functions.

The dispatcher uses TOOL_REGISTRY to execute tool calls by name without
needing to import individual modules directly.

Usage:
    from tools import TOOL_REGISTRY

    result = TOOL_REGISTRY["get_order"]("ORD-10021")
    result = TOOL_REGISTRY["search_products"]("wireless headphones")
    result = TOOL_REGISTRY["get_product"]("PROD-001")
"""

from tools.get_order import get_order
from tools.get_product import get_product
from tools.search_products import search_products

# ---------------------------------------------------------------------------
# TOOL_REGISTRY
# ---------------------------------------------------------------------------
# Maps each tool's canonical name (used by the planner and dispatcher) to its
# callable function. Add new tools here as the agent grows.
#
# Schema for each entry:
#   key   (str)      : canonical tool name — used by the planner in its plan
#   value (callable) : the tool function to invoke
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, callable] = {
    "get_order": get_order,
    "search_products": search_products,
    "get_product": get_product,
}

# Convenience list of all available tool names (useful for planner prompts)
AVAILABLE_TOOLS: list[str] = list(TOOL_REGISTRY.keys())

__all__ = [
    "get_order",
    "get_product",
    "search_products",
    "TOOL_REGISTRY",
    "AVAILABLE_TOOLS",
]
