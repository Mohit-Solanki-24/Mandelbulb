"""
planner.py
----------
Responsibility:
    Analyse a user's question using rule-based pattern matching and return a
    structured execution plan — an ordered list of tool-call steps.

    The planner is a PURE REASONING layer. It:
      - Reads only the question string.
      - Detects intent and extracts identifiers (order IDs, product IDs).
      - Returns a list of plan steps for the dispatcher to execute.
      - NEVER imports or calls any tool function.
      - NEVER fabricates or assumes data.

Plan step schema:
    {
        "step":   int,          # 1-based execution order
        "tool":   str,          # tool name matching a key in TOOL_REGISTRY
        "args":   dict,         # keyword arguments to pass to the tool
        "reason": str           # human-readable explanation of why this step was chosen
    }

Supported intents (in detection priority order):
    1. ORDER_LOOKUP          – "Where is my order?", "Status of ORD-10021"
    2. CHEAPER_ALTERNATIVE   – "cheaper", "less expensive", "alternative" + order/product ref
    3. PRODUCT_DETAIL        – "tell me about PROD-001", "details on PROD-003"
    4. PRODUCT_SEARCH        – "find headphones", "search for running shoes"
    5. AMBIGUOUS             – question contains both order and product signals
    6. UNSUPPORTED           – no recognisable intent found
"""

import json
import os
import re
import time
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("planner")

# ---------------------------------------------------------------------------
# Regex patterns for extracting structured identifiers
# ---------------------------------------------------------------------------

# Matches: ORD-10021, ord-10021, ORD10021 (with or without hyphen)
_ORDER_ID_PATTERN = re.compile(
    r"\b(ORD[-\s]?\d{4,6})\b",
    re.IGNORECASE,
)

# Matches: PROD-001, prod-001, PROD001 (with or without hyphen)
_PRODUCT_ID_PATTERN = re.compile(
    r"\b(PROD[-\s]?\d{3,5})\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Product name → product_id catalog (built once at import time)
# ---------------------------------------------------------------------------
# Allows the planner to recognise product names typed by customers
# (e.g. "Sony WH-1000XM5") without requiring a formal PROD-XXX ID.
# Loaded directly from mock_data.json — NOT through the tools layer.

from utils import load_mock_data

# Module-level singleton — built once when planner.py is first imported.
def _build_name_lookup() -> dict[str, str]:
    """
    Build a mapping of {lowercase_product_name: product_id} from mock_data.json.

    Used exclusively for name-based intent detection inside the planner.
    Returns an empty dict silently if the data file is missing, so the planner
    degrades gracefully rather than crashing at import time.

    Returns:
        dict[str, str]: Mapping of lower-cased product name → canonical product ID.
    """
    data = load_mock_data()
    return {
        p["name"].lower(): p["product_id"]
        for p in data.get("products", [])
        if "name" in p and "product_id" in p
    }

_PRODUCT_NAME_LOOKUP: dict[str, str] = _build_name_lookup()


_STOP_WORDS: set[str] = {
    "what", "where", "when", "who", "whom", "which", "why", "how",
    "the", "a", "an", "and", "or", "but", "if", "then", "else",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "about", "as", "into", "like", "through", "after", "before",
    "under", "over", "between", "out", "open", "time", "day", "life", "meaning",
    "today", "joke", "tell", "me", "you", "he", "she", "it", "they", "we",
    "this", "that", "these", "those", "my", "your", "his", "her", "its", "our",
    "their", "some", "any", "please", "can", "want", "need", "get", "give"
}


def _build_product_keywords() -> set[str]:
    """
    Build a set of all lowercase product names, categories, subcategories, brands,
    tags, and individual words from product names that act as product signals.
    """
    data = load_mock_data()
    keywords = set()
    for p in data.get("products", []):
        if "name" in p:
            name = p["name"].lower()
            if name not in _STOP_WORDS:
                keywords.add(name)
            for word in name.split():
                if len(word) >= 3 and word not in _STOP_WORDS:
                    keywords.add(word)
        if "category" in p:
            cat = p["category"].lower()
            if cat not in _STOP_WORDS:
                keywords.add(cat)
            for c_word in cat.split():
                if len(c_word) >= 3 and c_word not in _STOP_WORDS:
                    keywords.add(c_word)
        if "subcategory" in p:
            subcat = p["subcategory"].lower()
            if subcat not in _STOP_WORDS:
                keywords.add(subcat)
            for s_word in subcat.split():
                if len(s_word) >= 3 and s_word not in _STOP_WORDS:
                    keywords.add(s_word)
        if "brand" in p:
            brand = p["brand"].lower()
            if brand not in _STOP_WORDS:
                keywords.add(brand)
        if "tags" in p:
            for tag in p["tags"]:
                tag_l = tag.lower()
                if tag_l not in _STOP_WORDS:
                    keywords.add(tag_l)
                for t_word in tag_l.split():
                    if len(t_word) >= 3 and t_word not in _STOP_WORDS:
                        keywords.add(t_word)
    
    fallback_vocab = {
        "headphones", "iphone", "samsung", "tv", "mouse", "keyboard", "charger",
        "power bank", "shoes", "running shoes", "nike", "books", "kitchen", "appliances",
        "laptop", "monitor", "camera", "tablet", "earbuds", "smart watch", "watch", "electronics",
        "clothing", "footwear", "sports", "outdoors", "toys", "games", "paperwhite", "kindle",
        "instant pot", "airpods", "widget"
    }
    for item in fallback_vocab:
        if item not in _STOP_WORDS:
            keywords.add(item)
    return keywords


_PRODUCT_KEYWORDS: set[str] = _build_product_keywords()

# ---------------------------------------------------------------------------
# Intent keyword vocabulary
# ---------------------------------------------------------------------------

# Words that signal the user is asking about an order
_ORDER_KEYWORDS = {
    "order", "orders", "purchase", "bought", "buy", "delivery", "deliver",
    "shipped", "shipment", "shipping", "tracking", "track", "package",
    "parcel", "status", "arrived", "arrive", "return", "refund",
    "cancelled", "cancel", "receipt", "invoice",
}

# Words that signal the user wants to search or browse products
_SEARCH_KEYWORDS = {
    "find", "search", "show", "looking", "look", "recommend", "recommendation",
    "suggest", "suggestion", "browse", "list", "available", "options",
    "similar", "like", "alternatives", "products", "items", "buy", "shop",
    "good", "best", "top", "popular",
}

# Words that signal the user wants details on a specific product
_DETAIL_KEYWORDS = {
    "tell", "describe", "details", "detail", "info", "information",
    "specs", "specifications", "about", "more", "what is", "show me",
    "price", "cost", "how much", "rating", "stock", "available",
}

# Words that signal a request for a cheaper or alternative product
_ALTERNATIVE_KEYWORDS = {
    "cheaper", "less expensive", "budget", "affordable", "lower price",
    "save", "discount", "alternative", "alternatives", "instead",
    "different", "other", "another", "substitute", "similar",
}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Return a lowercase, whitespace-normalised version of the input string."""
    return " ".join(text.lower().split())


def _extract_order_id(text: str) -> Optional[str]:
    """
    Extract the first order ID found in the text.

    Normalises the matched ID to the canonical format 'ORD-XXXXX'
    (uppercase, with hyphen).

    Args:
        text (str): Raw question string.

    Returns:
        str | None: Canonical order ID (e.g. 'ORD-10021') or None.
    """
    match = _ORDER_ID_PATTERN.search(text)
    if match:
        # Normalise to uppercase and ensure hyphen separator
        raw = match.group(1).upper().replace(" ", "")
        if "-" not in raw:
            raw = raw[:3] + "-" + raw[3:]
        return raw
    return None


def _extract_product_id(text: str) -> Optional[str]:
    """
    Extract the first product ID found in the text.

    Normalises the matched ID to the canonical format 'PROD-XXX'
    (uppercase, with hyphen).

    Args:
        text (str): Raw question string.

    Returns:
        str | None: Canonical product ID (e.g. 'PROD-001') or None.
    """
    match = _PRODUCT_ID_PATTERN.search(text)
    if match:
        raw = match.group(1).upper().replace(" ", "")
        if "-" not in raw:
            raw = raw[:4] + "-" + raw[4:]
        return raw
    return None


def _extract_product_by_name(question: str) -> Optional[str]:
    """
    Match a known product name within the question and return its product_id.

    Matching strategy (applied in order of specificity):
      1. Full product name substring match (e.g. "Sony WH-1000XM5 Wireless Headphones").
      2. Consecutive n-gram match (3 words, then 2 words) from any product name,
         requiring the phrase to be at least 6 characters long to avoid false
         positives on short common words.

    Longer product names are tested first so the most specific match wins
    when multiple products could partially match the same question.

    Args:
        question (str): Raw customer question string.

    Returns:
        str | None: Canonical product ID (e.g. 'PROD-001') if a name was
                    matched, otherwise None.

    Examples:
        >>> _extract_product_by_name("Tell me about the Sony WH-1000XM5")
        'PROD-001'
        >>> _extract_product_by_name("I want a cheaper Instant Pot alternative")
        'PROD-008'
        >>> _extract_product_by_name("What headphones do you sell?")
        None  # no specific product named
    """
    if not _PRODUCT_NAME_LOOKUP:
        return None

    normalised_q = _normalise(question)

    # --- Pass 1: full name match (longest names first for specificity) ---
    for name_lower, product_id in sorted(
        _PRODUCT_NAME_LOOKUP.items(), key=lambda x: -len(x[0])
    ):
        if name_lower in normalised_q:
            return product_id

    # --- Pass 2: consecutive n-gram match (3-gram, then 2-gram) ---
    # Sort by name length descending so more specific products win ties.
    for name_lower, product_id in sorted(
        _PRODUCT_NAME_LOOKUP.items(), key=lambda x: -len(x[0])
    ):
        words = name_lower.split()
        for n in range(min(3, len(words)), 1, -1):   # try 3-grams before 2-grams
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i : i + n])
                # Require minimum length to avoid matching generic short words
                if len(phrase) >= 6 and phrase in normalised_q:
                    return product_id

    return None


def _has_keywords(tokens: set[str], keyword_set: set[str]) -> bool:
    """
    Return True if any token in *tokens* appears in *keyword_set*.

    Args:
        tokens (set[str]): Lowercased word tokens from the question.
        keyword_set (set[str]): Vocabulary set to check against.

    Returns:
        bool
    """
    return bool(tokens & keyword_set)


def _has_phrase(normalised_text: str, keyword_set: set[str]) -> bool:
    """
    Return True if any multi-word phrase in *keyword_set* appears in the text.

    Used for phrases like 'less expensive' or 'lower price' that won't be
    caught by single-token matching.

    Args:
        normalised_text (str): Lowercased, whitespace-normalised question.
        keyword_set (set[str]): Vocabulary set (may contain multi-word phrases).

    Returns:
        bool
    """
    return any(phrase in normalised_text for phrase in keyword_set if " " in phrase)


def _build_step(step: int, tool: str, args: dict, reason: str) -> dict:
    """
    Construct a single plan step dictionary.

    Args:
        step   (int):  1-based execution order index.
        tool   (str):  Tool name matching a key in TOOL_REGISTRY.
        args   (dict): Arguments to pass to the tool.
        reason (str):  Human-readable explanation of this step.

    Returns:
        dict: A plan step conforming to the plan step schema.
    """
    return {
        "step": step,
        "tool": tool,
        "args": args,
        "reason": reason,
    }


def _unsupported_plan(question: str) -> list[dict]:
    """
    Return a sentinel plan for questions that cannot be handled.

    Uses the special tool name '__unsupported__' so the dispatcher and
    response_builder can detect this case without raising an exception.

    Args:
        question (str): The original user question.

    Returns:
        list[dict]: A single-step plan marked as unsupported.
    """
    return [
        _build_step(
            step=1,
            tool="__unsupported__",
            args={"original_question": question},
            reason=(
                "No recognisable intent could be detected. "
                "The question does not match any supported tool pattern."
            ),
        )
    ]


# ---------------------------------------------------------------------------
# Intent detectors  (each returns a plan list or None if intent not matched)
# ---------------------------------------------------------------------------

def _detect_order_lookup(
    tokens: set[str],
    normalised: str,
    question: str,
) -> Optional[list[dict]]:
    """
    Detect ORDER_LOOKUP intent.

    Triggered when:
      - An order ID (e.g. ORD-10021) is explicitly present, OR
      - Order-related keywords are present without a competing product signal.

    Returns a single get_order step.
    """
    order_id = _extract_order_id(question)
    has_order_kw = _has_keywords(tokens, _ORDER_KEYWORDS)

    if not order_id and not has_order_kw:
        return None

    # If an ID is present, plan a direct lookup
    if order_id:
        return [
            _build_step(
                step=1,
                tool="get_order",
                args={"order_id": order_id},
                reason=f"User explicitly referenced order ID '{order_id}'.",
            )
        ]

    # Order keywords present but no specific ID — cannot look up without an ID.
    # Return unsupported so response_builder can ask the user for the order ID.
    return [
        _build_step(
            step=1,
            tool="__needs_order_id__",
            args={"original_question": question},
            reason=(
                "Order-related intent detected but no order ID found in the question. "
                "The agent needs to ask the customer for their order ID."
            ),
        )
    ]


def _detect_order_based_details_or_recommendations(
    tokens: set[str],
    normalised: str,
    question: str,
) -> Optional[list[dict]]:
    """
    Detect queries asking to:
      - identify the purchased product from an order,
      - fetch complete details of the purchased product,
      - recommend similar or cheaper products.

    Triggers a 3-step chain: get_order -> get_product -> search_products
    """
    order_id = _extract_order_id(question)
    if not order_id:
        return None

    product_related = {
        "product", "products", "item", "items", "buy", "bought", "purchase", "purchased",
        "specs", "specifications", "details", "alternative", "alternatives", "cheaper", "similar",
        "recommend", "recommendations", "what is inside", "what is in", "what did i", "what i bought",
        "what did i buy", "what did i purchase"
    }

    has_product_signal = (
        _has_keywords(tokens, product_related)
        or any(phrase in normalised for phrase in ["what did i", "what is in", "items inside", "product details", "what is the product", "which product", "item in order", "product in order", "what i bought"])
    )

    if has_product_signal:

        return [
            _build_step(
                step=1,
                tool="get_order",
                args={"order_id": order_id},
                reason=f"Fetch order '{order_id}' to identify the purchased product.",
            ),
            _build_step(
                step=2,
                tool="get_product",
                args={"product_id": "__product_id_from_order__"},
                reason="Extract the product ID from the order details and fetch complete product details.",
            ),
            _build_step(
                step=3,
                tool="search_products",
                args={"query": "__derived_from_product_tags__"},
                reason="Use the product details (category/tags/brand) to call search_products for similar or cheaper recommendations.",
            ),
        ]
    return None


def _detect_cheaper_alternative(
    tokens: set[str],
    normalised: str,
    question: str,
) -> Optional[list[dict]]:
    """
    Detect CHEAPER_ALTERNATIVE intent.

    Triggered when alternative/price keywords co-occur with either an order ID
    or a product ID. Builds a chained plan:

      - If order ID present  : Step 1 → get_order, Step 2 → search_products
      - If product ID present: Step 1 → get_product, Step 2 → search_products
      - Keywords only         : Step 1 → search_products (generic search)

    The search query for Step 2 is derived from the product context found in
    Step 1 at dispatch time; planner sets a placeholder query here.
    """
    has_alt_kw = (
        _has_keywords(tokens, _ALTERNATIVE_KEYWORDS)
        or _has_phrase(normalised, _ALTERNATIVE_KEYWORDS)
    )

    if not has_alt_kw:
        return None

    order_id = _extract_order_id(question)
    # Resolve product ID: try explicit PROD-XXX token first, then name matching.
    explicit_prod_id = _extract_product_id(question)
    product_id = explicit_prod_id or _extract_product_by_name(question)

    # Capture how the product was identified for use in the reason string.
    _matched_by_name = (
        product_id is not None
        and explicit_prod_id is None
    )

    # --- Chained: order → get_product → search ---
    if order_id:
        return [
            _build_step(
                step=1,
                tool="get_order",
                args={"order_id": order_id},
                reason=f"Fetch order '{order_id}' to identify the purchased product.",
            ),
            _build_step(
                step=2,
                tool="get_product",
                args={"product_id": "__product_id_from_order__"},
                reason="Extract the product ID from the order details and fetch complete product details.",
            ),
            _build_step(
                step=3,
                tool="search_products",
                args={"query": "__derived_from_product_tags__"},
                reason="Use the product details to search for similar or cheaper product recommendations.",
            ),
        ]


    # --- Chained: product (by ID or name) → search ---
    if product_id:
        _how_identified = (
            f"matched by name in the question"
            if _matched_by_name
            else f"explicit product ID '{product_id}' in the question"
        )
        return [
            _build_step(
                step=1,
                tool="get_product",
                args={"product_id": product_id},
                reason=(
                    f"Fetch product '{product_id}' ({_how_identified}) to determine "
                    "its category and tags before searching for alternatives."
                ),
            ),
            _build_step(
                step=2,
                tool="search_products",
                args={"query": "__derived_from_product_tags__"},
                reason=(
                    "Search for similar products using the category and tags "
                    "of the product found in Step 1."
                ),
            ),
        ]

    # --- Alternative intent without any ID: treat as a guided search ---
    # Extract search terms by removing alternative keywords from the question
    stop_words = {
        "cheaper", "alternative", "alternatives", "instead",
        "different", "substitute", "similar", "me", "a", "an",
        "the", "give", "show", "find", "get", "i", "want",
    }
    search_tokens = [t for t in tokens if t not in stop_words and len(t) > 2]
    fallback_query = " ".join(sorted(search_tokens)) if search_tokens else normalised

    return [
        _build_step(
            step=1,
            tool="search_products",
            args={"query": fallback_query},
            reason=(
                "Alternative/cheaper intent detected without a specific order "
                f"or product ID. Searching broadly for: '{fallback_query}'."
            ),
        )
    ]


def _detect_product_detail(
    tokens: set[str],
    normalised: str,
    question: str,
) -> Optional[list[dict]]:
    """
    Detect PRODUCT_DETAIL intent.

    Triggered when:
      - A product ID (PROD-XXX) is explicitly present, OR
      - A known product name is mentioned AND at least one detail keyword is
        present (name-only without detail intent falls through to PRODUCT_SEARCH).

    Detail keywords are used as a primary signal for name-based matches and
    as a secondary confirmation signal for ID-based matches.

    Returns a single get_product step.
    """
    product_id = _extract_product_id(question)
    matched_by_name = False

    if not product_id:
        # Fall back: try to resolve by product name.
        # Require at least one detail keyword to prevent over-triggering;
        # a bare product name without intent words is better handled by
        # _detect_product_search via tag/category matching.
        has_detail_kw = _has_keywords(tokens, _DETAIL_KEYWORDS)
        if not has_detail_kw:
            return None
        product_id = _extract_product_by_name(question)
        if not product_id:
            return None
        matched_by_name = True

    has_detail_kw = _has_keywords(tokens, _DETAIL_KEYWORDS)

    if matched_by_name:
        reason = (
            f"Product name matched in the question and resolved to '{product_id}'. "
            "Fetching full product details."
        )
    else:
        reason = (
            f"User explicitly referenced product ID '{product_id}'"
            + (" and asked for details." if has_detail_kw else ".")
        )

    return [
        _build_step(
            step=1,
            tool="get_product",
            args={"product_id": product_id},
            reason=reason,
        )
    ]


def _detect_product_search(
    tokens: set[str],
    normalised: str,
    question: str,
) -> Optional[list[dict]]:
    """
    Detect PRODUCT_SEARCH intent.
    """
    has_search_kw = _has_keywords(tokens, _SEARCH_KEYWORDS)

    # Check for product keywords
    has_product_token = bool(tokens & _PRODUCT_KEYWORDS)
    has_product_phrase = any(kw in normalised for kw in _PRODUCT_KEYWORDS if " " in kw)
    
    # Check if there is no order intent
    has_order_id = _extract_order_id(question) is not None
    has_order_kw = bool(tokens & _ORDER_KEYWORDS)
    no_order_intent = not has_order_id and not has_order_kw

    if not (has_search_kw or has_product_token or has_product_phrase) or not no_order_intent:
        return None

    # If it is a standalone product search (no search keywords like "find"),
    # use the normalized question itself as the query.
    if not has_search_kw:
        query = normalised
    else:
        # Remove high-frequency filler words to produce a cleaner search query
        filler = {
            "find", "search", "show", "me", "i", "am", "looking", "for", "a",
            "an", "the", "some", "any", "good", "please", "can", "you",
            "want", "need", "get", "give", "recommend", "suggest",
        }
        content_tokens = [t for t in tokens if t not in filler and len(t) > 2]
        query = " ".join(content_tokens) if content_tokens else normalised

    return [
        _build_step(
            step=1,
            tool="search_products",
            args={"query": query},
            reason=f"Search/browse intent detected. Searching catalog for: '{query}'.",
        )
    ]


def _detect_ambiguous(
    tokens: set[str],
    normalised: str,
    question: str,
) -> Optional[list[dict]]:
    """
    Detect AMBIGUOUS intent — question mixes order and product signals.

    When a question contains both an order ID and a product ID, or strong
    signals for both intents, prefer the order lookup first and follow up
    with the product detail, since the user likely wants order context plus
    product information.

    Returns a two-step chained plan.
    """
    order_id = _extract_order_id(question)
    product_id = _extract_product_id(question)

    if not (order_id and product_id):
        return None

    return [
        _build_step(
            step=1,
            tool="get_order",
            args={"order_id": order_id},
            reason=(
                f"Ambiguous question references both order '{order_id}' and "
                f"product '{product_id}'. Fetching the order first."
            ),
        ),
        _build_step(
            step=2,
            tool="get_product",
            args={"product_id": product_id},
            reason=(
                f"Also fetching product '{product_id}' as the user referenced "
                "both identifiers."
            ),
        ),
    ]



def call_gemini(question: str) -> Optional[list[dict]]:
    """
    Call official Google Gemini API to analyze the question and return a structured execution plan.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            pass

    if not api_key or api_key == "YOUR_GEMINI_API_KEY":
        print("[Planner] GEMINI_API_KEY not found.")
        logger.error("GEMINI_API_KEY is not set.")
        return None

    model = "gemini-2.5-flash"

    system_prompt = (
        "You are an AI Planning Engine.\n\n"
        "Your ONLY responsibility is deciding which tools should be executed.\n\n"
        "Available tools:\n\n"
        "1. get_order(order_id)\n\n"
        "2. get_product(product_id)\n\n"
        "3. search_products(query)\n\n"
        "Important Rule for Order Queries:\n"
        "For any query that asks to identify a purchased product, fetch complete product details, or recommend similar/cheaper products for an order, you MUST return a 3-step tool execution plan:\n"
        "Step 1: tool 'get_order', args: {'order_id': <order_id>}\n"
        "Step 2: tool 'get_product', args: {'product_id': '__product_id_from_order__'}\n"
        "Step 3: tool 'search_products', args: {'query': '__derived_from_product_tags__'}\n\n"
        "Never answer the user directly.\n\n"
        "Never generate explanations.\n\n"
        "Never generate markdown.\n\n"
        "Return ONLY valid JSON.\n\n"
        "Example:\n\n"
        "[\n"
        "  {\n"
        "    \"step\":1,\n"
        "    \"tool\":\"search_products\",\n"
        "    \"args\":{\n"
        "      \"query\":\"wireless headphones\"\n"
        "    }\n"
        "  }\n"
        "]"
    )


    print("[Planner] Calling Gemini...")
    print(f"[Planner] Model: {model}")

    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)
        t0 = time.time()
        response = client.models.generate_content(
            model=model,
            contents=question,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.0,
                response_mime_type="application/json",
            )
        )
        t1 = time.time()
        print("[Planner] Gemini Success")
        
        content = response.text.strip()
        duration = t1 - t0
        print(f"[Planner] Response time: {duration:.4f} seconds")
        
        # Token usage if available
        if response.usage_metadata:
            prompt_tokens = response.usage_metadata.prompt_token_count
            completion_tokens = response.usage_metadata.candidates_token_count
            print(f"[Planner] Tokens: prompt={prompt_tokens}, completion={completion_tokens}")

        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
            content = content.strip()
        
        plan_steps = json.loads(content)
        if isinstance(plan_steps, list):
            validated_steps = []
            for i, step in enumerate(plan_steps):
                if not isinstance(step, dict) or "tool" not in step:
                    continue
                validated_steps.append({
                    "step": step.get("step", i + 1),
                    "tool": step.get("tool"),
                    "args": step.get("args", {}),
                    "reason": step.get("reason", "Inferred by AI Planner")
                })
            if validated_steps:
                print("[Planner] Execution Plan Generated")
                print("[Planner] Dispatcher Started")
                return validated_steps
    except Exception as e:
        print("[Planner] Gemini Failed")
        print("[Planner] Regex Fallback")
        logger.error(f"Gemini call failed: {e}")
    return None


def _log_planner_execution(
    question: str,
    method: str,
    reason: str,
    execution_plan: list[dict],
    response_time: float
):
    """
    Log planning execution details to both Python logging and planner.log.
    """
    tool_names = [step.get("tool") for step in execution_plan]
    arguments = [step.get("args") for step in execution_plan]
    
    log_msg = (
        f"============================================================\n"
        f"TIMESTAMP: {datetime.now().isoformat()}\n"
        f"QUESTION: {question!r}\n"
        f"METHOD: {method}\n"
        f"REASON: {reason}\n"
        f"EXECUTION PLAN: {json.dumps(execution_plan, indent=2)}\n"
        f"TOOL NAMES: {tool_names}\n"
        f"ARGUMENTS: {arguments}\n"
        f"RESPONSE TIME: {response_time:.4f} seconds\n"
        f"============================================================\n"
    )
    
    logger.info("Planner execution: Method=%s, Tools=%s, Time=%.4fs", method, tool_names, response_time)
    
    log_path = os.path.join(os.path.dirname(__file__), "planner.log")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_msg)
    except Exception as e:
        logger.error(f"Failed to write to planner.log: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def plan(question: str) -> list[dict]:
    # Guard: blank or non-string input
    if not question or not isinstance(question, str) or not question.strip():
        t_start = time.time()
        p = _unsupported_plan(question or "")
        t_end = time.time()
        _log_planner_execution(
            question=question or "",
            method="Regex matched",
            reason="Blank or invalid input",
            execution_plan=p,
            response_time=t_end - t_start
        )
        return p

    t_start = time.time()
    normalised = _normalise(question)
    tokens = set(normalised.split())

    # 1. Ambiguous: both an order ID AND a product ID present
    result = _detect_ambiguous(tokens, normalised, question)
    
    # 1.5 Order-based details or recommendations
    if result is None:
        result = _detect_order_based_details_or_recommendations(tokens, normalised, question)

    # 2. Cheaper / alternative intent (may chain order→search or product→search)
    if result is None:
        result = _detect_cheaper_alternative(tokens, normalised, question)

        
    # 3. Order lookup (by ID or order-related keywords)
    if result is None:
        result = _detect_order_lookup(tokens, normalised, question)
        
    # 4. Product detail (explicit product ID present)
    if result is None:
        result = _detect_product_detail(tokens, normalised, question)
        
    # 5. Product search (search/browse keywords present)
    if result is None:
        result = _detect_product_search(tokens, normalised, question)

    # Check if Tier 1 confidently understood the intent
    if result is not None and len(result) > 0 and result[0]["tool"] != "__unsupported__":
        t_end = time.time()
        print("[Planner] Regex Used")
        print("[Planner] Dispatcher Started")
        _log_planner_execution(
            question=question,
            method="Regex matched",
            reason=result[0].get("reason", "Confidently matched intent via rules"),
            execution_plan=result,
            response_time=t_end - t_start
        )
        return result

    # Tier 2 fallback to Gemini
    llm_plan = call_gemini(question)
    if llm_plan is not None:
        t_end = time.time()
        _log_planner_execution(
            question=question,
            method="LLM used",
            reason=llm_plan[0].get("reason", "Intent determined via Gemini LLM"),
            execution_plan=llm_plan,
            response_time=t_end - t_start
        )
        return llm_plan

    # If LLM failed or returned invalid JSON, fallback to current regex planner's output
    print("[Planner] Regex Fallback")
    fallback_p = result if result is not None else _unsupported_plan(question)
    t_end = time.time()
    print("[Planner] Regex Used")
    print("[Planner] Dispatcher Started")
    _log_planner_execution(
        question=question,
        method="Regex matched",
        reason="No recognizable intent found; LLM fallback failed or returned invalid JSON. Using regex planner fallback.",
        execution_plan=fallback_p,
        response_time=t_end - t_start
    )
    return fallback_p
