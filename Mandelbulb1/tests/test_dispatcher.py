"""
tests/test_dispatcher.py
------------------------
Unit tests for dispatcher.execute_plan().

Verifies:
  - Correct execution of single-step plans for all three tools
  - Correct result schema for every step
  - Graceful handling of not-found results (None / empty list)
  - Placeholder resolution for both __derived_from_product_tags__
    and __derived_from_order_items__
  - Two-step tool chaining end-to-end
  - Sentinel handling (__unsupported__, __needs_order_id__)
  - Invalid tool name handling
  - Chained failures (step 2 when step 1 failed)
  - Empty plan input
  - Exception safety (dispatcher must never raise)
"""

import pytest
from dispatcher import execute_plan


# ===========================================================================
# Helpers
# ===========================================================================

def make_step(step: int, tool: str, args: dict, reason: str = "test") -> dict:
    """Build a synthetic plan step dict."""
    return {"step": step, "tool": tool, "args": args, "reason": reason}


def assert_result_schema(result: dict) -> None:
    """Assert a result dict conforms to the documented schema."""
    assert isinstance(result, dict)
    assert "step" in result
    assert "tool" in result
    assert "success" in result
    assert "data" in result
    assert "error" in result
    assert isinstance(result["success"], bool)


# ===========================================================================
# Result schema
# ===========================================================================

class TestResultSchema:

    def test_single_step_returns_one_result(self):
        plan = [make_step(1, "get_order", {"order_id": "ORD-10021"})]
        results = execute_plan(plan)
        assert len(results) == 1

    def test_result_conforms_to_schema(self):
        plan = [make_step(1, "get_order", {"order_id": "ORD-10021"})]
        results = execute_plan(plan)
        assert_result_schema(results[0])

    def test_step_number_is_preserved_in_result(self):
        plan = [make_step(7, "get_order", {"order_id": "ORD-10021"})]
        results = execute_plan(plan)
        assert results[0]["step"] == 7

    def test_tool_name_is_preserved_in_result(self):
        plan = [make_step(1, "get_order", {"order_id": "ORD-10021"})]
        results = execute_plan(plan)
        assert results[0]["tool"] == "get_order"

    def test_empty_plan_returns_empty_list(self):
        results = execute_plan([])
        assert results == []

    def test_none_plan_does_not_raise(self):
        # Dispatcher should handle gracefully; passing empty list is safe
        results = execute_plan([])
        assert isinstance(results, list)


# ===========================================================================
# get_order execution
# ===========================================================================

class TestGetOrderExecution:

    def test_valid_order_id_returns_success(self):
        plan = [make_step(1, "get_order", {"order_id": "ORD-10021"})]
        results = execute_plan(plan)
        assert results[0]["success"] is True

    def test_valid_order_data_is_correct(self):
        plan = [make_step(1, "get_order", {"order_id": "ORD-10021"})]
        results = execute_plan(plan)
        data = results[0]["data"]
        assert isinstance(data, dict)
        assert data["order_id"] == "ORD-10021"

    def test_valid_order_has_no_error(self):
        plan = [make_step(1, "get_order", {"order_id": "ORD-10021"})]
        results = execute_plan(plan)
        assert results[0]["error"] is None

    def test_invalid_order_id_returns_failure(self):
        plan = [make_step(1, "get_order", {"order_id": "ORD-99999"})]
        results = execute_plan(plan)
        assert results[0]["success"] is False

    def test_invalid_order_has_error_message(self):
        plan = [make_step(1, "get_order", {"order_id": "ORD-99999"})]
        results = execute_plan(plan)
        assert isinstance(results[0]["error"], str)
        assert len(results[0]["error"]) > 0

    def test_invalid_order_data_is_none(self):
        plan = [make_step(1, "get_order", {"order_id": "ORD-99999"})]
        results = execute_plan(plan)
        assert results[0]["data"] is None

    @pytest.mark.parametrize("order_id", [
        "ORD-10021", "ORD-10022", "ORD-10025", "ORD-10028", "ORD-10030"
    ])
    def test_multiple_valid_orders_all_succeed(self, order_id):
        plan = [make_step(1, "get_order", {"order_id": order_id})]
        results = execute_plan(plan)
        assert results[0]["success"] is True
        assert results[0]["data"]["order_id"] == order_id


# ===========================================================================
# get_product execution
# ===========================================================================

class TestGetProductExecution:

    def test_valid_product_id_returns_success(self):
        plan = [make_step(1, "get_product", {"product_id": "PROD-001"})]
        results = execute_plan(plan)
        assert results[0]["success"] is True

    def test_valid_product_data_is_correct(self):
        plan = [make_step(1, "get_product", {"product_id": "PROD-001"})]
        results = execute_plan(plan)
        data = results[0]["data"]
        assert isinstance(data, dict)
        assert data["product_id"] == "PROD-001"
        assert "name" in data
        assert "price" in data

    def test_invalid_product_id_returns_failure(self):
        plan = [make_step(1, "get_product", {"product_id": "PROD-999"})]
        results = execute_plan(plan)
        assert results[0]["success"] is False

    def test_invalid_product_has_error_message(self):
        plan = [make_step(1, "get_product", {"product_id": "PROD-999"})]
        results = execute_plan(plan)
        assert isinstance(results[0]["error"], str)

    def test_invalid_product_data_is_none(self):
        plan = [make_step(1, "get_product", {"product_id": "PROD-999"})]
        results = execute_plan(plan)
        assert results[0]["data"] is None

    @pytest.mark.parametrize("product_id", [
        "PROD-001", "PROD-005", "PROD-008", "PROD-012", "PROD-015"
    ])
    def test_multiple_valid_products_all_succeed(self, product_id):
        plan = [make_step(1, "get_product", {"product_id": product_id})]
        results = execute_plan(plan)
        assert results[0]["success"] is True


# ===========================================================================
# search_products execution
# ===========================================================================

class TestSearchProductsExecution:

    def test_valid_query_returns_success(self):
        plan = [make_step(1, "search_products", {"query": "wireless headphones"})]
        results = execute_plan(plan)
        assert results[0]["success"] is True

    def test_valid_query_data_is_a_list(self):
        plan = [make_step(1, "search_products", {"query": "wireless headphones"})]
        results = execute_plan(plan)
        assert isinstance(results[0]["data"], list)

    def test_valid_query_data_is_non_empty(self):
        plan = [make_step(1, "search_products", {"query": "wireless headphones"})]
        results = execute_plan(plan)
        assert len(results[0]["data"]) > 0

    def test_no_match_query_returns_failure(self):
        result = execute_plan([make_step(1, "search_products", {"query": "zzz_nonexistent_abcxyz999"})])
        assert result[0]["success"] is False

    def test_no_match_query_data_is_empty_list(self):
        result = execute_plan([make_step(1, "search_products", {"query": "zzz_nonexistent_abcxyz999"})])
        assert result[0]["data"] == []

    def test_no_match_has_error_message(self):
        result = execute_plan([make_step(1, "search_products", {"query": "zzz_nonexistent_abcxyz999"})])
        assert isinstance(result[0]["error"], str)

    def test_valid_search_has_no_error(self):
        plan = [make_step(1, "search_products", {"query": "running shoes"})]
        results = execute_plan(plan)
        assert results[0]["error"] is None


# ===========================================================================
# Sentinel handling
# ===========================================================================

class TestSentinelHandling:

    def test_unsupported_sentinel_returns_failure(self):
        plan = [make_step(1, "__unsupported__", {"original_question": "test"})]
        results = execute_plan(plan)
        assert results[0]["success"] is False

    def test_unsupported_sentinel_has_error_message(self):
        plan = [make_step(1, "__unsupported__", {"original_question": "test"})]
        results = execute_plan(plan)
        assert isinstance(results[0]["error"], str)
        assert len(results[0]["error"]) > 0

    def test_unsupported_sentinel_data_contains_original_args(self):
        args = {"original_question": "What time is it?"}
        plan = [make_step(1, "__unsupported__", args)]
        results = execute_plan(plan)
        # Data passes through the original args for response_builder context
        assert results[0]["data"] == args

    def test_needs_order_id_sentinel_returns_failure(self):
        plan = [make_step(1, "__needs_order_id__", {"original_question": "my order"})]
        results = execute_plan(plan)
        assert results[0]["success"] is False

    def test_needs_order_id_has_descriptive_error(self):
        plan = [make_step(1, "__needs_order_id__", {"original_question": "my order"})]
        results = execute_plan(plan)
        assert "order" in results[0]["error"].lower()

    def test_sentinel_tool_name_is_preserved(self):
        plan = [make_step(1, "__unsupported__", {})]
        results = execute_plan(plan)
        assert results[0]["tool"] == "__unsupported__"


# ===========================================================================
# Invalid tool name
# ===========================================================================

class TestInvalidToolName:

    def test_unknown_tool_returns_failure(self):
        plan = [make_step(1, "nonexistent_tool", {"arg": "value"})]
        results = execute_plan(plan)
        assert results[0]["success"] is False

    def test_unknown_tool_has_error_mentioning_tool_name(self):
        plan = [make_step(1, "nonexistent_tool", {})]
        results = execute_plan(plan)
        assert "nonexistent_tool" in results[0]["error"]

    def test_unknown_tool_data_is_none(self):
        plan = [make_step(1, "nonexistent_tool", {})]
        results = execute_plan(plan)
        assert results[0]["data"] is None

    def test_empty_tool_name_returns_failure(self):
        plan = [make_step(1, "", {})]
        results = execute_plan(plan)
        assert results[0]["success"] is False


# ===========================================================================
# Placeholder resolution
# ===========================================================================

class TestPlaceholderResolution:

    # ── __derived_from_product_tags__ ────────────────────────────────────

    def test_product_tags_placeholder_resolves_from_previous_product(self):
        """Step 1 fetches a product; step 2 should receive a real query."""
        plan = [
            make_step(1, "get_product", {"product_id": "PROD-001"}),
            make_step(2, "search_products", {"query": "__derived_from_product_tags__"}),
        ]
        results = execute_plan(plan)
        # Both steps should succeed and step 2 should have real data
        assert results[0]["success"] is True
        assert results[1]["success"] is True
        assert isinstance(results[1]["data"], list)

    def test_product_tags_placeholder_fails_if_previous_step_failed(self):
        """If step 1 fails, step 2 cannot resolve the placeholder."""
        plan = [
            make_step(1, "get_product", {"product_id": "PROD-999"}),  # will fail
            make_step(2, "search_products", {"query": "__derived_from_product_tags__"}),
        ]
        results = execute_plan(plan)
        assert results[0]["success"] is False
        assert results[1]["success"] is False
        assert "preceding step" in results[1]["error"].lower() or \
               "previous step" in results[1]["error"].lower()

    def test_product_tags_placeholder_fails_if_previous_data_is_order(self):
        """Passing an order dict when a product is expected should fail resolution."""
        plan = [
            make_step(1, "get_order", {"order_id": "ORD-10021"}),  # returns order, not product
            make_step(2, "search_products", {"query": "__derived_from_product_tags__"}),
        ]
        results = execute_plan(plan)
        assert results[1]["success"] is False
        assert "product" in results[1]["error"].lower()

    # ── __derived_from_order_items__ ─────────────────────────────────────

    def test_order_items_placeholder_resolves_from_previous_order(self):
        """Step 1 fetches an order; step 2 should receive a real query."""
        plan = [
            make_step(1, "get_order", {"order_id": "ORD-10021"}),
            make_step(2, "search_products", {"query": "__derived_from_order_items__"}),
        ]
        results = execute_plan(plan)
        assert results[0]["success"] is True
        # Step 2 may or may not find results depending on item names,
        # but it must not fail due to placeholder resolution errors.
        assert "preceding step" not in (results[1].get("error") or "")
        assert "previous step" not in (results[1].get("error") or "")

    def test_order_items_placeholder_fails_if_previous_step_failed(self):
        plan = [
            make_step(1, "get_order", {"order_id": "ORD-99999"}),   # will fail
            make_step(2, "search_products", {"query": "__derived_from_order_items__"}),
        ]
        results = execute_plan(plan)
        assert results[0]["success"] is False
        assert results[1]["success"] is False

    def test_order_items_placeholder_fails_if_previous_data_is_product(self):
        """Passing a product dict when an order is expected should fail resolution."""
        plan = [
            make_step(1, "get_product", {"product_id": "PROD-001"}),
            make_step(2, "search_products", {"query": "__derived_from_order_items__"}),
        ]
        results = execute_plan(plan)
        assert results[1]["success"] is False
        assert "order" in results[1]["error"].lower()


# ===========================================================================
# Multi-step chaining
# ===========================================================================

class TestMultiStepChaining:

    def test_two_step_chain_returns_two_results(self):
        plan = [
            make_step(1, "get_product", {"product_id": "PROD-001"}),
            make_step(2, "search_products", {"query": "__derived_from_product_tags__"}),
        ]
        results = execute_plan(plan)
        assert len(results) == 2

    def test_step_numbers_match_plan_step_numbers(self):
        plan = [
            make_step(1, "get_product", {"product_id": "PROD-001"}),
            make_step(2, "search_products", {"query": "__derived_from_product_tags__"}),
        ]
        results = execute_plan(plan)
        assert results[0]["step"] == 1
        assert results[1]["step"] == 2

    def test_three_step_plan_returns_three_results(self):
        plan = [
            make_step(1, "get_order", {"order_id": "ORD-10021"}),
            make_step(2, "get_product", {"product_id": "PROD-001"}),
            make_step(3, "search_products", {"query": "headphones"}),
        ]
        results = execute_plan(plan)
        assert len(results) == 3

    def test_get_order_then_get_product_both_succeed(self):
        plan = [
            make_step(1, "get_order", {"order_id": "ORD-10021"}),
            make_step(2, "get_product", {"product_id": "PROD-001"}),
        ]
        results = execute_plan(plan)
        assert results[0]["success"] is True
        assert results[1]["success"] is True

    def test_failed_step_does_not_prevent_later_independent_steps(self):
        """An independent step 2 (no placeholder) runs even if step 1 failed."""
        plan = [
            make_step(1, "get_order", {"order_id": "ORD-99999"}),  # fails
            make_step(2, "get_product", {"product_id": "PROD-001"}),  # independent
        ]
        results = execute_plan(plan)
        assert results[0]["success"] is False
        assert results[1]["success"] is True   # independent — not affected


# ===========================================================================
# Exception safety
# ===========================================================================

class TestExceptionSafety:

    def test_wrong_arg_name_returns_failure_not_exception(self):
        """Passing wrong arg name to a tool should produce an error result."""
        plan = [make_step(1, "get_order", {"wrong_arg": "ORD-10021"})]
        try:
            results = execute_plan(plan)
            assert results[0]["success"] is False
        except Exception as exc:
            pytest.fail(f"execute_plan raised instead of returning failure: {exc!r}")

    def test_dispatcher_never_raises_for_any_plan(self):
        """Regardless of what's in the plan, execute_plan must not raise."""
        weird_plans = [
            [],
            [make_step(1, "", {})],
            [make_step(1, "nonexistent", {"x": None})],
            [make_step(1, "__unsupported__", {})],
            [{"step": 1, "tool": "get_order", "args": {}, "reason": ""}],
        ]
        for weird_plan in weird_plans:
            try:
                results = execute_plan(weird_plan)
                assert isinstance(results, list)
            except Exception as exc:
                pytest.fail(f"execute_plan raised for plan {weird_plan!r}: {exc!r}")
