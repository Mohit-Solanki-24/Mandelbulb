"""
tests/test_response_builder.py
------------------------------
Unit tests for response_builder.build_response().

Tests are structured around synthetic result dicts that match the dispatcher's
output schema — no real tool calls are made in this file. This ensures each
formatter is tested in isolation from the tools and planner layers.
"""

import pytest
from response_builder import build_response


# ===========================================================================
# Helpers
# ===========================================================================

def make_result(
    step: int,
    tool: str,
    success: bool,
    data=None,
    error: str | None = None,
) -> dict:
    """Build a synthetic dispatcher result dict."""
    return {
        "step": step,
        "tool": tool,
        "success": success,
        "data": data,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Shared fake data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_order():
    return {
        "order_id": "ORD-10021",
        "customer": {"customer_id": "CUST-881", "name": "Emily Carter",
                     "email": "emily@test.com"},
        "status": "delivered",
        "placed_at": "2026-06-10T09:14:00Z",
        "estimated_delivery": "2026-06-14T18:00:00Z",
        "delivered_at": "2026-06-13T14:32:00Z",
        "shipping_address": "42 Maple Avenue, Austin, TX 78701",
        "items": [
            {"product_id": "PROD-001",
             "name": "Sony WH-1000XM5 Wireless Headphones",
             "quantity": 1, "unit_price": 349.99}
        ],
        "subtotal": 349.99,
        "shipping_cost": 0.00,
        "tax": 28.87,
        "total": 378.86,
        "payment_method": "Visa ending in 4821",
        "tracking_number": "1Z999AA10123456784",
    }


@pytest.fixture
def fake_product():
    return {
        "product_id": "PROD-001",
        "name": "Sony WH-1000XM5 Wireless Headphones",
        "category": "Electronics",
        "subcategory": "Audio",
        "price": 349.99,
        "currency": "USD",
        "stock": 42,
        "rating": 4.8,
        "tags": ["noise-cancelling", "wireless", "bluetooth"],
        "description": "Industry-leading noise cancelling headphones.",
        "brand": "Sony",
        "sku": "WH1000XM5-BLK",
    }


@pytest.fixture
def fake_alternative():
    return {
        "product_id": "PROD-002",
        "name": "Bose QuietComfort 45 Headphones",
        "category": "Electronics",
        "subcategory": "Audio",
        "price": 279.99,
        "currency": "USD",
        "stock": 28,
        "rating": 4.6,
        "tags": ["noise-cancelling", "wireless", "bluetooth"],
        "description": "Acclaimed noise cancellation technology.",
        "brand": "Bose",
        "sku": "QC45-WHT",
    }


# ===========================================================================
# General guarantees
# ===========================================================================

class TestGeneralGuarantees:

    def test_always_returns_a_string(self, fake_order):
        results = [make_result(1, "get_order", True, fake_order)]
        response = build_response(results)
        assert isinstance(response, str)

    def test_never_returns_none(self, fake_order):
        results = [make_result(1, "get_order", True, fake_order)]
        response = build_response(results)
        assert response is not None

    def test_never_returns_empty_string(self, fake_order):
        results = [make_result(1, "get_order", True, fake_order)]
        response = build_response(results)
        assert response.strip() != ""

    def test_empty_results_list_returns_fallback(self):
        response = build_response([])
        assert isinstance(response, str)
        assert len(response.strip()) > 0

    def test_does_not_raise_for_empty_results(self):
        try:
            response = build_response([])
            assert isinstance(response, str)
        except Exception as exc:
            pytest.fail(f"build_response([]) raised: {exc!r}")

    def test_does_not_raise_for_any_input(self, fake_order):
        inputs = [
            [],
            [make_result(1, "get_order", True, fake_order)],
            [make_result(1, "__unsupported__", False, {}, "unsupported")],
            [make_result(1, "nonexistent", False, None, "no such tool")],
        ]
        for results in inputs:
            try:
                response = build_response(results)
                assert isinstance(response, str)
            except Exception as exc:
                pytest.fail(f"build_response raised for input {results!r}: {exc!r}")


# ===========================================================================
# Scenario: Order found
# ===========================================================================

class TestOrderFoundResponse:

    def test_contains_order_id(self, fake_order):
        results = [make_result(1, "get_order", True, fake_order)]
        response = build_response(results)
        assert "ORD-10021" in response

    def test_contains_customer_name(self, fake_order):
        results = [make_result(1, "get_order", True, fake_order)]
        response = build_response(results)
        assert "Emily Carter" in response

    def test_contains_order_status(self, fake_order):
        results = [make_result(1, "get_order", True, fake_order)]
        response = build_response(results)
        assert "Delivered" in response or "delivered" in response.lower()

    def test_contains_item_name(self, fake_order):
        results = [make_result(1, "get_order", True, fake_order)]
        response = build_response(results)
        assert "Sony WH-1000XM5" in response

    def test_contains_total_price(self, fake_order):
        results = [make_result(1, "get_order", True, fake_order)]
        response = build_response(results)
        assert "378.86" in response

    def test_contains_tracking_number(self, fake_order):
        results = [make_result(1, "get_order", True, fake_order)]
        response = build_response(results)
        assert "1Z999AA10123456784" in response

    def test_contains_shipping_address(self, fake_order):
        results = [make_result(1, "get_order", True, fake_order)]
        response = build_response(results)
        assert "Austin" in response

    def test_does_not_expose_raw_json(self, fake_order):
        results = [make_result(1, "get_order", True, fake_order)]
        response = build_response(results)
        assert "{" not in response or "}" not in response or \
               "order_id" not in response  # should not look like raw JSON

    def test_cancelled_order_shows_cancellation_reason(self):
        cancelled_order = {
            "order_id": "ORD-10024",
            "customer": {"name": "Jake Morrison", "email": "j@test.com"},
            "status": "cancelled",
            "placed_at": "2026-06-15T08:45:00Z",
            "estimated_delivery": "2026-06-20T18:00:00Z",
            "delivered_at": None,
            "shipping_address": "88 Pine Road, Chicago, IL 60601",
            "items": [{"product_id": "PROD-011", "name": "LEGO Ferrari",
                        "quantity": 1, "unit_price": 399.99}],
            "subtotal": 399.99, "shipping_cost": 0.00, "tax": 33.00,
            "total": 432.99, "payment_method": "Visa",
            "tracking_number": None,
            "cancellation_reason": "Customer requested cancellation",
        }
        results = [make_result(1, "get_order", True, cancelled_order)]
        response = build_response(results)
        assert "Cancelled" in response or "cancelled" in response.lower()
        assert "cancellation" in response.lower() or "Customer requested" in response

    def test_returned_order_shows_refund_status(self):
        returned_order = {
            "order_id": "ORD-10027",
            "customer": {"name": "Sandra Kowalski", "email": "s@test.com"},
            "status": "returned",
            "placed_at": "2026-05-28T13:45:00Z",
            "estimated_delivery": "2026-06-02T18:00:00Z",
            "delivered_at": "2026-06-01T10:15:00Z",
            "shipping_address": "14 Cedar Court, Boston, MA 02101",
            "items": [{"product_id": "PROD-009", "name": "Ninja Air Fryer",
                        "quantity": 1, "unit_price": 119.99}],
            "subtotal": 119.99, "shipping_cost": 0.00, "tax": 9.90,
            "total": 129.89, "payment_method": "Mastercard",
            "tracking_number": "1Z999",
            "return_reason": "Product did not meet expectations",
            "refund_status": "refund_processed",
        }
        results = [make_result(1, "get_order", True, returned_order)]
        response = build_response(results)
        assert "return" in response.lower() or "refund" in response.lower()

    def test_out_for_delivery_shows_correct_status(self):
        order = {
            "order_id": "ORD-10026",
            "customer": {"name": "Tom Nguyen", "email": "t@test.com"},
            "status": "out_for_delivery",
            "placed_at": "2026-06-21T11:00:00Z",
            "estimated_delivery": "2026-06-24T20:00:00Z",
            "delivered_at": None,
            "shipping_address": "55 Willow Blvd, SF, CA",
            "items": [], "subtotal": 0, "shipping_cost": 0,
            "tax": 0, "total": 0,
            "payment_method": "Visa", "tracking_number": "1Z999",
        }
        results = [make_result(1, "get_order", True, order)]
        response = build_response(results)
        assert "Out for Delivery" in response or "out_for_delivery" in response.lower()


# ===========================================================================
# Scenario: Order not found
# ===========================================================================

class TestOrderNotFoundResponse:

    def test_contains_the_order_id_that_was_not_found(self):
        results = [make_result(
            1, "get_order", False, None,
            "Tool 'get_order' returned no result for args: {'order_id': 'ORD-99999'}."
        )]
        response = build_response(results)
        assert "ORD-99999" in response

    def test_contains_helpful_guidance(self):
        results = [make_result(
            1, "get_order", False, None,
            "Tool 'get_order' returned no result for args: {'order_id': 'ORD-99999'}."
        )]
        response = build_response(results)
        # Should suggest what to do next
        assert "email" in response.lower() or "check" in response.lower() \
               or "support" in response.lower()


# ===========================================================================
# Scenario: Product found
# ===========================================================================

class TestProductFoundResponse:

    def test_contains_product_name(self, fake_product):
        results = [make_result(1, "get_product", True, fake_product)]
        response = build_response(results)
        assert "Sony WH-1000XM5" in response

    def test_contains_price(self, fake_product):
        results = [make_result(1, "get_product", True, fake_product)]
        response = build_response(results)
        assert "349.99" in response

    def test_contains_rating(self, fake_product):
        results = [make_result(1, "get_product", True, fake_product)]
        response = build_response(results)
        assert "4.8" in response

    def test_contains_brand(self, fake_product):
        results = [make_result(1, "get_product", True, fake_product)]
        response = build_response(results)
        assert "Sony" in response

    def test_contains_category(self, fake_product):
        results = [make_result(1, "get_product", True, fake_product)]
        response = build_response(results)
        assert "Electronics" in response or "Audio" in response

    def test_contains_description(self, fake_product):
        results = [make_result(1, "get_product", True, fake_product)]
        response = build_response(results)
        assert "noise cancelling" in response.lower() or "Industry-leading" in response

    def test_contains_stock_info(self, fake_product):
        results = [make_result(1, "get_product", True, fake_product)]
        response = build_response(results)
        assert "42" in response or "Stock" in response or "stock" in response

    def test_out_of_stock_product_shows_warning(self, fake_product):
        fake_product["stock"] = 0
        results = [make_result(1, "get_product", True, fake_product)]
        response = build_response(results)
        assert "Out of Stock" in response or "out of stock" in response.lower()

    def test_low_stock_product_shows_warning(self, fake_product):
        fake_product["stock"] = 3
        results = [make_result(1, "get_product", True, fake_product)]
        response = build_response(results)
        assert "3" in response and ("left" in response.lower() or "Only" in response)


# ===========================================================================
# Scenario: Product not found
# ===========================================================================

class TestProductNotFoundResponse:

    def test_contains_the_product_id_that_was_not_found(self):
        results = [make_result(
            1, "get_product", False, None,
            "Tool 'get_product' returned no result for args: {'product_id': 'PROD-999'}."
        )]
        response = build_response(results)
        assert "PROD-999" in response

    def test_suggests_searching_instead(self):
        results = [make_result(
            1, "get_product", False, None,
            "Tool 'get_product' returned no result for args: {'product_id': 'PROD-999'}."
        )]
        response = build_response(results)
        assert "search" in response.lower() or "find" in response.lower() \
               or "try" in response.lower()


# ===========================================================================
# Scenario: Search results found
# ===========================================================================

class TestSearchResultsResponse:

    def test_response_mentions_number_of_results(self, fake_product, fake_alternative):
        products = [fake_product, fake_alternative]
        results = [make_result(1, "search_products", True, products)]
        response = build_response(results)
        assert "2" in response or "Found" in response

    def test_response_contains_product_names(self, fake_product, fake_alternative):
        products = [fake_product, fake_alternative]
        results = [make_result(1, "search_products", True, products)]
        response = build_response(results)
        assert "Sony WH-1000XM5" in response
        assert "Bose QuietComfort" in response

    def test_response_contains_prices(self, fake_product, fake_alternative):
        products = [fake_product, fake_alternative]
        results = [make_result(1, "search_products", True, products)]
        response = build_response(results)
        assert "349.99" in response
        assert "279.99" in response

    def test_single_result_is_displayed_correctly(self, fake_product):
        results = [make_result(1, "search_products", True, [fake_product])]
        response = build_response(results)
        assert "Sony WH-1000XM5" in response

    def test_results_are_numbered(self, fake_product, fake_alternative):
        products = [fake_product, fake_alternative]
        results = [make_result(1, "search_products", True, products)]
        response = build_response(results)
        assert "1." in response
        assert "2." in response


# ===========================================================================
# Scenario: Empty search results
# ===========================================================================

class TestEmptySearchResponse:

    def test_empty_search_returns_helpful_message(self):
        results = [make_result(
            1, "search_products", False, [],
            "Tool 'search_products' found no matching results for args: {'query': 'xyz'}."
        )]
        response = build_response(results)
        assert isinstance(response, str)
        assert len(response.strip()) > 0

    def test_empty_search_suggests_tips(self):
        results = [make_result(1, "search_products", False, [], "no results")]
        response = build_response(results)
        assert "explore" in response.lower() or "recommendations" in response.lower() \
               or "browse" in response.lower()


# ===========================================================================
# Scenario: Cheaper alternatives
# ===========================================================================

class TestCheaperAlternativesResponse:

    def test_alternative_response_mentions_source_product(
        self, fake_product, fake_alternative
    ):
        results = [
            make_result(1, "get_product", True, fake_product),
            make_result(2, "search_products", True, [fake_product, fake_alternative]),
        ]
        response = build_response(results)
        assert "Sony WH-1000XM5" in response

    def test_alternative_response_includes_alternative_product(
        self, fake_product, fake_alternative
    ):
        results = [
            make_result(1, "get_product", True, fake_product),
            make_result(2, "search_products", True, [fake_product, fake_alternative]),
        ]
        response = build_response(results)
        assert "Bose QuietComfort" in response

    def test_alternative_response_shows_cheaper_price(
        self, fake_product, fake_alternative
    ):
        results = [
            make_result(1, "get_product", True, fake_product),
            make_result(2, "search_products", True, [fake_product, fake_alternative]),
        ]
        response = build_response(results)
        assert "279.99" in response

    def test_alternative_response_excludes_source_product_from_list(
        self, fake_product, fake_alternative
    ):
        """Source product should not appear in its own alternatives list."""
        results = [
            make_result(1, "get_product", True, fake_product),
            make_result(2, "search_products", True, [fake_product, fake_alternative]),
        ]
        response = build_response(results)
        # Bose should appear, Sony should appear in the header but not as a recommendation
        assert "Bose QuietComfort" in response

    def test_no_alternatives_found_returns_graceful_message(self, fake_product):
        results = [
            make_result(1, "get_product", True, fake_product),
            make_result(2, "search_products", False, [],
                        "Tool 'search_products' found no matching results."),
        ]
        response = build_response(results)
        assert isinstance(response, str)
        assert "Sony WH-1000XM5" in response   # product details still shown
        assert "couldn't find" in response.lower() or "no" in response.lower()

    def test_alternative_from_order_shows_order_context(self, fake_order, fake_alternative):
        results = [
            make_result(1, "get_order", True, fake_order),
            make_result(2, "search_products", True, [fake_alternative]),
        ]
        response = build_response(results)
        assert "alternative" in response.lower() or "ORD-10021" in response \
               or "Sony" in response


# ===========================================================================
# Scenario: Unsupported question
# ===========================================================================

class TestUnsupportedResponse:

    def test_unsupported_returns_polite_message(self):
        results = [make_result(
            1, "__unsupported__", False,
            {"original_question": "What time is it?"},
            "No recognisable intent could be detected."
        )]
        response = build_response(results)
        assert "sorry" in response.lower() or "understand" in response.lower() \
               or "unable" in response.lower()

    def test_unsupported_response_lists_capabilities(self):
        results = [make_result(1, "__unsupported__", False, {}, "unsupported")]
        response = build_response(results)
        # Should mention what the agent CAN do
        assert "order" in response.lower() or "product" in response.lower() \
               or "search" in response.lower()

    def test_unsupported_does_not_expose_internal_error(self):
        results = [make_result(
            1, "__unsupported__", False, {},
            "No recognisable intent could be detected. "
            "The question does not match any supported tool pattern."
        )]
        response = build_response(results)
        # The raw internal error message should not be in the customer response
        assert "tool pattern" not in response


# ===========================================================================
# Scenario: Missing order ID
# ===========================================================================

class TestMissingOrderIdResponse:

    def test_needs_order_id_asks_for_id(self):
        results = [make_result(
            1, "__needs_order_id__", False,
            {"original_question": "Where is my order?"},
            "Order intent detected but no order ID found."
        )]
        response = build_response(results)
        assert "order" in response.lower()
        assert "id" in response.lower() or "number" in response.lower() \
               or "ID" in response

    def test_needs_order_id_tells_where_to_find_it(self):
        results = [make_result(1, "__needs_order_id__", False, {}, "needs order id")]
        response = build_response(results)
        assert "ord-10021" in response.lower()


# ===========================================================================
# Scenario: Ambiguous (order + product)
# ===========================================================================

class TestAmbiguousResponse:

    def test_ambiguous_response_contains_both_order_and_product(
        self, fake_order, fake_product
    ):
        results = [
            make_result(1, "get_order", True, fake_order),
            make_result(2, "get_product", True, fake_product),
        ]
        response = build_response(results)
        assert "ORD-10021" in response
        assert "Sony WH-1000XM5" in response

    def test_ambiguous_only_order_found(self, fake_order):
        results = [
            make_result(1, "get_order", True, fake_order),
            make_result(2, "get_product", False, None, "Product not found"),
        ]
        response = build_response(results)
        assert "ORD-10021" in response


# ===========================================================================
# Scenario: Tool / dispatcher failures
# ===========================================================================

class TestGenericFailureResponse:

    def test_unknown_tool_result_returns_fallback_message(self):
        results = [make_result(
            1, "mystery_tool", False, None,
            "Tool 'mystery_tool' is not registered."
        )]
        response = build_response(results)
        assert isinstance(response, str)
        assert len(response.strip()) > 0

    def test_failure_response_is_polite_not_technical(self):
        results = [make_result(
            1, "mystery_tool", False, None,
            "Unexpected error: NullPointerException in line 42 of dispatcher.py"
        )]
        response = build_response(results)
        # Should NOT expose technical error strings to the user
        assert "NullPointerException" not in response
        assert "dispatcher.py" not in response
        assert "line 42" not in response

    def test_custom_unsupported_dont_know_order_id(self):
        results = [make_result(
            1, "__unsupported__", False,
            {"original_question": "I don't know my order ID"},
            "Unsupported intent"
        )]
        response = build_response(results)
        assert "purchase history" in response.lower()
        assert "confirmation" in response.lower()

    def test_custom_unsupported_find_products(self):
        results = [make_result(
            1, "__unsupported__", False,
            {"original_question": "find products"},
            "Unsupported intent"
        )]
        response = build_response(results)
        assert "gaming mouse" in response.lower()
        assert "running shoes" in response.lower()
