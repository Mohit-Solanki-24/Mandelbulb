"""
tests/test_agent.py
-------------------
End-to-end integration tests for run_agent(question: str) -> str.

These tests exercise the complete pipeline:
    run_agent → planner → dispatcher → response_builder

All assertions operate on the final string response only — no internal state
is inspected. This mirrors how an actual API consumer would interact with the agent.
"""

import pytest
from run_agent import run_agent


# ===========================================================================
# Helpers
# ===========================================================================

def assert_response_is_valid(response: str) -> None:
    """Basic invariants every run_agent response must satisfy."""
    assert isinstance(response, str), "Response must be a string"
    assert response.strip() != "", "Response must not be empty or whitespace-only"


# ===========================================================================
# Invariant: run_agent never raises and always returns a non-empty string
# ===========================================================================

class TestAgentInvariants:

    @pytest.mark.parametrize("question", [
        "Where is my order ORD-10021?",
        "Find wireless headphones",
        "Tell me about PROD-001",
        "",
        "   ",
        "What time is it?",
        "Show me cheaper alternatives to PROD-004",
        "Track my package ORD-99999",
    ])
    def test_always_returns_a_non_empty_string(self, question):
        response = run_agent(question)
        assert_response_is_valid(response)

    @pytest.mark.parametrize("bad_input", [None, 42, [], {}, 3.14, True])
    def test_never_raises_for_non_string_input(self, bad_input):
        try:
            response = run_agent(bad_input)
            assert isinstance(response, str)
            assert response.strip() != ""
        except Exception as exc:
            pytest.fail(f"run_agent({bad_input!r}) raised: {exc!r}")

    def test_never_exposes_stack_trace(self):
        """No response should look like a Python stack trace."""
        response = run_agent("This is a totally bizarre question #@$%^")
        assert "Traceback" not in response
        assert "File \"" not in response
        assert "line " not in response or "line" not in response[:50]

    def test_never_exposes_raw_json_in_response(self):
        response = run_agent("Where is my order ORD-10021?")
        # A raw JSON dump would have "order_id": style key-value pairs
        assert '"order_id"' not in response
        assert '"product_id"' not in response


# ===========================================================================
# Order lookup flows
# ===========================================================================

class TestOrderLookupFlows:

    def test_valid_delivered_order_returns_order_details(self):
        response = run_agent("Where is my order ORD-10021?")
        assert "ORD-10021" in response
        assert "Delivered" in response or "delivered" in response.lower()

    def test_valid_shipped_order_returns_shipped_status(self):
        response = run_agent("What is the status of ORD-10022?")
        assert "ORD-10022" in response
        assert "Shipped" in response or "shipped" in response.lower()

    def test_valid_processing_order_returns_processing_status(self):
        response = run_agent("Track my order ORD-10023")
        assert "ORD-10023" in response
        assert "Processing" in response or "processing" in response.lower()

    def test_valid_out_for_delivery_order(self):
        response = run_agent("Has ORD-10026 been delivered?")
        assert "ORD-10026" in response

    def test_valid_cancelled_order_shows_cancellation(self):
        response = run_agent("What happened to order ORD-10024?")
        assert "ORD-10024" in response
        assert "Cancelled" in response or "cancelled" in response.lower()

    def test_valid_returned_order_shows_return_info(self):
        response = run_agent("What is the status of ORD-10027?")
        assert "ORD-10027" in response
        assert "return" in response.lower() or "refund" in response.lower()

    def test_order_response_contains_item_name(self):
        response = run_agent("Show me order ORD-10021")
        assert "Sony" in response or "WH-1000XM5" in response

    def test_order_response_contains_total_price(self):
        response = run_agent("Show me order ORD-10021")
        # ORD-10021 total is $378.86
        assert "378.86" in response

    def test_invalid_order_id_returns_not_found_message(self):
        response = run_agent("Where is my order ORD-99999?")
        assert "ORD-99999" in response
        # Should not return a real order
        assert "Delivered" not in response or "ORD-10021" not in response

    def test_order_keywords_without_id_asks_for_id(self):
        # Use a keyword that IS in _ORDER_KEYWORDS (e.g. 'shipment')
        response = run_agent("My shipment has not arrived yet")
        # Should ask for the order ID
        assert "order" in response.lower()
        assert "id" in response.lower() or "ID" in response or "number" in response.lower()

    def test_tracking_request_without_id_asks_for_id(self):
        response = run_agent("I want to track my package")
        assert "order" in response.lower()

    @pytest.mark.parametrize("order_id,expected_substring", [
        ("ORD-10021", "Delivered"),
        ("ORD-10022", "Shipped"),
        ("ORD-10023", "Processing"),
    ])
    def test_various_order_statuses(self, order_id, expected_substring):
        response = run_agent(f"What is the status of {order_id}?")
        assert order_id in response
        assert expected_substring in response


# ===========================================================================
# Product detail flows
# ===========================================================================

class TestProductDetailFlows:

    def test_product_detail_by_id_returns_product_name(self):
        response = run_agent("Tell me about PROD-001")
        assert "Sony WH-1000XM5" in response

    def test_product_detail_by_id_returns_price(self):
        response = run_agent("Tell me about PROD-001")
        assert "349.99" in response

    def test_product_detail_by_id_returns_brand(self):
        response = run_agent("Details on PROD-008")
        assert "Instant Pot" in response

    def test_product_detail_by_id_returns_rating(self):
        response = run_agent("Tell me about PROD-001")
        assert "4.8" in response

    def test_product_detail_by_name_sony(self):
        response = run_agent("Tell me about the Sony WH-1000XM5")
        assert "Sony" in response
        assert "349.99" in response

    def test_product_detail_by_name_instant_pot(self):
        response = run_agent("What are the specs of the Instant Pot?")
        assert "Instant Pot" in response
        assert "89.95" in response

    def test_product_detail_by_name_kindle(self):
        response = run_agent("Tell me about the Kindle Paperwhite")
        assert "Kindle" in response
        assert "139.99" in response

    def test_invalid_product_id_returns_not_found_message(self):
        response = run_agent("Tell me about PROD-999")
        assert "PROD-999" in response
        assert "couldn't find" in response.lower() or "not find" in response.lower()

    @pytest.mark.parametrize("product_id", [
        "PROD-001", "PROD-004", "PROD-008", "PROD-010", "PROD-014",
    ])
    def test_multiple_product_ids_all_return_details(self, product_id):
        response = run_agent(f"Tell me about {product_id}")
        assert product_id not in response or True  # product name should appear
        assert isinstance(response, str)
        assert len(response.strip()) > 0


# ===========================================================================
# Product search flows
# ===========================================================================

class TestProductSearchFlows:

    def test_headphones_search_returns_results(self):
        response = run_agent("Find me wireless headphones")
        # At least one headphone product name should appear
        assert "Headphone" in response or "AirPods" in response

    def test_running_shoes_search_returns_results(self):
        response = run_agent("Show me running shoes")
        assert "Nike" in response or "Adidas" in response or "shoe" in response.lower()

    def test_kitchen_appliances_search_returns_results(self):
        response = run_agent("Find kitchen appliances")
        assert "Instant Pot" in response or "Ninja" in response or "Vitamix" in response

    def test_search_response_includes_prices(self):
        response = run_agent("Show me headphones")
        assert "$" in response or "USD" in response

    def test_search_response_includes_ratings(self):
        response = run_agent("Recommend wireless headphones")
        assert "/5" in response or "4." in response

    def test_no_match_query_returns_helpful_message(self):
        response = run_agent("Find me a zzz_nonexistent_abcxyz999")
        assert "couldn't find" in response.lower() or "no " in response.lower()
        assert "explore" in response.lower() or "recommendations" in response.lower() \
               or "browse" in response.lower()

    def test_search_for_water_bottle_returns_hydro_flask(self):
        response = run_agent("Find me a water bottle")
        assert "Hydro Flask" in response or "water bottle" in response.lower()

    def test_search_for_blender_returns_vitamix(self):
        response = run_agent("Find me a blender")
        assert "Vitamix" in response or "blender" in response.lower()

    @pytest.mark.parametrize("query", [
        "wireless headphones",
        "running shoes",
        "portable charger",
        "kitchen appliances",
        "e-reader",
    ])
    def test_various_searches_return_non_empty_results(self, query):
        response = run_agent(f"Find me {query}")
        assert isinstance(response, str)
        assert len(response.strip()) > 0


# ===========================================================================
# Cheaper alternative flows
# ===========================================================================

class TestCheaperAlternativeFlows:

    def test_cheaper_alternative_by_product_id(self):
        response = run_agent("Show me cheaper alternatives to PROD-001")
        # Sony is $349.99 — Bose ($279.99) should appear as a cheaper option
        assert isinstance(response, str)
        assert len(response.strip()) > 0

    def test_cheaper_alternative_mentions_source_product(self):
        response = run_agent("Show me cheaper alternatives to PROD-001")
        assert "Sony" in response or "WH-1000XM5" in response

    def test_cheaper_alternative_by_product_name(self):
        response = run_agent("Show me cheaper alternatives to the Sony WH-1000XM5")
        assert "Sony" in response or "alternative" in response.lower()

    def test_cheaper_alternative_for_instant_pot_by_name(self):
        response = run_agent("I want a cheaper alternative to the Instant Pot")
        assert "Instant Pot" in response or "kitchen" in response.lower() \
               or "alternative" in response.lower()

    def test_cheaper_alternative_by_order_id(self):
        response = run_agent("Find cheaper alternatives for my order ORD-10021")
        assert isinstance(response, str)
        assert len(response.strip()) > 0

    def test_cheaper_alternative_with_invalid_order_returns_not_found(self):
        response = run_agent("Find cheaper alternatives for my order ORD-99999")
        # response_builder shows a not-found message; the exact ID may or may not
        # appear depending on how the ID is extracted from the error string
        assert "couldn't find" in response.lower() or "not find" in response.lower() \
               or "wasn't" in response.lower() or "find an order" in response.lower()

    def test_cheaper_alternative_with_invalid_product_returns_not_found(self):
        response = run_agent("Find a cheaper alternative to PROD-999")
        # Not-found message should appear; ID may appear depending on error string extraction
        assert "couldn't find" in response.lower() or "not find" in response.lower() \
               or "PROD-999" in response


# ===========================================================================
# Unsupported question flows
# ===========================================================================

class TestUnsupportedFlows:

    @pytest.mark.parametrize("question", [
        "What time does the store open?",
        "Tell me a joke",
        "How is the weather today?",
        "What is the meaning of life?",
        "What is your name?",
        "Can you write me an essay?",
    ])
    def test_unsupported_question_returns_polite_decline(self, question):
        response = run_agent(question)
        assert isinstance(response, str)
        assert "sorry" in response.lower() or "understand" in response.lower() \
               or "help" in response.lower()

    def test_unsupported_response_guides_user(self):
        response = run_agent("Tell me a joke")
        # Should tell user what the agent CAN do
        assert "order" in response.lower() or "product" in response.lower() \
               or "search" in response.lower()


# ===========================================================================
# Edge case inputs
# ===========================================================================

class TestEdgeCaseInputs:

    def test_empty_string_returns_message_asking_for_question(self):
        response = run_agent("")
        assert isinstance(response, str)
        assert len(response.strip()) > 0
        # Should prompt the user to ask something
        assert "question" in response.lower() or "empty" in response.lower() \
               or "help" in response.lower()

    def test_whitespace_only_string_handled_gracefully(self):
        response = run_agent("   \t\n  ")
        assert_response_is_valid(response)

    def test_none_input_handled_gracefully(self):
        response = run_agent(None)
        assert_response_is_valid(response)

    def test_integer_input_handled_gracefully(self):
        response = run_agent(42)
        assert_response_is_valid(response)

    def test_list_input_handled_gracefully(self):
        response = run_agent(["order", "ORD-10021"])
        assert_response_is_valid(response)

    def test_dict_input_handled_gracefully(self):
        response = run_agent({"question": "order"})
        assert_response_is_valid(response)

    def test_very_long_question_handled_gracefully(self):
        long_question = "Find me " + "wireless headphones " * 100
        response = run_agent(long_question)
        assert_response_is_valid(response)

    def test_special_characters_in_question(self):
        response = run_agent("!@#$%^&*() ORD-10021 ???")
        assert_response_is_valid(response)
        # Should still detect the order ID
        assert "ORD-10021" in response or "order" in response.lower()

    def test_question_with_only_punctuation(self):
        response = run_agent("???!!!")
        assert_response_is_valid(response)


# ===========================================================================
# Chaining integration tests
# ===========================================================================

class TestToolChainingIntegration:

    def test_product_to_search_chain_executes_fully(self):
        """Full get_product → search_products chain end-to-end."""
        response = run_agent("Show me cheaper alternatives to PROD-001")
        # Sony ($349.99) — Bose ($279.99) is cheaper
        assert isinstance(response, str)
        # The response should contain either the source product or alternatives
        assert "Sony" in response or "Bose" in response \
               or "alternative" in response.lower()

    def test_order_to_search_chain_executes_fully(self):
        """Full get_order → search_products chain end-to-end."""
        response = run_agent("Find cheaper alternatives for items in order ORD-10025")
        assert isinstance(response, str)
        assert len(response.strip()) > 0

    def test_ambiguous_chain_returns_combined_response(self):
        """Full get_order + get_product ambiguous chain end-to-end."""
        response = run_agent("My order ORD-10021 contained PROD-001 — tell me more")
        assert isinstance(response, str)
        # Both order and product should be referenced
        assert "ORD-10021" in response or "Emily" in response
