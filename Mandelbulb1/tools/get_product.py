"""
tools/get_product.py
--------------------
Tool: get_product
Responsibility: Retrieve a single product from the catalog by its product ID.
Returns the full product dictionary on success, or None if the product does not exist.
"""

from typing import Optional
from utils import load_all_products


def get_product(product_id: str) -> Optional[dict]:
    """
    Retrieve a single product from the catalog by its product ID.

    Performs a case-insensitive match against stored product IDs.
    Returns the complete product dictionary including pricing, stock level,
    category, tags, description, brand, and SKU.

    Args:
        product_id (str): The product ID to look up (e.g. "PROD-001").

    Returns:
        dict: The matching product dictionary if found. Structure includes:
            - product_id   (str)
            - name         (str)
            - category     (str)
            - subcategory  (str)
            - price        (float)
            - currency     (str)   : e.g. "USD"
            - stock        (int)   : units currently in stock
            - rating       (float) : average customer rating (0.0 – 5.0)
            - tags         (list)  : list of keyword strings
            - description  (str)
            - brand        (str)
            - sku          (str)
            - image_url    (str)
        None: If no product with the given ID exists in the catalog.

    Example:
        >>> product = get_product("PROD-001")
        >>> product["name"]
        'Sony WH-1000XM5 Wireless Headphones'
        >>> product["price"]
        349.99
        >>> get_product("PROD-999")  # does not exist
        None
    """
    if not product_id or not isinstance(product_id, str):
        return None

    normalized_id = product_id.strip().upper()
    products = load_all_products()

    for product in products:
        if product.get("product_id", "").upper() == normalized_id:
            return product

    return None
