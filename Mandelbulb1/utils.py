"""
utils.py
--------
Shared utilities for the ShopSmart AI application. Consolidates mock data loading,
pricing, and date formatting to ensure consistency and eliminate duplication.
"""

import json
import os
from datetime import datetime
from typing import Any, Optional

# Resolve mock data path relative to this file
_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_data.json")

def load_mock_data() -> dict:
    """Load mock data dictionary from mock_data.json safely."""
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Data file not found at: {_DATA_PATH}. "
            "Ensure mock_data.json exists in the project root."
        )
    except json.JSONDecodeError as e:
        raise ValueError(f"mock_data.json contains invalid JSON: {e}")

def load_all_orders() -> list[dict]:
    """Load and return the list of orders from mock_data.json."""
    return load_mock_data().get("orders", [])

def load_all_products() -> list[dict]:
    """Load and return the list of products from mock_data.json."""
    return load_mock_data().get("products", [])

def fmt_price(amount: Any, currency: str = "USD") -> str:
    """Format price with currency symbol and 2 decimal places."""
    symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
    s = symbols.get(str(currency).upper(), f"{currency} ")
    try:
        return f"{s}{float(amount):,.2f}"
    except (TypeError, ValueError):
        return f"{s}{amount}"

def fmt_date_short(iso_string: Optional[str], fmt: str = "%d %b %Y") -> str:
    """Parse an ISO 8601 UTC timestamp and return a short date string (default format "13 Jun 2026")."""
    if not iso_string:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime(fmt)
    except Exception:
        return iso_string
