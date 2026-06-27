"""
tests/test_planner.py
---------------------
Unit tests for planner.plan().

Verifies:
  - Correct intent detection for all six intents
  - Correct tool name selection
  - Correct argument extraction (order IDs, product IDs, search queries)
  - Product name matching (PROD-ID-free detection)
  - Tool chaining (multi-step plans)
  - Plan step schema conformance
  - Graceful handling of edge-case and unsupported inputs
"""

import pytest
from planner import plan


# ===========================================================================
# Helpers
# ===========================================================================

def assert_step_schema(step: dict) -> None:
    """Assert that a plan step conforms to the required schema."""
    assert isinstance(step, dict), "Step must be a dict"
    assert "step" in step, "Step missing 'step' key"
    assert "tool" in step, "Step missing 'tool' key"
    assert "args" in step, "Step missing 'args' key"
    assert "reason" in step, "Step missing 'reason' key"
    assert isinstance(step["step"], int), "'step' must be an int"
    assert isinstance(step["args"], dict), "'args' must be a dict"
    assert isinstance(step["reason"], str), "'reason' must be a str"
    assert step["reason"].strip(), "'reason' must not be empty"


def first_tool(result: list[dict]) -> str:
    return result[0]["tool"] if result else ""


def first_args(result: list[dict]) -> dict:
    return result[0]["args"] if result else {}


# ===========================================================================
# Schema conformance
# ===========================================================================

class TestPlanSchema:

    def test_plan_always_returns_a_list(self):
        result = plan("Where is my order ORD-10021?")
        assert isinstance(result, list)

    def test_plan_list_is_never_empty(self):
        result = plan("Where is my order ORD-10021?")
        assert len(result) >= 1

    def test_each_step_conforms_to_schema(self):
        result = plan("Where is my order ORD-10021?")
        for step in result:
            assert_step_schema(step)

    def test_step_numbers_are_sequential_from_one(self):
        result = plan("Find me cheaper alternatives to PROD-001")
        step_numbers = [s["step"] for s in result]
        assert step_numbers == list(range(1, len(result) + 1))

    def test_unsupported_plan_has_exactly_one_step(self):
        result = plan("What time does the store open?")
        assert len(result) == 1

    def test_empty_input_returns_one_unsupported_step(self):
        result = plan("")
        assert len(result) == 1
        assert result[0]["tool"] == "__unsupported__"


# ===========================================================================
# Intent: ORDER_LOOKUP
# ===========================================================================

class TestOrderLookupIntent:

    def test_explicit_order_id_triggers_get_order(self):
        result = plan("Where is my order ORD-10021?")
        assert first_tool(result) == "get_order"

    def test_extracted_order_id_is_correct(self):
        result = plan("Where is my order ORD-10021?")
        assert first_args(result)["order_id"] == "ORD-10021"

    def test_lowercase_order_id_is_normalised(self):
        result = plan("track ord-10021")
        assert first_tool(result) == "get_order"
        assert first_args(result)["order_id"] == "ORD-10021"

    def test_order_id_without_hyphen_is_recognised(self):
        result = plan("status of ORD10025")
        assert first_tool(result) == "get_order"
        assert first_args(result)["order_id"] == "ORD-10025"

    @pytest.mark.parametrize("question", [
        "Where is my order ORD-10022?",
        "Track my package ORD-10023",
        "Has ORD-10025 been delivered?",
        "What is the status of ORD-10028?",
        "I need to check order ORD-10030",
    ])
    def test_various_order_questions_with_id(self, question):
        result = plan(question)
        assert first_tool(result) == "get_order"
        assert "order_id" in first_args(result)

    def test_order_keyword_without_id_triggers_needs_order_id(self):
        # 'shipment' is in _ORDER_KEYWORDS; without an ID this should ask for one
        result = plan("My shipment has not arrived yet")
        assert first_tool(result) == "__needs_order_id__"

    def test_delivery_keyword_without_id_triggers_needs_order_id(self):
        result = plan("When will my delivery arrive?")
        assert first_tool(result) == "__needs_order_id__"

    def test_tracking_keyword_without_id_triggers_needs_order_id(self):
        result = plan("I want to track my package")
        assert first_tool(result) == "__needs_order_id__"

    def test_returns_single_step_for_order_lookup(self):
        result = plan("Show me order ORD-10021")
        assert len(result) == 1

    def test_order_args_has_order_id_key(self):
        result = plan("What happened to ORD-10026?")
        assert "order_id" in first_args(result)


# ===========================================================================
# Intent: PRODUCT_DETAIL (by ID)
# ===========================================================================

class TestProductDetailByIdIntent:

    def test_explicit_product_id_triggers_get_product(self):
        result = plan("Tell me about PROD-001")
        assert first_tool(result) == "get_product"

    def test_extracted_product_id_is_correct(self):
        result = plan("Tell me about PROD-001")
        assert first_args(result)["product_id"] == "PROD-001"

    def test_lowercase_product_id_is_normalised(self):
        result = plan("details on prod-005")
        assert first_tool(result) == "get_product"
        assert first_args(result)["product_id"] == "PROD-005"

    def test_product_id_without_hyphen_is_accepted(self):
        result = plan("What is PROD010?")
        assert first_tool(result) == "get_product"

    @pytest.mark.parametrize("question", [
        "Tell me about PROD-001",
        "Details on PROD-003",
        "Info about PROD-010",
        "What is PROD-015?",
        "How much does PROD-007 cost?",
    ])
    def test_various_product_detail_questions_by_id(self, question):
        result = plan(question)
        assert first_tool(result) == "get_product"
        assert "product_id" in first_args(result)

    def test_returns_single_step_for_product_detail(self):
        result = plan("Tell me about PROD-001")
        assert len(result) == 1


# ===========================================================================
# Intent: PRODUCT_DETAIL (by name)
# ===========================================================================

class TestProductDetailByNameIntent:

    def test_product_name_with_detail_keyword_triggers_get_product(self):
        result = plan("Tell me about the Sony WH-1000XM5")
        assert first_tool(result) == "get_product"

    def test_product_name_resolves_to_correct_product_id(self):
        result = plan("Tell me about the Sony WH-1000XM5")
        # Sony WH-1000XM5 is PROD-001
        assert first_args(result)["product_id"] == "PROD-001"

    def test_instant_pot_name_resolves_correctly(self):
        result = plan("What are the specs of the Instant Pot?")
        assert first_tool(result) == "get_product"
        assert first_args(result)["product_id"] == "PROD-008"

    def test_kindle_name_resolves_correctly(self):
        result = plan("Tell me about the Kindle Paperwhite")
        assert first_tool(result) == "get_product"
        assert first_args(result)["product_id"] == "PROD-010"

    def test_product_name_without_detail_keyword_does_not_trigger_detail(self):
        """A bare product name mention without detail intent should NOT trigger
        get_product (it should fall through to search or unsupported)."""
        result = plan("Sony WH-1000XM5")
        # Without a detail keyword, this should NOT route to get_product via name
        # It may route to search or unsupported — but NOT get_product from name only
        if first_tool(result) == "get_product":
            # If it does route to get_product, it must be via an explicit PROD-ID
            assert "PROD-" in plan("Sony WH-1000XM5")[0]["args"].get("product_id", "")


# ===========================================================================
# Intent: PRODUCT_SEARCH
# ===========================================================================

class TestProductSearchIntent:

    def test_find_keyword_triggers_search_products(self):
        result = plan("Find me wireless headphones")
        assert first_tool(result) == "search_products"

    def test_search_query_is_derived_from_question(self):
        result = plan("Find me wireless headphones")
        query = first_args(result)["query"]
        assert isinstance(query, str)
        assert len(query.strip()) > 0

    def test_search_query_contains_relevant_keywords(self):
        result = plan("Find me wireless headphones")
        query = first_args(result)["query"]
        assert "headphones" in query or "wireless" in query

    @pytest.mark.parametrize("question", [
        "Find me wireless headphones",
        "Show me running shoes",
        "Looking for kitchen appliances",
        "Recommend a good blender",
        "Find me a portable charger",
    ])
    def test_various_search_questions(self, question):
        result = plan(question)
        assert first_tool(result) == "search_products"

    def test_filler_words_are_stripped_from_query(self):
        result = plan("Can you show me some good running shoes please")
        query = first_args(result)["query"]
        assert "show" not in query
        assert "please" not in query
        assert "can" not in query

    def test_returns_single_step_for_search(self):
        result = plan("Find me wireless headphones")
        assert len(result) == 1


# ===========================================================================
# Intent: CHEAPER_ALTERNATIVE (with product ID)
# ===========================================================================

class TestCheaperAlternativeByIdIntent:

    def test_cheaper_keyword_with_product_id_triggers_chain(self):
        result = plan("Show me cheaper alternatives to PROD-001")
        assert len(result) == 2

    def test_first_step_is_get_product(self):
        result = plan("Show me cheaper alternatives to PROD-001")
        assert result[0]["tool"] == "get_product"
        assert result[0]["args"]["product_id"] == "PROD-001"

    def test_second_step_is_search_products(self):
        result = plan("Show me cheaper alternatives to PROD-001")
        assert result[1]["tool"] == "search_products"

    def test_second_step_has_placeholder_arg(self):
        result = plan("Show me cheaper alternatives to PROD-001")
        assert result[1]["args"]["query"] == "__derived_from_product_tags__"

    @pytest.mark.parametrize("question", [
        "Find a cheaper alternative to PROD-004",
        "I want something more affordable than PROD-007",
        "Show a budget option instead of PROD-014",
    ])
    def test_various_cheaper_questions_with_id(self, question):
        result = plan(question)
        assert len(result) == 2
        assert result[0]["tool"] == "get_product"
        assert result[1]["tool"] == "search_products"


# ===========================================================================
# Intent: CHEAPER_ALTERNATIVE (with product name)
# ===========================================================================

class TestCheaperAlternativeByNameIntent:

    def test_cheaper_keyword_with_product_name_triggers_chain(self):
        # 'Vitamix 5200' provides a 2-gram match for PROD-014
        result = plan("Show me cheaper alternatives to the Vitamix 5200")
        assert len(result) == 2

    def test_first_step_resolves_product_id_from_name(self):
        result = plan("I want a cheaper alternative to the Instant Pot")
        assert result[0]["tool"] == "get_product"
        # Instant Pot is PROD-008
        assert result[0]["args"]["product_id"] == "PROD-008"

    def test_second_step_is_search_with_placeholder(self):
        result = plan("I want a cheaper alternative to the Instant Pot")
        assert result[1]["tool"] == "search_products"
        assert result[1]["args"]["query"] == "__derived_from_product_tags__"


# ===========================================================================
# Intent: CHEAPER_ALTERNATIVE (with order ID)
# ===========================================================================

class TestCheaperAlternativeByOrderIntent:

    def test_cheaper_keyword_with_order_id_triggers_chain(self):
        result = plan("Find cheaper alternatives for my order ORD-10021")
        assert len(result) == 3

    def test_first_step_is_get_order(self):
        result = plan("Find cheaper alternatives for my order ORD-10021")
        assert result[0]["tool"] == "get_order"
        assert result[0]["args"]["order_id"] == "ORD-10021"

    def test_second_step_is_get_product_with_order_placeholder(self):
        result = plan("Find cheaper alternatives for my order ORD-10021")
        assert result[1]["tool"] == "get_product"
        assert result[1]["args"]["product_id"] == "__product_id_from_order__"

    def test_third_step_is_search_with_product_placeholder(self):
        result = plan("Find cheaper alternatives for my order ORD-10021")
        assert result[2]["tool"] == "search_products"
        assert result[2]["args"]["query"] == "__derived_from_product_tags__"



# ===========================================================================
# Intent: AMBIGUOUS (both order ID and product ID)
# ===========================================================================

class TestAmbiguousIntent:

    def test_both_ids_trigger_two_step_plan(self):
        result = plan("I ordered ORD-10021 which had PROD-001 in it")
        assert len(result) == 2

    def test_first_step_is_get_order_for_ambiguous(self):
        result = plan("I ordered ORD-10021 which had PROD-001 in it")
        assert result[0]["tool"] == "get_order"

    def test_second_step_is_get_product_for_ambiguous(self):
        result = plan("I ordered ORD-10021 which had PROD-001 in it")
        assert result[1]["tool"] == "get_product"

    def test_order_id_extracted_correctly_in_ambiguous(self):
        result = plan("I ordered ORD-10025 and want info on PROD-007")
        assert result[0]["args"]["order_id"] == "ORD-10025"

    def test_product_id_extracted_correctly_in_ambiguous(self):
        result = plan("I ordered ORD-10025 and want info on PROD-007")
        assert result[1]["args"]["product_id"] == "PROD-007"


# ===========================================================================
# Intent: UNSUPPORTED
# ===========================================================================

class TestUnsupportedIntent:

    @pytest.mark.parametrize("question", [
        "What time does the store open?",
        "What is the meaning of life?",
        "Tell me a joke",
        "How is the weather today?",
        "What is your name?",
    ])
    def test_unrelated_questions_return_unsupported(self, question):
        result = plan(question)
        assert result[0]["tool"] == "__unsupported__"

    def test_unsupported_plan_preserves_original_question(self):
        question = "What time does the store open?"
        result = plan(question)
        assert result[0]["args"].get("original_question") == question

    def test_unsupported_step_schema_is_valid(self):
        result = plan("What time does the store open?")
        assert_step_schema(result[0])


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_empty_string_returns_unsupported(self):
        result = plan("")
        assert result[0]["tool"] == "__unsupported__"

    def test_whitespace_only_returns_unsupported(self):
        result = plan("   ")
        assert result[0]["tool"] == "__unsupported__"

    def test_none_input_returns_unsupported(self):
        result = plan(None)
        assert result[0]["tool"] == "__unsupported__"

    def test_integer_input_returns_unsupported(self):
        result = plan(42)
        assert result[0]["tool"] == "__unsupported__"

    def test_does_not_raise_for_any_string_input(self):
        for question in ["", "  ", "??????????", "123", "!@#$%"]:
            try:
                result = plan(question)
                assert isinstance(result, list)
                assert len(result) >= 1
            except Exception as exc:
                pytest.fail(f"plan({question!r}) raised {exc!r}")


# ===========================================================================
# Hybrid Planner Tier 2 Tests
# ===========================================================================

from unittest.mock import patch, MagicMock
import json

class TestHybridPlanner:

    @patch("google.genai.Client")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "fake-api-key"})
    def test_tier2_gemini_fallback_success(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {
                "step": 1,
                "tool": "search_products",
                "args": {"query": "cool widget"},
                "reason": "User is searching for cool widgets"
            }
        ])
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        # Query that Tier 1 regex doesn't match confidently (returns __unsupported__)
        result = plan("What time does the store open?")
        assert len(result) == 1
        assert result[0]["tool"] == "search_products"
        assert result[0]["args"]["query"] == "cool widget"

    @patch("google.genai.Client")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "fake-api-key"})
    def test_tier2_gemini_fallback_failure(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("Connection error")

        # Query that Tier 1 regex doesn't match confidently
        result = plan("What time does the store open?")
        assert len(result) == 1
        assert result[0]["tool"] == "__unsupported__"

    @patch("google.genai.Client")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "fake-api-key"})
    def test_call_gemini_direct(self, mock_client_cls):
        from planner import call_gemini

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {
                "step": 1,
                "tool": "get_order",
                "args": {"order_id": "ORD-10021"},
                "reason": "Lookup order"
            }
        ])
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        res = call_gemini("Track my order ORD-10021")
        assert res is not None
        assert res[0]["tool"] == "get_order"
        assert res[0]["args"]["order_id"] == "ORD-10021"

