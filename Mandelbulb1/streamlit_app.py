"""
streamlit_app.py
----------------
ShopSmart AI — Shopping Assistant
Full chat UI with live backend integration via agent_bridge.

State machine:
  show_landing=True  + no messages  → landing view (action cards)
  show_landing=False OR has messages → chat view (rich message cards)
"""

import re
import sys
import os
import streamlit as st
import textwrap
import base64
from datetime import datetime

# Ensure project root is importable
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ─── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ShopSmart AI — Shopping Assistant",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Load CSS ──────────────────────────────────────────────────────────────────
with open("styles.css", "r", encoding="utf-8") as _css_f:
    st.markdown(f"<style>{_css_f.read()}</style>", unsafe_allow_html=True)

from utils import fmt_price as _fmt_price, fmt_date_short as _fmt_date_short, load_all_orders, load_all_products

# ─── Session state initialisation ──────────────────────────────────────────────
_DEFAULTS = {
    "messages": [],
    "active_nav": "Chat Assistant",
    "show_landing": True,
    "recent_tools": [],
    "ctx_order": None,
    "ctx_product": None,
    "ctx_search": None,
    "active_card": None,
    "orders_selected_id": None,
    "products_selected_id": None,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "_agent_ready" not in st.session_state:
    try:
        from agent_bridge import query as _agent_query
        st.session_state._agent_ready   = True
        st.session_state._agent_query   = _agent_query
    except Exception as _e:
        st.session_state._agent_ready   = False
        st.session_state._agent_query   = None
        st.session_state._agent_err     = str(_e)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS — time / markdown
# ══════════════════════════════════════════════════════════════════════════════

def _ts() -> str:
    return datetime.now().strftime("%I:%M %p").lstrip("0")


def _md2html(text: str) -> str:
    """Convert lightweight markdown subset to safe HTML for bubble rendering."""
    text = text.strip()
    if not text:
        return ""
        
    lines = text.split("\n")
    html_blocks = []
    current_para = []
    in_list = False
    list_items = []
    
    def flush_para():
        if current_para:
            para_text = "<br>".join(current_para)
            para_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', para_text)
            para_text = re.sub(r'`([^`]+)`',     r'<code>\1</code>',     para_text)
            html_blocks.append(f"<p>{para_text}</p>")
            current_para.clear()
            
    def flush_list():
        if list_items:
            formatted_items = []
            for item in list_items:
                item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
                item = re.sub(r'`([^`]+)`',     r'<code>\1</code>',     item)
                formatted_items.append(f"<li>{item}</li>")
            html_blocks.append("<ul>" + "".join(formatted_items) + "</ul>")
            list_items.clear()
            
    for line in lines:
        line_stripped = line.strip()
        list_match = re.match(r'^\s*[•\-]\s+(.*)', line)
        if list_match:
            flush_para()
            in_list = True
            list_items.append(list_match.group(1))
        elif not line_stripped:
            flush_para()
            if in_list:
                flush_list()
                in_list = False
        else:
            if in_list:
                flush_list()
                in_list = False
            current_para.append(line)
            
    flush_para()
    flush_list()
    
    return "".join(html_blocks)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS — data formatting
# ══════════════════════════════════════════════════════════════════════════════


_STATUS_CFG = {
    "processing":       ("⏳", "Processing",       "#f59e0b", "#fffbeb", "#fde68a"),
    "shipped":          ("🚚", "Shipped",           "#3b82f6", "#eff6ff", "#bfdbfe"),
    "out_for_delivery": ("🚀", "Out for Delivery",  "#8b5cf6", "#f5f3ff", "#ddd6fe"),
    "delivered":        ("✅", "Delivered",          "#10b981", "#ecfdf5", "#a7f3d0"),
    "cancelled":        ("❌", "Cancelled",          "#ef4444", "#fef2f2", "#fecaca"),
    "returned":         ("🔄", "Returned",           "#f97316", "#fff7ed", "#fed7aa"),
}


# ══════════════════════════════════════════════════════════════════════════════
# RICH CARD RENDERERS — return HTML strings
# ══════════════════════════════════════════════════════════════════════════════

def _render_order_card(order: dict) -> str:
    """Render a professional order-detail card as HTML."""
    oid    = order.get("order_id", "Unknown")
    cust   = order.get("customer", {}).get("name", "Valued Customer")
    status = order.get("status", "unknown")
    emoji, label, color, bg, border = _STATUS_CFG.get(
        status,
        ("📋", status.replace("_"," ").title(), "#6b7280", "#f9fafb", "#d1d5db")
    )
    placed   = _fmt_date_short(order.get("placed_at",""))
    est_del  = _fmt_date_short(order.get("estimated_delivery",""))
    del_date = _fmt_date_short(order.get("delivered_at",""))
    address  = order.get("shipping_address","N/A")
    payment  = order.get("payment_method","N/A")
    tracking = order.get("tracking_number") or "Not yet available"
    total    = _fmt_price(order.get("total",0), "USD")
    subtotal = _fmt_price(order.get("subtotal",0), "USD")
    shipping = _fmt_price(order.get("shipping_cost",0), "USD")
    tax      = _fmt_price(order.get("tax",0), "USD")

    # Items
    items_html = ""
    for it in order.get("items", []):
        items_html += f"""
        <div class="oc-item-row">
            <div class="oc-item-dot"></div>
            <div class="oc-item-name">{it.get('name','Item')}</div>
            <div class="oc-item-qty">×{it.get('quantity',1)}</div>
            <div class="oc-item-price">{_fmt_price(it.get('unit_price',0))}</div>
        </div>"""

    # Optional notes
    cancel_html = ""
    if order.get("cancellation_reason"):
        cancel_html = f"""
        <div class="oc-note oc-note-cancel">
            ⚠️ <strong>Cancellation:</strong> {order['cancellation_reason']}
        </div>"""

    return_html = ""
    if order.get("return_reason"):
        refund = order.get("refund_status","Pending").replace("_"," ").title()
        return_html = f"""
        <div class="oc-note oc-note-return">
            🔄 <strong>Return:</strong> {order['return_reason']}<br>
            <span style="font-size:11px;">Refund status: {refund}</span>
        </div>"""

    html = f"""
    <div class="order-card">
        <!-- Header -->
        <div class="oc-header">
            <div class="oc-header-left">
                <div class="oc-order-id">📦 {oid}</div>
                <div class="oc-customer">{cust}</div>
            </div>
            <div class="oc-badge" style="background:{bg}; color:{color}; border:1px solid {border};">
                {emoji} {label}
            </div>
        </div>

        <!-- Dates row -->
        <div class="oc-meta-grid">
            <div class="oc-meta-cell">
                <div class="oc-meta-label">📅 Placed</div>
                <div class="oc-meta-value">{placed}</div>
            </div>
            <div class="oc-meta-cell">
                <div class="oc-meta-label">🎯 Est. Delivery</div>
                <div class="oc-meta-value">{est_del}</div>
            </div>
            {"" if not order.get("delivered_at") else f'''
            <div class="oc-meta-cell">
                <div class="oc-meta-label">✅ Delivered</div>
                <div class="oc-meta-value">{del_date}</div>
            </div>'''}
            <div class="oc-meta-cell">
                <div class="oc-meta-label">🔍 Tracking</div>
                <div class="oc-meta-value oc-tracking">{tracking}</div>
            </div>
        </div>

        <!-- Items -->
        <div class="oc-section">
            <div class="oc-section-title">🛍️ Items Ordered</div>
            {items_html}
        </div>

        <!-- Pricing -->
        <div class="oc-section">
            <div class="oc-section-title">💰 Pricing</div>
            <div class="oc-price-grid">
                <div class="oc-price-row"><span>Subtotal</span><span>{subtotal}</span></div>
                <div class="oc-price-row"><span>Shipping</span><span>{shipping}</span></div>
                <div class="oc-price-row"><span>Tax</span><span>{tax}</span></div>
                <div class="oc-price-row oc-price-total"><span>Total</span><span>{total}</span></div>
            </div>
        </div>

        <!-- Shipping -->
        <div class="oc-section">
            <div class="oc-section-title">📍 Delivery Details</div>
            <div class="oc-delivery-row"><span class="oc-dl">Ship to</span><span class="oc-dv">{address}</span></div>
            <div class="oc-delivery-row"><span class="oc-dl">Payment</span><span class="oc-dv">{payment}</span></div>
        </div>

        {cancel_html}
        {return_html}
    </div>"""
    return textwrap.dedent(html).replace('\n', '')


def _render_product_card(prod: dict) -> str:
    """Render a single product detail card as HTML."""
    name     = prod.get("name", "Unknown Product")
    brand    = prod.get("brand", "")
    cat      = prod.get("category", "")
    subcat   = prod.get("subcategory", "")
    price    = _fmt_price(prod.get("price",0), prod.get("currency","USD"))
    rating   = float(prod.get("rating", 0))
    stock    = int(prod.get("stock", 0))
    desc     = prod.get("description","")
    tags     = prod.get("tags",[])
    pid      = prod.get("product_id","")

    cat_str  = f"{cat} › {subcat}" if subcat else cat
    stars    = "★" * int(round(rating)) + "☆" * (5 - int(round(rating)))

    if stock == 0:
        stock_html = '<span class="pc-stock out">❌ Out of Stock</span>'
    elif stock <= 10:
        stock_html = f'<span class="pc-stock low">⚠️ Only {stock} left</span>'
    else:
        stock_html = f'<span class="pc-stock ok">✅ In Stock</span>'

    tags_html = "".join(f'<span class="pc-tag">{t}</span>' for t in tags[:6])

    # Category color mapping
    cat_colors = {
        "Electronics": ("#4361ee", "#eef2ff"),
        "Footwear":    ("#059669", "#ecfdf5"),
        "Kitchen":     ("#ea580c", "#fff7ed"),
        "Outdoors":    ("#7c3aed", "#f5f3ff"),
        "Books":       ("#0891b2", "#ecfeff"),
        "Accessories": ("#db2777", "#fdf2f8"),
    }
    cat_color, cat_bg = cat_colors.get(cat, ("#6b7280", "#f9fafb"))

    html = f"""
    <div class="product-card">
        <!-- Product header -->
        <div class="pc-header">
            <div class="pc-icon-wrap" style="background:{cat_bg}; border-color:{cat_color}22;">
                <span class="pc-icon">🛍️</span>
            </div>
            <div class="pc-header-info">
                <div class="pc-name">{name}</div>
                <div class="pc-brand-cat">
                    <span class="pc-brand">{brand}</span>
                    <span class="pc-sep">·</span>
                    <span class="pc-cat" style="color:{cat_color};">{cat_str}</span>
                </div>
            </div>
        </div>

        <!-- Price / Rating / Stock row -->
        <div class="pc-stats">
            <div class="pc-price">{price}</div>
            <div class="pc-rating">
                <span class="pc-stars">{stars}</span>
                <span class="pc-rating-val">{rating}/5</span>
            </div>
            {stock_html}
        </div>

        <!-- Description -->
        <div class="pc-desc">{desc}</div>

        <!-- Tags -->
        {"" if not tags else f'<div class="pc-tags">{tags_html}</div>'}

        <!-- Footer -->
        <div class="pc-footer">
            <span class="pc-pid">ID: {pid}</span>
        </div>
    </div>"""
    return textwrap.dedent(html).replace('\n', '')


def _render_search_cards(products: list[dict], query: str = "") -> str:
    """Render a grid of product search result cards."""
    shown = products[:5]
    header = f'<div class="search-header">🔍 Found <strong>{len(products)}</strong> product{"s" if len(products)!=1 else ""}{f" for <em>\"{query}\"</em>" if query else ""}</div>'

    cards_html = ""
    for p in shown:
        name    = p.get("name","Unknown")
        brand   = p.get("brand","")
        cat     = p.get("category","")
        subcat  = p.get("subcategory","")
        price   = _fmt_price(p.get("price",0), p.get("currency","USD"))
        rating  = float(p.get("rating",0))
        stock   = int(p.get("stock",0))
        desc    = p.get("description","")
        short_d = (desc[:90] + "…") if len(desc) > 90 else desc
        stars   = "★" * int(round(rating)) + "☆" * (5-int(round(rating)))
        cat_str = f"{cat} › {subcat}" if subcat else cat

        if stock == 0:
            stock_badge = '<span class="sr-badge badge-out">Out of Stock</span>'
        elif stock <= 10:
            stock_badge = f'<span class="sr-badge badge-low">Only {stock} left</span>'
        else:
            stock_badge = '<span class="sr-badge badge-ok">In Stock</span>'

        cards_html += f"""
        <div class="sr-card">
            <div class="sr-card-left">
                <div class="sr-card-icon">🛍️</div>
            </div>
            <div class="sr-card-body">
                <div class="sr-name">{name}</div>
                <div class="sr-meta">
                    <span class="sr-brand">{brand}</span>
                    <span class="sr-sep">·</span>
                    <span class="sr-cat">{cat_str}</span>
                </div>
                <div class="sr-desc">{short_d}</div>
                <div class="sr-footer">
                    <span class="sr-price">{price}</span>
                    <span class="sr-stars">{stars}</span>
                    <span class="sr-rating">{rating}/5</span>
                    {stock_badge}
                </div>
            </div>
        </div>"""

    if len(products) > 5:
        extra = len(products) - 5
        cards_html += f'<div class="sr-more">… and {extra} more result{"s" if extra!=1 else ""}. Try a more specific search.</div>'

    html = f'<div class="search-results-wrap">{header}{cards_html}</div>'
    return textwrap.dedent(html).replace('\n', '')


def _render_alternatives_cards(source: dict, products: list[dict]) -> str:
    """Render cheaper alternatives as horizontal cards with savings badges."""
    # Source product info
    source_name  = source.get("name","the selected product") if isinstance(source, dict) else "your order"
    source_price = source.get("price") if isinstance(source, dict) else None
    source_id    = source.get("product_id","") if isinstance(source, dict) else ""
    currency     = source.get("currency","USD") if isinstance(source, dict) else "USD"

    # Filter: must be cheaper AND not the same product
    if source_price is not None:
        candidates = [p for p in products
                      if p.get("price",float("inf")) < source_price
                      and p.get("product_id","") != source_id]
    else:
        candidates = [p for p in products if p.get("product_id","") != source_id]

    shown = candidates[:4] if candidates else products[:4]

    price_str = f" ({_fmt_price(source_price, currency)})" if source_price else ""
    header = f'<div class="alt-header">🔎 Cheaper alternatives to <strong>{source_name}</strong>{price_str}</div>'

    if not shown:
        return f'{header}<div class="alt-empty">No cheaper alternatives found in our catalog at this time. The product may already be the best value in its category.</div>'

    cards_html = ""
    for p in shown:
        pname   = p.get("name","Unknown")
        pprice  = float(p.get("price",0))
        pcur    = p.get("currency","USD")
        rating  = float(p.get("rating",0))
        desc    = p.get("description","")
        short_d = (desc[:75]+"…") if len(desc)>75 else desc
        stars   = "★" * int(round(rating)) + "☆" * (5 - int(round(rating)))
        pid     = p.get("product_id","")
        cat     = p.get("category","")

        savings_html = ""
        if source_price and pprice < source_price:
            saved  = source_price - pprice
            pct    = int((saved / source_price) * 100)
            savings_html = f'<div class="alt-savings">💰 Save {_fmt_price(saved, pcur)} ({pct}% off)</div>'

        # Compile matching selection reasons dynamically
        reasons = []
        if isinstance(source, dict):
            if cat and cat == source.get("category"):
                reasons.append("Same category")
            if p.get("subcategory") and p.get("subcategory") == source.get("subcategory"):
                reasons.append("Similar features")
            if p.get("brand") and p.get("brand") == source.get("brand"):
                reasons.append(f"Same brand ({p.get('brand')})")
            if source_price and pprice < source_price:
                reasons.append("Cheaper price")
            if rating >= float(source.get("rating", 0.0)):
                reasons.append("Top rated")

        reasons_html = ""
        if reasons:
            reasons_html = f"""
            <div class="alt-reasons">
                💡 Recommended because: {", ".join(reasons)}
            </div>"""

        # Category colour for icon background
        cat_colors = {
            "Electronics": "#eef2ff", "Footwear": "#ecfdf5",
            "Kitchen": "#fff7ed", "Outdoors": "#f5f3ff",
        }
        icon_bg = cat_colors.get(cat, "#f3f4f6")

        cards_html += f"""
        <div class="alt-card">
            <div class="alt-card-icon" style="background:{icon_bg};">
                <span>🛍️</span>
                <span class="alt-rating">{stars}</span>
            </div>
            <div class="alt-card-body">
                <div class="alt-prod-name">{pname}</div>
                <div class="alt-prod-desc">{short_d}</div>
                <div class="alt-prod-footer">
                    <span class="alt-price">{_fmt_price(pprice, pcur)}</span>
                    <span class="alt-rating-val">⭐ {rating}/5</span>
                </div>
                {savings_html}
                {reasons_html}
            </div>
        </div>"""


    html = f'<div class="alternatives-wrap">{header}<div class="alt-cards-grid">{cards_html}</div></div>'
    return textwrap.dedent(html).replace('\n', '')


def _render_product_grid_card(prod: dict, button_label: str, button_key: str) -> bool:
    """Render a single product card with standard UI style and return True if clicked."""
    cat_colors_map = {
        "Electronics": ("#4361ee", "#eef2ff"),
        "Footwear":    ("#059669", "#ecfdf5"),
        "Kitchen & Dining": ("#ea580c", "#fff7ed"),
        "Sports & Outdoors":("#7c3aed", "#f5f3ff"),
        "Books & Media":    ("#0891b2", "#ecfeff"),
        "Clothing":    ("#db2777", "#fdf2f8"),
        "Toys & Games":("#d97706", "#fffbeb"),
    }
    
    pid    = prod.get("product_id", "")
    pname  = prod.get("name", "")
    brand  = prod.get("brand", "")
    cat    = prod.get("category", "")
    price  = _fmt_price(prod.get("price", 0), prod.get("currency", "USD"))
    rating = float(prod.get("rating", 0))
    stock  = int(prod.get("stock", 0))
    stars  = "★" * int(round(rating)) + "☆" * (5 - int(round(rating)))
    acc, bg = cat_colors_map.get(cat, ("#6b7280", "#f9fafb"))

    if stock == 0:
        stock_badge = f'<span style="color:#ef4444;font-size:.75rem;font-weight:600;">❌ Out of Stock</span>'
    elif stock <= 10:
        stock_badge = f'<span style="color:#f59e0b;font-size:.75rem;font-weight:600;">⚠️ Only {stock} left</span>'
    else:
        stock_badge = f'<span style="color:#10b981;font-size:.75rem;font-weight:600;">✅ In Stock</span>'

    st.markdown(f"""
    <div style="background:#fff;border:1.5px solid #e2e8f0;border-radius:14px;
                padding:16px;margin-bottom:4px;transition:box-shadow .2s;
                box-shadow:0 1px 4px rgba(0,0,0,.05);">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
            <div style="width:42px;height:42px;border-radius:10px;background:{bg};
                        display:flex;align-items:center;justify-content:center;
                        font-size:1.3rem;flex-shrink:0;">🛍️</div>
            <div style="min-width:0;">
                <div style="font-weight:700;font-size:.88rem;color:#1e293b;
                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{pname[:40]}{'…' if len(pname)>40 else ''}</div>
                <div style="font-size:.75rem;color:#64748b;margin-top:1px;">
                    <span style="font-weight:600;color:{acc};">{brand}</span>
                    &nbsp;·&nbsp;{cat}
                </div>
            </div>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            <span style="font-size:1.1rem;font-weight:800;color:#1e293b;">{price}</span>
            <span style="font-size:.8rem;color:#f59e0b;">{stars} <span style="color:#64748b;">{rating}/5</span></span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;">
            {stock_badge}
            <span style="font-family:monospace;font-size:.72rem;color:#94a3b8;">{pid}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    return st.button(button_label, key=button_key, use_container_width=True)


def _render_product_grid(products: list[dict], key_prefix: str, button_label_func, on_click_callback) -> None:
    """Render a list of products in a 2-column grid."""
    for row_start in range(0, len(products), 2):
        row_prods = products[row_start : row_start + 2]
        cols = st.columns(len(row_prods))
        for col, prod in zip(cols, row_prods):
            pid = prod.get("product_id", "")
            with col:
                btn_label = button_label_func(pid)
                btn_key = f"{key_prefix}_{pid}"
                if _render_product_grid_card(prod, btn_label, btn_key):
                    on_click_callback(pid)


# ══════════════════════════════════════════════════════════════════════════════
# CHAT MESSAGE RENDERING
# ══════════════════════════════════════════════════════════════════════════════

def _render_message(msg: dict, msg_idx: int) -> None:
    """Render a single chat message using the correct rich card or text bubble."""
    role    = msg["role"]
    ts      = msg["ts"]
    intent  = msg.get("intent","text")
    content = msg.get("content","")
    data    = msg.get("data",{})

    if role == "user":
        st.markdown(f"""
        <div class="msg-row msg-user">
            <div class="msg-body msg-body-right">
                <div class="msg-bubble bubble-user">{_md2html(content)}</div>
                <div class="msg-meta msg-meta-right">{ts} ✓✓</div>
            </div>
        </div>""", unsafe_allow_html=True)
        return

    # ── Assistant messages ─────────────────────────────────────────────────
    st.markdown(f"""
    <div class="msg-row msg-bot">
        <div class="msg-bot-orb">🤖</div>
        <div class="msg-body">""", unsafe_allow_html=True)

    # NEW: Collapsible tool steps
    tool_calls = data.get("tool_calls", [])
    if tool_calls:
        # Filter out sentinel tools
        valid_tools = [tc for tc in tool_calls if not tc.get("tool", "").startswith("__")]
        if valid_tools:
            with st.expander("⚙️ Agent Reasoning (Tool Execution)", key=f"expander_{msg_idx}"):
                for tc in valid_tools:
                    t_name = tc.get("tool","")
                    t_args = tc.get("args", {})
                    success = tc.get("success", True)
                    badge = "✅" if success else "❌"
                    args_str = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in t_args.values())
                    st.markdown(f"**{badge}** `{t_name}({args_str})`")

    if intent == "order_found" and data.get("order"):
        # Text intro + rich order card
        st.markdown(f"""
        <div class="msg-bubble bubble-bot" style="margin-bottom:10px;">
            {_md2html(content.split(chr(10))[0])}
        </div>""", unsafe_allow_html=True)
        st.markdown(_render_order_card(data["order"]), unsafe_allow_html=True)

    elif intent == "product_found" and data.get("products"):
        st.markdown(f"""
        <div class="msg-bubble bubble-bot" style="margin-bottom:10px;">
            Here are the details for the product you asked about:
        </div>""", unsafe_allow_html=True)
        st.markdown(_render_product_card(data["products"][0]), unsafe_allow_html=True)

    elif intent == "search_results" and data.get("products"):
        st.markdown(_render_search_cards(data["products"]), unsafe_allow_html=True)

    elif intent == "alternatives" and data.get("source") is not None:
        st.markdown(f"""
        <div class="msg-bubble bubble-bot" style="margin-bottom:12px;">
            {_md2html(content)}
        </div>""", unsafe_allow_html=True)
        st.markdown(_render_alternatives_cards(data["source"], data.get("products",[])),
                    unsafe_allow_html=True)


    else:
        # Plain text bubble for: unsupported, needs_order_id, not_found, error, text
        st.markdown(f"""
        <div class="msg-bubble bubble-bot">{_md2html(content)}</div>""",
                    unsafe_allow_html=True)

        if intent == "unsupported":
            st.markdown('<div class="chip-marker"></div>', unsafe_allow_html=True)
            chips = [
                ("📦 Track Order", "Sure!\n\nPlease enter your Order ID.\n\nExample:\nORD-10021"),
                ("🔍 Search Products", "Tell me what product you're looking for.\n\nExample:\nWireless headphones"),
                ("🛍️ Product Details", "Please enter the Product ID or Product Name."),
                ("💰 Cheaper Alternatives", "Tell me the Product ID, Product Name, or Order ID."),
                ("💬 Something Else", "Ask me anything related to orders or products.")
            ]
            cols = st.columns(len(chips))
            for i, (chip_label, reply_text) in enumerate(chips):
                with cols[i]:
                    if st.button(chip_label, key=f"chip_{msg_idx}_{i}", use_container_width=True):
                        _add_bot_text(reply_text)
                        st.session_state.show_landing = False
                        st.rerun()

    st.markdown(f"""
            <div class="msg-meta">{ts}</div>
        </div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# AGENT CALL
# ══════════════════════════════════════════════════════════════════════════════

def _call_agent(user_input: str) -> None:
    """Call the real agent pipeline and append user + assistant messages."""
    _add_user(user_input)

    agent_fn = st.session_state.get("_agent_query")
    if not agent_fn:
        _add_bot_text(
            "⚠️ Backend is not available at the moment. "
            f"Error: {st.session_state.get('_agent_err','Unknown')}",
            "error"
        )
        return

    with st.status("🧠 Agent Reasoning...", expanded=True) as status:
        st.write("🔄 **Understand:** Parsing intent from question...")
        st.write("⚙️ **Choose Tools:** Selecting execution path...")
        try:
            result = agent_fn(user_input)
            st.write("⚡ **Execute:** Calling tools against real data...")
            st.write("📝 **Respond:** Formatting structured response...")
            status.update(label="Response ready", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Error", state="error", expanded=True)
            _add_bot_text(f"⚠️ Unexpected error: {e}", "error")
            return

    # Update context and recent tools dynamically based on actual tool execution
    for tc in result.tool_calls:
        tool_name = tc.get("tool", "")
        args = tc.get("args", {})
        success = tc.get("success", True)
        
        if not tool_name.startswith("__"):
            # Format arguments for UI display
            args_str = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in args.values())
            call_str = f'{tool_name}({args_str})'
            # Insert at beginning with success state
            st.session_state.recent_tools.insert(0, (call_str, _ts(), success))
            
            # Update contexts dynamically
            if tool_name == "get_order" and "order_id" in args:
                st.session_state.ctx_order = args["order_id"]
            elif tool_name == "get_product" and "product_id" in args:
                st.session_state.ctx_product = args["product_id"]
            elif tool_name == "search_products" and "query" in args:
                st.session_state.ctx_search = args["query"]
                
    # Maintain latest 10 calls
    st.session_state.recent_tools = st.session_state.recent_tools[:10]

    # Store message with intent + structured data
    st.session_state.messages.append({
        "role":    "assistant",
        "content": result.text,
        "ts":      _ts(),
        "intent":  result.intent,
        "data": {
            "order":    result.order,
            "products": result.products,
            "source":   result.source,
            "tool_calls": result.tool_calls,
        },
    })
    st.session_state.show_landing = False


def _add_user(text: str) -> None:
    st.session_state.messages.append({
        "role": "user", "content": text,
        "ts": _ts(), "intent": "text", "data": {}
    })

def _add_bot_text(text: str, intent: str = "text") -> None:
    st.session_state.messages.append({
        "role": "assistant", "content": text,
        "ts": _ts(), "intent": intent, "data": {}
    })


# ══════════════════════════════════════════════════════════════════════════════
# QUICK ACTION CARDS
# ══════════════════════════════════════════════════════════════════════════════

def _handle_quick_action(key: str) -> None:
    _QUICK_RESPONSES = {
        "Your Order": (
            "Track my order",
            "Sure! I can help you track your order.\n\nPlease enter your Order ID (for example: ORD-10021)."
        ),
        "Find Products": (
            "Find products",
            "Sure! I'd be happy to help you find a product.\n\nTell me the product name, category, brand, or simply describe what you're looking for.\n\nExamples:\n- Wireless headphones\n- Running shoes\n- Samsung phone\n- Gaming mouse"
        ),
        "Compare Prices": (
            "Compare prices",
            "I can help compare prices for any product.\n\nJust tell me the product name and I'll compare the available options."
        ),
        "Delivery Status": (
            "Check delivery status",
            "I can check your delivery status.\n\nPlease enter your Order ID to continue."
        ),
        "Anything Else": (
            "I need help with something else.",
            "I'm here to help with any shopping-related question.\n\nFeel free to ask about products, orders, deliveries, pricing, recommendations, or anything else."
        ),
    }

    if key in _QUICK_RESPONSES:
        user_msg, bot_msg = _QUICK_RESPONSES[key]
        _add_user(user_msg)
        _add_bot_text(bot_msg)

    # ── Active-card state: one card selected at a time ──────────────────────
    st.session_state.active_card = key

    st.session_state.show_landing = False


def _clear_chat() -> None:
    st.session_state.messages     = []
    st.session_state.show_landing = True

def _new_chat() -> None:
    st.session_state.messages     = []
    st.session_state.ctx_order    = None
    st.session_state.ctx_product  = None
    st.session_state.ctx_search   = None
    st.session_state.recent_tools = []
    st.session_state['_last_msg_count'] = 0


def _render_welcome_hero():
    """Render the chat landing welcome banner."""
    st.markdown("""
    <div class="welcome-row">
        <div class="bot-orb">🤖</div>
        <div class="welcome-body">
            <h2 class="welcome-h2">Hello! How can I help you today?</h2>
            <p class="welcome-p">Choose an option below or ask me anything about your shopping needs.</p>
            <span class="msg-timestamp">Live AI Agent — real data</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    # Backend status banner
    if not st.session_state._agent_ready:
        st.markdown(f"""
        <div class="agent-warn">
            ⚠️ Backend unavailable: {st.session_state.get('_agent_err','Unknown error')}.
            Make sure all backend files are present and run from the project root.
        </div>
        """, unsafe_allow_html=True)


def _render_quick_action_cards():
    """Render the interactive landing option cards."""
    _cards_cfg = [
        ("📦","Your Order",     "Track, manage or view details about your orders","#eef2ff","#4361ee"),
        ("🛍️","Find Products",  "Search for products across categories and brands","#ecfdf5","#059669"),
        ("🏷️","Compare Prices", "Compare prices and find the best deals for you","#fff7ed","#ea580c"),
        ("🚚","Delivery Status","Check delivery status and expected delivery dates","#f5f3ff","#7c3aed"),
    ]
    _c1,_c2,_c3,_c4 = st.columns(4, gap="small")
    for _col,(_ico,_ttl,_dsc,_bg,_acc) in zip([_c1,_c2,_c3,_c4], _cards_cfg):
        with _col:
            _is_active = (st.session_state.active_card == _ttl)
            _card_cls  = "action-card selected" if _is_active else "action-card"
            st.markdown(f"""
            <div class="{_card_cls}">
                <div class="action-icon-wrap" style="background:{_bg};">
                    <span class="action-emoji" style="color:{_acc};">{_ico}</span>
                </div>
                <div class="action-title">{_ttl}</div>
                <div class="action-desc">{_dsc}</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown('<div class="act-trigger"></div>', unsafe_allow_html=True)
            if st.button("",key=f"__qact_{_ttl}",use_container_width=True):
                _handle_quick_action(_ttl); st.rerun()

    _anything_cls = "anything-card selected" if st.session_state.active_card == "Anything Else" else "anything-card"
    st.markdown(f"""
    <div class="{_anything_cls}">
        <div class="anything-left">
            <div class="anything-bubble"><span class="anything-emoji">💬</span></div>
            <div class="anything-text">
                <div class="anything-title">Anything Else?</div>
                <div class="anything-sub">Ask me anything — orders, products, alternatives!</div>
            </div>
        </div>
        <div class="anything-chevron">›</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="any-trigger"></div>', unsafe_allow_html=True)
    if st.button("",key="__qact_anything_else",use_container_width=True,help="Open chat"):
        _handle_quick_action("Anything Else"); st.rerun()

    st.markdown("""
    <div class="chat-hint">
        <span class="hint-dash">— — —</span>
        <span class="hint-text">or type your question below to get started</span>
        <span class="hint-arrow">↗</span>
    </div>
    """, unsafe_allow_html=True)


def _render_chat_history():
    """Render message bubbles from session history."""
    if st.session_state.messages:
        st.markdown('<div class="chat-history-spacing" style="margin-top: 40px; border-top: 1px solid #e2e8f0; padding-top: 20px;"></div>', unsafe_allow_html=True)
        for idx, _msg in enumerate(st.session_state.messages):
            _render_message(_msg, idx)
            
        st.markdown('<div id="chat-end" style="height: 90px;"></div>', unsafe_allow_html=True)


def _render_chat_composer():
    """Render message text input form with submit handler."""
    with st.form(key="__msg_form", clear_on_submit=True):
        _cols = st.columns([12, 1, 1])
        with _cols[0]:
            _user_input = st.text_input(
                "",
                placeholder="Type your message here...",
                key="__chat_input_field",
                label_visibility="collapsed"
            )
        with _cols[1]:
            st.markdown(
                '<button type="button" id="speech-mic-btn" class="custom-mic-btn" title="Voice Input">'
                '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path>'
                '<path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>'
                '<line x1="12" y1="19" x2="12" y2="22"></line>'
                '</svg></button>',
                unsafe_allow_html=True
            )
        with _cols[2]:
            _submitted = st.form_submit_button("Send")
            
    if _submitted and _user_input:
        _call_agent(_user_input)
        st.rerun()


@st.dialog("Start New Chat?")
def confirm_new_chat():
    st.write("Your current conversation will be cleared.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with c2:
        if st.button("New Chat", type="primary", use_container_width=True):
            _new_chat()
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# LEFT SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div class="brand-wrap">
        <div class="brand-logo">🤖</div>
        <div class="brand-copy">
            <div class="brand-name">ShopSmart AI</div>
            <div class="brand-sub">Shopping Assistant</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    _nav_items = [
        ("💬", "Chat Assistant"),
        ("📦", "Orders"),
        ("🛍️", "Products"),
        ("🔍", "Search"),
        ("📋", "Logs"),
        ("⚙️", "Settings"),
    ]
    _active = st.session_state.active_nav

    # Render each nav item as: wrapper div → HTML li → invisible Streamlit button
    # The CSS makes the button an absolute overlay over its wrapper, preserving
    # the visual design while making the full row area clickable.
    for _ico, _lbl in _nav_items:
        _cls = "nav-li active" if _lbl == _active else "nav-li"
        st.markdown(f"""
        <div class="nav-item-wrap">
            <div class="{_cls}">
                <span class="nav-icon">{_ico}</span>
                <span class="nav-label">{_lbl}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button(_lbl, key=f"__navbtn_{_lbl}", use_container_width=True):
            st.session_state.active_nav = _lbl
            if _lbl == "Chat Assistant":
                pass  # stay in chat
            st.rerun()

    _msg_cnt   = len(st.session_state.messages)
    _ready_txt = f"Ready to help • {_msg_cnt} msg{'s' if _msg_cnt!=1 else ''}" if _msg_cnt else "Ready to assist you"
    _online    = "🟢 Online" if st.session_state._agent_ready else "🔴 Backend unavailable"
    st.markdown(f"""
    <div class="agent-status">
        <div class="agent-info">
            <div class="agent-title">AI Agent Status</div>
            <div class="agent-row">
                <span class="agent-dot"></span>
                <span class="agent-online">{_online}</span>
            </div>
            <div class="agent-ready">{_ready_txt}</div>
        </div>
        <div class="agent-avatar">🤖</div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TOP BAR
# ══════════════════════════════════════════════════════════════════════════════
_tb_l, _tb_r = st.columns([3, 1])
with _tb_l:
    st.markdown("""
    <div class="topbar-block">
        <div class="topbar-title">AI Shopping Assistant</div>
        <div class="topbar-sub">Powered by live backend — real data from mock_data.json</div>
    </div>
    """, unsafe_allow_html=True)
with _tb_r:
    _cr1, _cr2, _cr3 = st.columns([2, 2, 1])
    with _cr1:
        st.markdown('<div class="topbar-clear-wrap">', unsafe_allow_html=True)
        if st.button("🗑️ Clear", key="__clear_btn", use_container_width=True):
            _clear_chat(); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with _cr2:
        st.markdown('<div class="topbar-clear-wrap">', unsafe_allow_html=True)
        _export_data = "\\n\\n".join(f"[{m['ts']}] {m['role'].upper()}: {m['content']}" for m in st.session_state.messages)
        st.download_button("💾 Export", data=_export_data, file_name="chat_export.txt", use_container_width=True, key="__export_download_btn")
        st.markdown('</div>', unsafe_allow_html=True)
    with _cr3:
        st.markdown('<div class="topbar-avatar-pill">AS</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
_center, _right = st.columns([1.9, 1.1], gap="large")

# ─────────────────────────────────────────────────────────────────────────────
# HELPER — load all data directly from mock_data.json (same source as tools)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _load_all_orders() -> list:
    return load_all_orders()

@st.cache_data(show_spinner=False)
def _load_all_products() -> list:
    return load_all_products()


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: ORDERS
# ─────────────────────────────────────────────────────────────────────────────
def _render_orders_page():
    """Full Orders browser — list view + detail panel."""
    all_orders = _load_all_orders()
    selected_id = st.session_state.orders_selected_id

    # ── Page header ───────────────────────────────────────────────────────────
    st.markdown("""
    <div style="padding:18px 0 8px 0;">
        <h2 style="margin:0;font-size:1.55rem;font-weight:700;color:#1e293b;">📦 Orders</h2>
        <p style="margin:4px 0 0 0;font-size:0.88rem;color:#64748b;">All orders from your store — click any row to view full details.</p>
    </div>
    """, unsafe_allow_html=True)

    # ── If an order is selected, show detail view ─────────────────────────────
    if selected_id:
        order = next((o for o in all_orders if o["order_id"] == selected_id), None)
        if order:
            # Back button
            if st.button("← Back to Orders", key="__orders_back"):
                st.session_state.orders_selected_id = None
                st.rerun()

            st.markdown(_render_order_card(order), unsafe_allow_html=True)

            # Track Order button
            st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)
            if st.button(f"🚀 Track Order {order['order_id']}", key="__track_order_btn",
                         type="primary", use_container_width=False):
                st.session_state.orders_selected_id = None
                st.session_state.active_nav = "Chat Assistant"
                st.session_state.show_landing = False
                _call_agent(f"Track my order {order['order_id']}")
                st.rerun()
            return

    # ── List view ─────────────────────────────────────────────────────────────
    # Table header
    st.markdown("""
    <div style="display:grid;grid-template-columns:110px 1fr 130px 90px;gap:0;
                background:#f1f5f9;border:1px solid #e2e8f0;border-radius:10px 10px 0 0;
                padding:10px 16px;font-size:0.78rem;font-weight:700;color:#64748b;
                text-transform:uppercase;letter-spacing:.05em;margin-top:8px;">
        <div>Order ID</div><div>Customer</div><div>Status</div><div style="text-align:right;">Total</div>
    </div>
    """, unsafe_allow_html=True)

    for idx, order in enumerate(all_orders):
        oid      = order.get("order_id", "")
        cname    = order.get("customer", {}).get("name", "—")
        status   = order.get("status", "")
        total    = _fmt_price(order.get("total", 0))
        placed   = _fmt_date_short(order.get("placed_at", ""))
        emoji, label, color, bg, border = _STATUS_CFG.get(
            status,
            ("📋", status.replace("_", " ").title(), "#6b7280", "#f9fafb", "#d1d5db")
        )
        is_last  = (idx == len(all_orders) - 1)
        row_radius = "0 0 10px 10px" if is_last else "0"

        st.markdown(f"""
        <div style="display:grid;grid-template-columns:110px 1fr 130px 90px;gap:0;
                    background:#fff;border:1px solid #e2e8f0;border-top:none;
                    padding:12px 16px;font-size:0.88rem;color:#1e293b;
                    border-radius:{row_radius};">
            <div style="font-weight:600;color:#4361ee;font-family:monospace;">{oid}</div>
            <div>
                <div style="font-weight:600;">{cname}</div>
                <div style="font-size:0.75rem;color:#94a3b8;margin-top:1px;">{placed}</div>
            </div>
            <div><span style="background:{bg};color:{color};border:1px solid {border};
                              border-radius:20px;padding:3px 10px;font-size:0.77rem;font-weight:600;">
                {emoji} {label}</span></div>
            <div style="text-align:right;font-weight:700;">{total}</div>
        </div>
        """, unsafe_allow_html=True)

        # Invisible Streamlit button to capture click
        if st.button(f"View {oid}", key=f"__order_row_{oid}",
                     use_container_width=True):
            st.session_state.orders_selected_id = oid
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: PRODUCTS
# ─────────────────────────────────────────────────────────────────────────────
def _render_products_page():
    """Full Products catalog — card grid + detail panel."""
    all_products = _load_all_products()
    selected_id  = st.session_state.products_selected_id

    # ── Page header ───────────────────────────────────────────────────────────
    st.markdown("""
    <div style="padding:18px 0 8px 0;">
        <h2 style="margin:0;font-size:1.55rem;font-weight:700;color:#1e293b;">🛍️ Products</h2>
        <p style="margin:4px 0 0 0;font-size:0.88rem;color:#64748b;">Full product catalog — click any card to ask the AI about it.</p>
    </div>
    """, unsafe_allow_html=True)

    # ── If a product is selected, go straight to chatbot ─────────────────────
    # (detail view isn't needed; clicking triggers the agent immediately)
    if selected_id:
        prod = next((p for p in all_products if p["product_id"] == selected_id), None)
        if prod:
            st.session_state.products_selected_id = None
            st.session_state.active_nav = "Chat Assistant"
            st.session_state.show_landing = False
            _call_agent(f"Tell me about product {prod['product_id']}")
            st.rerun()

    # ── Category filter pills ─────────────────────────────────────────────────
    categories = sorted(set(p.get("category", "") for p in all_products))
    if "_prod_cat_filter" not in st.session_state:
        st.session_state._prod_cat_filter = "All"

    cat_options = ["All"] + categories
    cols_filter = st.columns(len(cat_options))
    for ci, cat in enumerate(cat_options):
        active_cat = st.session_state._prod_cat_filter
        btn_style  = "primary" if cat == active_cat else "secondary"
        with cols_filter[ci]:
            if st.button(cat, key=f"__cat_filter_{ci}", type=btn_style,
                         use_container_width=True):
                st.session_state._prod_cat_filter = cat
                st.rerun()

    # Apply filter
    active_filter = st.session_state._prod_cat_filter
    displayed = all_products if active_filter == "All" else [
        p for p in all_products if p.get("category", "") == active_filter
    ]

    st.markdown(f"<div style='font-size:0.82rem;color:#64748b;margin:10px 0 6px 2px;'>"
                f"Showing <strong>{len(displayed)}</strong> product{'s' if len(displayed)!=1 else ''}"
                f"</div>", unsafe_allow_html=True)

    # ── Product cards grid — 2 per row ────────────────────────────────────────
    def products_btn_label(pid):
        return f"Ask about {pid}"
        
    def products_on_click(pid):
        st.session_state.products_selected_id = pid
        st.rerun()

    _render_product_grid(displayed, "__prod_btn", products_btn_label, products_on_click)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: SEARCH
# ─────────────────────────────────────────────────────────────────────────────
def _render_search_page():
    """Full Product Search Explorer — search bar + results view."""
    all_products = _load_all_products()

    # Inject smooth fade-in animations and pulse styles
    st.markdown("""
    <style>
    @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.6; }
        50% { transform: scale(1.05); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.6; }
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .stColumn, .product-card-anim {
        animation: fadeIn 0.35s ease-out;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Hero Header Section ───────────────────────────────────────────────────
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 26px 22px; border-radius: 16px; margin-bottom: 20px; color: white; box-shadow: 0 4px 20px rgba(0,0,0,0.06);">
        <h2 style="margin:0;font-size:1.65rem;font-weight:800;color:#ffffff;display:flex;align-items:center;gap:10px;">🔍 AI Product Search</h2>
        <p style="margin:6px 0 0 0;font-size:0.88rem;color:#94a3b8;opacity:0.95;">Instantly search products by name, brand, category or product ID.</p>
    </div>
    """, unsafe_allow_html=True)

    # Search bar input
    query = st.text_input(
        "Search Products",
        placeholder="Search products...",
        label_visibility="collapsed",
        key="search_input_explorer"
    )

    # Auto-focus Javascript inject
    st.components.v1.html("""
    <script>
    setTimeout(function() {
        const doc = window.parent.document;
        const input = doc.querySelector('input[placeholder="Search products..."]');
        if (input && doc.activeElement !== input) {
            input.focus();
        }
    }, 150);
    </script>
    """, height=0)

    query_clean = query.strip().lower()

    # Live filtering loading pulse indicator
    if query_clean:
        st.markdown("""
        <div style="display:flex; align-items:center; gap:8px; font-size:0.78rem; color:#64748b; margin-top:-10px; margin-bottom:12px;">
            <span style="width:7px; height:7px; background-color:#10b981; border-radius:50%; display:inline-block; animation: pulse 1.2s infinite ease-in-out;"></span>
            <span>Live filtering active...</span>
        </div>
        """, unsafe_allow_html=True)

    if query_clean:
        matched_products = [
            p for p in all_products
            if query_clean in p.get("name", "").lower()
            or query_clean in p.get("brand", "").lower()
            or query_clean in p.get("category", "").lower()
            or query_clean in p.get("product_id", "").lower()
            or any(query_clean in t.lower() for t in p.get("tags", []))
        ]
    else:
        matched_products = all_products

    # ── Empty State ───────────────────────────────────────────────────────────
    if query_clean and not matched_products:
        st.markdown(f"""
        <div style="padding: 32px 20px; background: #ffffff; border: 1.5px dashed #cbd5e1; border-radius: 16px; margin-top: 24px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.01);">
            <div style="font-size: 2.2rem; margin-bottom: 10px;">🔍</div>
            <h3 style="margin:0 0 4px 0;font-size:1.15rem;font-weight:700;color:#1e293b;">No products found</h3>
            <p style="margin:0 0 16px 0;font-size:0.88rem;color:#64748b;">We couldn't find any matching product.</p>
            <div style="text-align: left; max-width: 300px; margin: 0 auto; background: #f8fafc; padding: 14px 18px; border-radius: 12px; border: 1px solid #e2e8f0;">
                <div style="font-weight:700; font-size:0.78rem; color:#475569; margin-bottom: 6px; text-transform:uppercase; letter-spacing:0.03em;">💡 You may try:</div>
                <ul style="margin:0; padding-left: 20px; font-size: 0.85rem; color: #475569; line-height: 1.6;">
                    <li>headphones</li>
                    <li>mouse</li>
                    <li>power bank</li>
                    <li>Samsung</li>
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Display Results ───────────────────────────────────────────────────────
    if query_clean:
        st.markdown(f"""
        <div style="margin: 24px 0 12px 0;">
            <h3 style="margin:0;font-size:1.25rem;font-weight:700;color:#1e293b;">Results for "{query}"</h3>
            <p style="margin:2px 0 0 0;font-size:0.85rem;color:#64748b;">Showing {len(matched_products)} matching product{'s' if len(matched_products) != 1 else ''}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="margin: 28px 0 12px 0;">
            <h3 style="margin:0;font-size:1.25rem;font-weight:700;color:#1e293b;">⭐ Featured Products</h3>
            <p style="margin:2px 0 0 0;font-size:0.85rem;color:#64748b;">Showing all {len(matched_products)} products</p>
        </div>
        """, unsafe_allow_html=True)

    # ── Product cards grid — 2 per row ────────────────────────────────────────
    def search_btn_label(pid):
        return "💬 Ask AI about this Product"
        
    def search_on_click(pid):
        st.session_state.active_nav = "Chat Assistant"
        st.session_state.show_landing = False
        _call_agent(f"Tell me about product {pid}")
        st.rerun()

    _render_product_grid(matched_products, "__search_prod_btn", search_btn_label, search_on_click)


# ─────────────────────────────────────────────────────────────────────────────
# CENTER COLUMN
# ─────────────────────────────────────────────────────────────────────────────
with _center:
    # ════════════ ROUTE BY ACTIVE NAV ════════════
    _nav = st.session_state.active_nav

    if _nav == "Orders":
        _render_orders_page()
        st.stop()

    if _nav == "Products":
        _render_products_page()
        st.stop()

    if _nav == "Search":
        _render_search_page()
        st.stop()

    # ════════════ LANDING VIEW (Chat Assistant) ════════════
    _render_welcome_hero()
    _render_quick_action_cards()

    # ════════════ CHAT VIEW ════════════
    _render_chat_history()

    # ── Chat Composer ───────────────────────────────────────────────────────
    _render_chat_composer()

    # ── Chat Composer is rendered BELOW both columns ────────────────────────
    # (position:fixed works correctly outside column stacking contexts)

    # Voice input logic via Web Speech API + card hover binding
    st.components.v1.html("""
    <script>
    const parent = window.parent.document;
    const micBtn = parent.getElementById('speech-mic-btn');
    const inputField = parent.querySelector('[data-testid="stForm"] input[type="text"]');

    if (micBtn && inputField && !micBtn.hasAttribute('data-bound')) {
        micBtn.setAttribute('data-bound', 'true');
        
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            micBtn.onclick = () => alert('Speech recognition is not supported in this browser. Try Chrome or Edge.');
        } else {
            const recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            
            recognition.onstart = () => {
                micBtn.classList.add('recording');
            };
            
            recognition.onend = () => {
                micBtn.classList.remove('recording');
            };
            
            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                
                // Append space if there's already text
                const currentValue = inputField.value;
                const newValue = currentValue ? currentValue + ' ' + transcript : transcript;
                
                // Set the value of the React input
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                if (nativeInputValueSetter) {
                    nativeInputValueSetter.call(inputField, newValue);
                    // Dispatch input event for React
                    const ev2 = new Event('input', { bubbles: true});
                    inputField.dispatchEvent(ev2);
                } else {
                    // Fallback
                    inputField.value = newValue;
                }
            };
            
            micBtn.onclick = (e) => {
                e.preventDefault();
                if (micBtn.classList.contains('recording')) {
                    recognition.stop();
                } else {
                    recognition.start();
                }
            };
        }
    }

    // ── Card hover binding ────────────────────────────────────────────────────
    // Bind mouseenter/mouseleave on the entire column so every pixel inside
    // the card (including empty space) keeps the hover state active.
    (function bindCardHovers() {
        const doc = window.parent.document;

        function bindActionCards() {
            const cols = doc.querySelectorAll('[data-testid="stColumn"]:has(> [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] .action-card)');
            cols.forEach(function(col) {
                if (col.hasAttribute('data-hover-bound')) return;
                col.setAttribute('data-hover-bound', 'true');
                const card = col.querySelector('.action-card');
                if (!card) return;
                col.addEventListener('mouseenter', function() { card.classList.add('hovered'); });
                col.addEventListener('mouseleave', function() { card.classList.remove('hovered'); });
            });
        }

        function bindAnythingElse() {
            const anyBtns = doc.querySelectorAll(
                '[data-testid="stElementContainer"]:has(.any-trigger) + [data-testid="stElementContainer"] button'
            );
            anyBtns.forEach(function(btn) {
                if (btn.hasAttribute('data-hover-bound')) return;
                btn.setAttribute('data-hover-bound', 'true');
                const anyCard = doc.querySelector('.anything-card');
                if (!anyCard) return;
                btn.addEventListener('mouseenter', function() { anyCard.classList.add('hovered'); });
                btn.addEventListener('mouseleave', function() { anyCard.classList.remove('hovered'); });
            });
        }

        bindActionCards();
        bindAnythingElse();

        // Re-bind when Streamlit re-renders DOM nodes (they lose the data-hover-bound attr)
        if (!doc.querySelector('[data-click-observer]')) {
            const sentinel = doc.createElement('div');
            sentinel.setAttribute('data-click-observer', '1');
            sentinel.style.display = 'none';
            doc.body.appendChild(sentinel);
            new MutationObserver(function() {
                bindActionCards();
                bindAnythingElse();
            }).observe(doc.body, { childList: true, subtree: true });
        }
    })();

    // ── Fixed input bar: pin to center column ────────────────────────────────
    // Reads the live bounding rect of the centre column and applies it to the
    // fixed-position form wrapper so it stays perfectly aligned at all sizes.
    (function pinInputBar() {
        const doc = window.parent.document;

        function applyPin() {
            // The form's wrapping element-container
            const formWrap = doc.querySelector('div.element-container:has([data-testid="stForm"])');
            if (!formWrap) return;

            // Find the center column: the first stColumn inside stHorizontalBlock
            // that contains the stForm (we identify it by the stForm being a descendant)
            const allCols = doc.querySelectorAll('[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]');
            let centerCol = null;
            for (const col of allCols) {
                if (col.querySelector('[data-testid="stForm"]')) { centerCol = col; break; }
            }
            if (!centerCol) return;

            const rect = centerCol.getBoundingClientRect();
            formWrap.style.left   = rect.left + 'px';
            formWrap.style.width  = rect.width + 'px';
            formWrap.style.bottom = '0';
        }

        applyPin();
        window.parent.addEventListener('resize', applyPin);

        // Also re-apply after Streamlit rerenders
        new MutationObserver(applyPin).observe(doc.body, { childList: true, subtree: true });
    })();
    </script>
    """, height=0)

    # Auto-scroll script
    _current_msg_count = len(st.session_state.messages)
    _last_msg_count = st.session_state.get('_last_msg_count', 0)
    
    if _current_msg_count > _last_msg_count:
        st.session_state['_last_msg_count'] = _current_msg_count
        import time
        _js_id = int(time.time() * 1000)
        from streamlit.components.v1 import html as _st_html
        _st_html(f"""<script id="scroll-js-{_js_id}">
        setTimeout(function(){{
            function doScroll() {{
                // Scroll the main container to the absolute bottom
                var container = parent.document.querySelector('[data-testid="stAppViewContainer"]');
                if (container) {{
                    container.scrollTo({{
                        top: container.scrollHeight,
                        behavior: 'smooth'
                    }});
                }}
                // Fallback scroll to chat-end element
                var el = parent.document.getElementById('chat-end');
                if (el) {{
                    el.scrollIntoView({{behavior: 'smooth', block: 'end'}});
                }}
            }}
            
            // Execute scroll immediately and at multiple intervals to handle Streamlit rendering latency
            doScroll();
            [50, 150, 300, 500, 800, 1200].forEach(function(t) {{
                setTimeout(doScroll, t);
            }});
            
            // Focus correct restored input field
            var input = parent.document.querySelector('[data-testid="stForm"] input[type="text"]');
            if (input) {{
                input.focus();
            }}
        }}, 50);
        </script>""", height=0)



# ─────────────────────────────────────────────────────────────────────────────
# RIGHT COLUMN — dynamic panel
# ─────────────────────────────────────────────────────────────────────────────
with _right:
    try:
        with open("ai_agent.jpg", "rb") as img_f:
            img_base64 = base64.b64encode(img_f.read()).decode("utf-8")
        st.markdown(f"""
        <div class="agent-image-container">
            <img src="data:image/jpeg;base64,{img_base64}" class="agent-image" alt="AI Agent" />
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"Could not load AI Agent welcome image: {e}")


