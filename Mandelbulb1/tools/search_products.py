"""
tools/search_products.py
------------------------
Tool: search_products
Responsibility: Search the product catalog using a plain-text query string.
Performs keyword matching across product name, description, category,
subcategory, brand, and tags. Returns a ranked list of matching products.
Returns an empty list when no products match — never returns None.
"""

from utils import load_all_products

# Fields to search through for each product (in order of relevance weight)
_SEARCH_FIELDS = ["name", "brand", "tags", "category", "subcategory", "description"]


def _score_product(product: dict, keywords: list[str]) -> int:
    """
    Compute a relevance score for a product against a list of keywords.

    Scoring weights (per keyword match):
        - name or brand  : 4 points
        - tags           : 3 points
        - category / subcategory : 2 points
        - description    : 1 point

    Args:
        product (dict): A product dictionary from the catalog.
        keywords (list[str]): Lowercase, tokenised search terms.

    Returns:
        int: Total relevance score. 0 means no match.
    """
    weights = {
        "name": 4,
        "brand": 4,
        "tags": 3,
        "category": 2,
        "subcategory": 2,
        "description": 1,
    }

    score = 0
    for field, weight in weights.items():
        field_value = product.get(field, "")

        # Flatten lists (e.g. tags) into a single searchable string
        if isinstance(field_value, list):
            field_value = " ".join(field_value)

        field_lower = field_value.lower()
        for keyword in keywords:
            if keyword in field_lower:
                score += weight

    return score


def search_products(query: str) -> list[dict]:
    """
    Search the product catalog using a free-text query string.

    Tokenises the query into individual keywords and scores every product
    in the catalog based on how many keywords appear across key fields
    (name, brand, tags, category, subcategory, description).
    Results are returned sorted by relevance score, highest first.

    Args:
        query (str): A natural language or keyword search string.
                     Examples: "wireless headphones", "running shoes nike",
                               "kitchen appliances", "portable charger USB-C".

    Returns:
        list[dict]: A list of matching product dictionaries sorted by relevance.
                    Each product includes: product_id, name, category,
                    subcategory, price, currency, stock, rating, tags,
                    description, brand, sku.
                    Returns an EMPTY LIST if:
                      - No products match the query.
                      - The query is blank or contains only whitespace.

    Example:
        >>> results = search_products("wireless noise cancelling headphones")
        >>> [p["name"] for p in results]
        ['Sony WH-1000XM5 Wireless Headphones',
         'Bose QuietComfort 45 Headphones',
         'Apple AirPods Pro (2nd Generation)']

        >>> search_products("quantum refrigerator")  # no matches
        []
    """
    if not query or not isinstance(query, str) or not query.strip():
        return []

    # Tokenise: lowercase, split on whitespace, filter very short tokens
    keywords = [kw for kw in query.strip().lower().split() if len(kw) >= 2]

    if not keywords:
        return []

    products = load_all_products()

    scored: list[tuple[int, dict]] = []

    for product in products:
        score = _score_product(product, keywords)
        if score > 0:
            scored.append((score, product))

    # Sort descending by score; stable sort preserves catalog order for ties
    scored.sort(key=lambda x: x[0], reverse=True)

    return [product for _, product in scored]
