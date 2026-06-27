"""
dispatcher.py
-------------
Responsibility:
    Execute a structured plan produced by planner.plan() and return a list of
    per-step result dictionaries.

    The dispatcher is the EXECUTION layer. It:
      - Iterates over plan steps in order.
      - Handles sentinel tool names without hitting TOOL_REGISTRY.
      - Validates that real tool names exist in TOOL_REGISTRY.
      - Resolves dynamic placeholder arguments using previous step outputs.
      - Calls each tool and wraps every outcome — success, "not found", or
        exception — in a structured result dict.
      - NEVER raises an exception to the caller under any circumstances.

Result step schema:
    {
        "step":    int,         # mirrors the plan step number (1-based)
        "tool":    str,         # tool name that was called (or sentinel name)
        "success": bool,        # True if the tool returned usable data
        "data":    any,         # tool return value on success; None on failure
        "error":   str | None   # human-readable error message; None on success
    }

Placeholder arguments resolved by the dispatcher:
    "__derived_from_product_tags__"
        Builds a search query from the previous step's product result using
        its tags, subcategory, and category.

    "__derived_from_order_items__"
        Builds a search query from the previous step's order result using
        the names of items contained in that order.
"""

from typing import Any

from tools import TOOL_REGISTRY

# ---------------------------------------------------------------------------
# Constants — sentinel tool names and placeholder strings
# ---------------------------------------------------------------------------

# Sentinel tool names emitted by the planner for edge-case intents.
# These are NOT looked up in TOOL_REGISTRY; the dispatcher handles them directly.
_SENTINEL_UNSUPPORTED = "__unsupported__"
_SENTINEL_NEEDS_ORDER_ID = "__needs_order_id__"
_ALL_SENTINELS: frozenset[str] = frozenset(
    {_SENTINEL_UNSUPPORTED, _SENTINEL_NEEDS_ORDER_ID}
)

# Placeholder strings that appear in plan step args and require runtime resolution.
_PLACEHOLDER_PRODUCT_TAGS = "__derived_from_product_tags__"
_PLACEHOLDER_ORDER_ITEMS = "__derived_from_order_items__"
_PLACEHOLDER_PRODUCT_ID_FROM_ORDER = "__product_id_from_order__"


# ---------------------------------------------------------------------------
# Private helpers — result construction
# ---------------------------------------------------------------------------

def _build_result(
    step: int,
    tool: str,
    success: bool,
    data: Any = None,
    error: str | None = None,
) -> dict:
    """
    Construct a single execution result dictionary.

    Args:
        step    (int)        : 1-based plan step number.
        tool    (str)        : Tool name that was invoked (or sentinel name).
        success (bool)       : True if the tool returned usable data.
        data    (Any)        : The tool's return value; None if the call failed.
        error   (str | None) : Human-readable error description; None on success.

    Returns:
        dict: Structured result conforming to the result step schema.
    """
    return {
        "step": step,
        "tool": tool,
        "success": success,
        "data": data,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Private helpers — query derivation from previous step output
# ---------------------------------------------------------------------------

def _resolve_query_from_product(product: dict) -> str:
    """
    Build a focused search query string from a product dict's metadata.

    Called when a plan step's args contain the placeholder
    ``'__derived_from_product_tags__'``.  Combines the product's tags,
    subcategory, and category into a space-separated keyword string that
    ``search_products`` can score against.

    Strategy:
      1. Take up to 4 tags (most specific signal).
      2. Append subcategory and category (broader context).
      3. Deduplicate while preserving insertion order.

    Args:
        product (dict): A product dict as returned by the ``get_product`` tool.

    Returns:
        str: A space-separated search query, e.g.
             "noise-cancelling wireless bluetooth audio electronics".
             Falls back to the product's name if no metadata is available.
     """
    seen: set[str] = set()
    parts: list[str] = []

    def _add(term: str) -> None:
        normalised = term.strip().lower()
        if normalised and normalised not in seen:
            seen.add(normalised)
            parts.append(normalised)

    for tag in product.get("tags", [])[:4]:   # cap at 4 tags for query focus
        _add(tag)

    _add(product.get("subcategory", ""))
    _add(product.get("category", ""))

    return " ".join(parts) if parts else product.get("name", "product")


def _resolve_query_from_order(order: dict) -> str:
    """
    Build a search query string from the items listed in an order dict.

    Called when a plan step's args contain the placeholder
    ``'__derived_from_order_items__'``.  Extracts item names from the order
    and joins them into a space-separated keyword string so ``search_products``
    can find similar or alternative items.

    Deduplication is applied so repeated order lines produce clean queries.

    Args:
        order (dict): An order dict as returned by the ``get_order`` tool.

    Returns:
        str: A space-separated search query derived from item names, e.g.
             "Sony WH-1000XM5 Wireless Headphones".
             Falls back to the generic string "products" if the order is empty.
    """
    items: list[dict] = order.get("items", [])
    if not items:
        return "products"

    seen: set[str] = set()
    keywords: list[str] = []

    for item in items:
        name = item.get("name", "").strip()
        if name and name not in seen:
            seen.add(name)
            keywords.append(name)

    return " ".join(keywords) if keywords else "products"


# ---------------------------------------------------------------------------
# Private helpers — placeholder resolution
# ---------------------------------------------------------------------------

def _resolve_placeholders(
    args: dict,
    previous_result: dict | None,
) -> tuple[dict, str | None]:
    """
    Substitute placeholder argument values with runtime-derived values.

    Scans every value in ``args`` for known placeholder strings and replaces
    them using data carried in ``previous_result``.  All other values are
    passed through unchanged.

    Args:
        args            (dict)        : The raw argument dict from the plan step.
                                        This dict is NOT mutated — a copy is made.
        previous_result (dict | None) : The full result dict from the preceding
                                        step, or None if this is the first step.

    Returns:
        tuple[dict, str | None]:
          - Resolved args dict with all recognised placeholders replaced.
          - An error string if resolution failed (e.g. previous step returned
            no data), or None if all placeholders were resolved successfully.
    """
    resolved = dict(args)  # shallow copy — do not mutate the original plan step

    for key, value in resolved.items():

        # ── Placeholder: derive query from a previous get_product result ──
        if value == _PLACEHOLDER_PRODUCT_TAGS:
            if previous_result is None or not previous_result.get("success"):
                return resolved, (
                    f"Cannot resolve '{_PLACEHOLDER_PRODUCT_TAGS}': "
                    "the preceding step did not return a successful product result."
                )
            product = previous_result.get("data")
            if not isinstance(product, dict) or "product_id" not in product:
                return resolved, (
                    f"Cannot resolve '{_PLACEHOLDER_PRODUCT_TAGS}': "
                    "preceding step data does not look like a product dict "
                    f"(got: {type(product).__name__})."
                )
            resolved[key] = _resolve_query_from_product(product)

        # ── Placeholder: derive query from a previous get_order result ──
        elif value == _PLACEHOLDER_ORDER_ITEMS:
            if previous_result is None or not previous_result.get("success"):
                return resolved, (
                    f"Cannot resolve '{_PLACEHOLDER_ORDER_ITEMS}': "
                    "the preceding step did not return a successful order result."
                )
            order = previous_result.get("data")
            if not isinstance(order, dict) or "order_id" not in order:
                return resolved, (
                    f"Cannot resolve '{_PLACEHOLDER_ORDER_ITEMS}': "
                    "preceding step data does not look like an order dict "
                    f"(got: {type(order).__name__})."
                )
            resolved[key] = _resolve_query_from_order(order)

        # ── Placeholder: extract product ID from a previous get_order result ──
        elif value == _PLACEHOLDER_PRODUCT_ID_FROM_ORDER:
            if previous_result is None or not previous_result.get("success"):
                return resolved, (
                    f"Cannot resolve '{_PLACEHOLDER_PRODUCT_ID_FROM_ORDER}': "
                    "the preceding step did not return a successful order result."
                )
            order = previous_result.get("data")
            if not isinstance(order, dict) or "order_id" not in order:
                return resolved, (
                    f"Cannot resolve '{_PLACEHOLDER_PRODUCT_ID_FROM_ORDER}': "
                    "preceding step data does not look like an order dict."
                )
            items = order.get("items", [])
            if not items:
                return resolved, (
                    f"Cannot resolve '{_PLACEHOLDER_PRODUCT_ID_FROM_ORDER}': "
                    "order items list is empty."
                )
            resolved[key] = items[0].get("product_id")

    return resolved, None



# ---------------------------------------------------------------------------
# Private helpers — sentinel handling
# ---------------------------------------------------------------------------

def _execute_sentinel(step_num: int, tool_name: str, args: dict) -> dict:
    """
    Handle sentinel tool names emitted by the planner for special edge cases.

    Sentinels are never looked up in TOOL_REGISTRY.  They exist solely to
    carry structured context to the response_builder so it can formulate an
    appropriate customer-facing message.

    Supported sentinels:
        ``__unsupported__``
            The planner could not map the question to any tool.
        ``__needs_order_id__``
            Order intent was detected but no order ID was present.

    Args:
        step_num  (int)  : 1-based step index.
        tool_name (str)  : The sentinel string.
        args      (dict) : The plan step's args dict (passed through as data
                           so the response_builder has the original question).

    Returns:
        dict: A result step with ``success=False`` and a descriptive error
              string. The ``data`` field carries the original args dict.
    """
    _sentinel_messages: dict[str, str] = {
        _SENTINEL_UNSUPPORTED: (
            "The question could not be matched to any available tool. "
            "The agent is unable to answer this question."
        ),
        _SENTINEL_NEEDS_ORDER_ID: (
            "Order intent was detected but no order ID was found in the question. "
            "The customer needs to provide their order ID."
        ),
    }

    error_msg = _sentinel_messages.get(
        tool_name,
        f"Unknown sentinel tool name received: '{tool_name}'.",
    )

    return _build_result(
        step=step_num,
        tool=tool_name,
        success=False,
        data=args,      # pass through for response_builder context
        error=error_msg,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def execute_plan(plan: list[dict]) -> list[dict]:
    """
    Execute a structured plan produced by ``planner.plan()`` and return one
    result dictionary per step.

    Processing order for each step:
      1. **Sentinel check** — if the tool name is a sentinel, handle it
         immediately without touching TOOL_REGISTRY.
      2. **Registry validation** — confirm the tool exists in TOOL_REGISTRY;
         return an error result if not.
      3. **Placeholder resolution** — substitute runtime-derived values for
         any placeholder strings in the step's args.
      4. **Tool execution** — call the tool and wrap its return value.
      5. **Result classification**:
           - Tool returned a non-empty dict/list  → success=True
           - Tool returned None                   → success=False (not found)
           - Tool returned an empty list           → success=False (no results)
           - Tool raised an exception              → success=False (captured)

    The result from each step is available to the next step for chaining,
    enabling patterns like ``get_product`` → ``search_products`` where the
    second step's query is derived from the first step's product data.

    Args:
        plan (list[dict]): Ordered list of plan step dicts as produced by
                           ``planner.plan()``. Each step must contain:
                             - ``"step"``   (int)  : 1-based execution order
                             - ``"tool"``   (str)  : tool name or sentinel string
                             - ``"args"``   (dict) : arguments (may contain placeholders)
                             - ``"reason"`` (str)  : planner note (ignored here)

    Returns:
        list[dict]: One result dict per plan step, each containing:
            - ``"step"``    (int)       : mirrors the plan step number
            - ``"tool"``    (str)       : tool that was called
            - ``"success"`` (bool)      : True if tool returned usable data
            - ``"data"``    (Any)       : tool return value; None on failure
            - ``"error"``   (str|None)  : error description; None on success

    Guarantees:
        - This function NEVER raises. Every exception is caught and surfaced
          through the ``"error"`` field of the affected result dict.
        - If a step fails and a later step depends on its output via a
          placeholder, the later step also fails gracefully with a clear message.
        - An empty plan input returns an empty list.

    Examples:
        >>> from planner import plan
        >>> from dispatcher import execute_plan
        >>>
        >>> # Single-step: order lookup
        >>> results = execute_plan(plan("Where is my order ORD-10021?"))
        >>> results[0]["success"]
        True
        >>> results[0]["data"]["status"]
        'delivered'
        >>>
        >>> # Two-step chain: product detail → alternative search
        >>> results = execute_plan(plan("Show me cheaper alternatives to PROD-001"))
        >>> results[0]["tool"], results[1]["tool"]
        ('get_product', 'search_products')
        >>> results[1]["success"]
        True
        >>>
        >>> # Invalid order ID
        >>> results = execute_plan(plan("Track order ORD-99999"))
        >>> results[0]["success"]
        False
        >>> results[0]["error"]
        "Tool 'get_order' returned no result for args: {'order_id': 'ORD-99999'}."
    """
    if not plan:
        return []

    results: list[dict] = []
    previous_result: dict | None = None   # carries the last step's result for chaining

    for step_dict in plan:
        step_num: int = step_dict.get("step", len(results) + 1)
        tool_name: str = step_dict.get("tool", "")
        raw_args: dict = step_dict.get("args", {})

        # ------------------------------------------------------------------
        # 1. Sentinel tools — handle without TOOL_REGISTRY
        # ------------------------------------------------------------------
        if tool_name in _ALL_SENTINELS:
            result = _execute_sentinel(step_num, tool_name, raw_args)
            results.append(result)
            previous_result = result
            continue

        # ------------------------------------------------------------------
        # 2. Validate the tool exists in TOOL_REGISTRY
        # ------------------------------------------------------------------
        if tool_name not in TOOL_REGISTRY:
            result = _build_result(
                step=step_num,
                tool=tool_name,
                success=False,
                data=None,
                error=(
                    f"Tool '{tool_name}' is not registered in TOOL_REGISTRY. "
                    f"Available tools: {sorted(TOOL_REGISTRY.keys())}."
                ),
            )
            results.append(result)
            previous_result = result
            continue

        # ------------------------------------------------------------------
        # 3. Resolve placeholder arguments using the previous step's output
        # ------------------------------------------------------------------
        resolved_args, resolution_error = _resolve_placeholders(
            raw_args, previous_result
        )

        if resolution_error:
            result = _build_result(
                step=step_num,
                tool=tool_name,
                success=False,
                data=None,
                error=resolution_error,
            )
            results.append(result)
            previous_result = result
            continue

        # ------------------------------------------------------------------
        # 4. Call the tool — catch every possible exception
        # ------------------------------------------------------------------
        try:
            tool_fn = TOOL_REGISTRY[tool_name]
            return_value = tool_fn(**resolved_args)

            # ── Classify the return value ──────────────────────────────────
            # None → "not found" (get_order / get_product contract)
            if return_value is None:
                result = _build_result(
                    step=step_num,
                    tool=tool_name,
                    success=False,
                    data=None,
                    error=(
                        f"Tool '{tool_name}' returned no result for "
                        f"args: {resolved_args}."
                    ),
                )

            # Empty list → "no matches" (search_products contract)
            elif isinstance(return_value, list) and len(return_value) == 0:
                result = _build_result(
                    step=step_num,
                    tool=tool_name,
                    success=False,
                    data=[],
                    error=(
                        f"Tool '{tool_name}' found no matching results for "
                        f"args: {resolved_args}."
                    ),
                )

            # Non-empty return value — genuine success
            else:
                result = _build_result(
                    step=step_num,
                    tool=tool_name,
                    success=True,
                    data=return_value,
                    error=None,
                )

        except TypeError as exc:
            # Wrong argument names or missing required parameters
            result = _build_result(
                step=step_num,
                tool=tool_name,
                success=False,
                data=None,
                error=(
                    f"Tool '{tool_name}' was called with invalid arguments "
                    f"{resolved_args}: {exc}"
                ),
            )

        except FileNotFoundError as exc:
            # Tool could not locate mock_data.json
            result = _build_result(
                step=step_num,
                tool=tool_name,
                success=False,
                data=None,
                error=f"Data file not found when running '{tool_name}': {exc}",
            )

        except ValueError as exc:
            # Malformed JSON or bad data inside the data file
            result = _build_result(
                step=step_num,
                tool=tool_name,
                success=False,
                data=None,
                error=f"Data error in '{tool_name}': {exc}",
            )

        except Exception as exc:   # pylint: disable=broad-except
            # Catch-all safety net — the dispatcher must never propagate
            # any exception regardless of what the tool raises.
            result = _build_result(
                step=step_num,
                tool=tool_name,
                success=False,
                data=None,
                error=(
                    f"Unexpected error in '{tool_name}': "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        # ------------------------------------------------------------------
        # 5. Store result and advance the chaining cursor
        # ------------------------------------------------------------------
        results.append(result)
        previous_result = result   # expose this step's output to the next step

    return results
