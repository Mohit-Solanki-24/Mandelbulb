"""
tools/get_order.py
------------------
Tool: get_order
Responsibility: Look up a single order by its order ID from the mock data store.
Returns the full order dictionary on success, or None if the order does not exist.
"""

from typing import Optional
from utils import load_all_orders


def get_order(order_id: str) -> Optional[dict]:
    """
    Retrieve a single order by its order ID.

    Performs a case-insensitive match against the stored order IDs.
    Returns the complete order dictionary including customer info, items,
    pricing, shipping address, status, and delivery dates.

    Args:
        order_id (str): The order ID to look up (e.g. "ORD-10021").

    Returns:
        dict: The matching order dictionary if found. Structure includes:
            - order_id       (str)
            - customer       (dict)  : customer_id, name, email
            - status         (str)   : "processing" | "shipped" | "out_for_delivery"
                                       | "delivered" | "cancelled" | "returned"
            - placed_at      (str)   : ISO 8601 timestamp
            - estimated_delivery (str | None)
            - delivered_at   (str | None)
            - shipping_address (str)
            - items          (list)  : list of {product_id, name, quantity, unit_price}
            - subtotal       (float)
            - shipping_cost  (float)
            - tax            (float)
            - total          (float)
            - payment_method (str)
            - tracking_number (str | None)
        None: If no order with the given ID exists.

    Example:
        >>> order = get_order("ORD-10021")
        >>> order["status"]
        'delivered'
        >>> get_order("ORD-99999")  # does not exist
        None
    """
    if not order_id or not isinstance(order_id, str):
        return None

    normalized_id = order_id.strip().upper()
    orders = load_all_orders()

    for order in orders:
        if order.get("order_id", "").upper() == normalized_id:
            return order

    return None
