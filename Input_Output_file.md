# ShopSmart AI — Input / Output Examples

---

## 1. Where Is My Order?

**Input**
```
Where is my order ORD-10021?
```

**Output**
```
📦  Order ORD-10021
──────────────────────────────────────────────────
Customer     : Emily Carter
Status       : ✅ Delivered

📅  Dates
  • Placed              : 10 June 2026 at 9:14 AM UTC
  • Estimated Delivery  : 14 June 2026
  • Delivered On        : 13 June 2026 at 2:32 PM UTC

🛍️  Items Ordered
  • Sony WH-1000XM5 Wireless Headphones × 1  —  $349.99

💰  Pricing
  • Subtotal    : $349.99
  • Shipping    : $0.00
  • Tax         : $28.87
  • Total       : $378.86

📍  Delivery Details
  • Ship to  : 42 Maple Avenue, Austin, TX 78701
  • Payment  : Visa ending in 4821
  • Tracking : 1Z999AA10123456784
```

---

## 2. Product Details

**Input**
```
Tell me about PROD-001
```

**Output**
```
🛍️  Sony WH-1000XM5 Wireless Headphones
──────────────────────────────────────────────────
Brand      : Sony
Category   : Electronics › Audio
Price      : $349.99
Rating     : ★★★★★  4.8/5.0
Stock      : ✅ In Stock (42 units)

📝  Description
  Industry-leading noise cancelling with two processors and eight microphones.
  Up to 30-hour battery life. Crystal clear hands-free calling.

🏷️  Tags: noise-cancelling, wireless, bluetooth, premium-audio, headphones
📦  SKU: WH1000XM5-BLK
```

---

**Input**
```
Tell me about PROD-010
```

**Output**
```
🛍️  Kindle Paperwhite (11th Generation)
──────────────────────────────────────────────────
Brand      : Amazon
Category   : Books & Media › E-Readers
Price      : $139.99
Rating     : ★★★★★  4.8/5.0
Stock      : ✅ In Stock (200 units)

📝  Description
  6.8" display with thinner borders. Adjustable warm light.
  10 weeks of battery life. Waterproof (IPX8). 8 GB storage.

🏷️  Tags: e-reader, kindle, waterproof, 6.8-inch, adjustable-warm-light
📦  SKU: KINDLE-PW-11G-8GB
```

---

## 3. Search Products

**Input**
```
Find me wireless headphones
```

**Output**
```
🔍  Found 4 products:
──────────────────────────────────────────────────
1. Sony WH-1000XM5 Wireless Headphones
   💲 $349.99   ⭐ 4.8/5.0   Electronics › Audio
   Brand: Sony
   Industry-leading noise cancelling with two processors and eight microphones. Up to 30-hour battery l…

2. Bose QuietComfort 45 Headphones
   💲 $279.99   ⭐ 4.6/5.0   Electronics › Audio
   Brand: Bose
   Acclaimed noise cancellation technology. TriPort acoustic architecture for balanced audio. 24-hour b…

3. Logitech MX Master 3S Wireless Mouse
   💲 $99.99   ⭐ 4.8/5.0   Electronics › Peripherals
   Brand: Logitech
   8K DPI sensor works on any surface, including glass. MagSpeed electromagnetic scroll wheel. Silent c…

4. Apple AirPods Pro (2nd Generation)
   💲 $249.00   ⭐ 4.7/5.0   Electronics › Audio
   Brand: Apple
   Active Noise Cancellation, Adaptive Transparency, Personalized Spatial Audio. Up to 6 hours of liste…
```

---

**Input**
```
Search for running shoes
```

**Output**
```
🔍  Found 2 products:
──────────────────────────────────────────────────
1. Nike Air Zoom Pegasus 40 Running Shoes
   💲 $134.99   ⭐ 4.5/5.0   Footwear › Athletic
   Brand: Nike
   Responsive foam cushioning for a smooth, fast ride. Wider toe box for a more natural fit. Engineered…

2. Adidas Ultraboost 23 Running Shoes
   💲 $189.99   ⭐ 4.6/5.0   Footwear › Athletic
   Brand: Adidas
   BOOST midsole technology returns energy with every step. Primeknit+ upper adapts to your foot shape.…
```

---

## 4. Track Your Order

**Input**
```
Track my order ORD-10022
```

**Output**
```
📦  Order ORD-10022
──────────────────────────────────────────────────
Customer     : Marcus Webb
Status       : 🚚 Shipped

📅  Dates
  • Placed              : 20 June 2026 at 2:05 PM UTC
  • Estimated Delivery  : 25 June 2026

🛍️  Items Ordered
  • Samsung 65" QLED 4K Smart TV × 1  —  $1,199.99
  • Logitech MX Master 3S Wireless Mouse × 1  —  $99.99

💰  Pricing
  • Subtotal    : $1,299.98
  • Shipping    : $0.00
  • Tax         : $107.25
  • Total       : $1,407.23

📍  Delivery Details
  • Ship to  : 17 Oak Street, Denver, CO 80202
  • Payment  : Mastercard ending in 3362
  • Tracking : 1Z999AA10123456785
```

---

**Input**
```
Track my package ORD-10026
```

**Output**
```
📦  Order ORD-10026
──────────────────────────────────────────────────
Customer     : Tom Nguyen
Status       : 🚀 Out for Delivery

📅  Dates
  • Placed              : 21 June 2026 at 11:00 AM UTC
  • Estimated Delivery  : 24 June 2026

🛍️  Items Ordered
  • Apple AirPods Pro (2nd Generation) × 1  —  $249.00
  • Anker 737 Power Bank (PowerCore 24K) × 1  —  $149.99

💰  Pricing
  • Subtotal    : $398.99
  • Shipping    : $0.00
  • Tax         : $32.91
  • Total       : $431.90

📍  Delivery Details
  • Ship to  : 55 Willow Blvd, San Francisco, CA 94105
  • Payment  : Visa ending in 5599
  • Tracking : 1Z999AA10123456787
```

---

**Input**
```
Where is my order ORD-99999?
```

**Output**
```
😕  I wasn't able to find an order with the ID ORD-99999.

Please double-check the order ID and try again. Your order ID can be found
in your confirmation email (it looks like ORD-XXXXX).

If you believe this is an error, please contact our support team.
```

---

## 5. Cheaper Products

**Input**
```
Show me cheaper alternatives to PROD-001
```

**Output**
```
🔎  Looking for alternatives to Sony WH-1000XM5 Wireless Headphones ($349.99):
──────────────────────────────────────────────────
1. Bose QuietComfort 45 Headphones
   💲 $279.99   ⭐ 4.6/5.0  💰 Save $70.00
   Acclaimed noise cancellation technology. TriPort acoustic architecture for balanced audio.…

2. Apple AirPods Pro (2nd Generation)
   💲 $249.00   ⭐ 4.7/5.0  💰 Save $100.99
   Active Noise Cancellation, Adaptive Transparency, Personalized Spatial Audio. Up to 6 hour…

3. Logitech MX Master 3S Wireless Mouse
   💲 $99.99   ⭐ 4.8/5.0  💰 Save $250.00
   8K DPI sensor works on any surface, including glass. MagSpeed electromagnetic scroll wheel…

4. Anker 737 Power Bank (PowerCore 24K)
   💲 $149.99   ⭐ 4.7/5.0  💰 Save $200.00
   140W maximum output to charge a MacBook. 24,000 mAh capacity for 1.4 iPhone 14 Pro Max cha…
```

---

**Input**
```
Is there a budget option instead of the Vitamix 5200 Blender?
```

**Output**
```
🔎  Looking for alternatives to Vitamix 5200 Blender Professional Grade ($449.95):
──────────────────────────────────────────────────
1. Instant Pot Duo 7-in-1 Electric Pressure Cooker
   💲 $89.95   ⭐ 4.7/5.0  💰 Save $360.00
   7-in-1 multi-use: Pressure Cooker, Slow Cooker, Rice Cooker, Steamer, Sauté Pan, Yogurt Ma…

2. Ninja Air Fryer Pro 4-in-1
   💲 $119.99   ⭐ 4.6/5.0  💰 Save $329.96
   Up to 75% less fat than traditional frying. 4-in-1 versatility: Air Fry, Roast, Reheat, De…
```

---

## 6. Compare Price

**Input**
```
Tell me about ORD-10021 and PROD-004
```

**Output**
```
📦  Order ORD-10021
──────────────────────────────────────────────────
Customer     : Emily Carter
Status       : ✅ Delivered

📅  Dates
  • Placed              : 10 June 2026 at 9:14 AM UTC
  • Estimated Delivery  : 14 June 2026
  • Delivered On        : 13 June 2026 at 2:32 PM UTC

🛍️  Items Ordered
  • Sony WH-1000XM5 Wireless Headphones × 1  —  $349.99

💰  Pricing
  • Subtotal    : $349.99
  • Shipping    : $0.00
  • Tax         : $28.87
  • Total       : $378.86

📍  Delivery Details
  • Ship to  : 42 Maple Avenue, Austin, TX 78701
  • Payment  : Visa ending in 4821
  • Tracking : 1Z999AA10123456784

══════════════════════════════════════════════════

You also asked about this product:

🛍️  Samsung 65" QLED 4K Smart TV
──────────────────────────────────────────────────
Brand      : Samsung
Category   : Electronics › Televisions
Price      : $1,199.99
Rating     : ★★★★☆  4.5/5.0
Stock      : ✅ In Stock (12 units)

📝  Description
  Quantum Dot technology delivers 100% Color Volume. Real 4K Quantum Processor.
  Ambient Mode+ blends into your home decor.

🏷️  Tags: 4K, QLED, smart-tv, large-screen, HDR
📦  SKU: QN65Q80C
```

---

**Input**
```
Which is the cheapest running shoe you have?
```

**Output**
```
🔍  Found 2 products:
──────────────────────────────────────────────────
1. Nike Air Zoom Pegasus 40 Running Shoes
   💲 $134.99   ⭐ 4.5/5.0   Footwear › Athletic
   Brand: Nike
   Responsive foam cushioning for a smooth, fast ride. Wider toe box for a more natural fit. Engineered…

2. Adidas Ultraboost 23 Running Shoes
   💲 $189.99   ⭐ 4.6/5.0   Footwear › Athletic
   Brand: Adidas
   BOOST midsole technology returns energy with every step. Primeknit+ upper adapts to your foot shape.…
```

*(Nike Air Zoom Pegasus 40 at $134.99 is the cheapest option)*

---

## 7. Gemini API — Tested via Fallback Queries

Queries that do not match any regex rule are sent to **Google Gemini 2.5 Flash** automatically.
The API key is loaded from the `.env` file (`GEMINI_API_KEY`).

---

**Input**
```
Hello
```

**Output** *(Gemini fallback — greeting detected)*
```
👋 Hello! I'm your AI Shopping Assistant.

Here's what I can help you with:

📦 Track or check an order
🔍 Search products
🛍️ View product details
💰 Find cheaper alternatives
💬 Ask anything else about our store

How can I help you today?
```

---

**Input**
```
What is the capital of France?
```

**Output** *(Gemini fallback — off-topic question)*
```
🤔 I couldn't understand your request.

I can help with:

📦 Order tracking
🔍 Product search
🛍️ Product details
💰 Cheaper alternatives
💬 Shopping-related questions

Please try asking in a different way.
```

---

## 8. All Tools at Once — Order + Product + Alternatives

A single query that triggers all 3 tools chained together:
`get_order` → `get_product` → `search_products`

**Input**
```
Is there a cheaper alternative to what I bought in ORD-10028?
```

**Output**
```
✓ Order Found   ✓ Product Identified   ✓ Recommendations Generated

── Section 1 – Order Summary ──────────────────────

  Order ID        : ORD-10028
  Order Status    : 🚚 Shipped
  Delivery Status : ⏳ Estimated Delivery by 27 June 2026
  Order Date      : 22 June 2026
  Total Amount    : $454.63

── Section 2 – Purchased Product ──────────────────

  Product Name : Kindle Paperwhite (11th Generation)
  Product ID   : PROD-010
  Brand        : Amazon
  Category     : Books & Media
  Price        : $139.99
  Description  : 6.8" display with thinner borders. Adjustable warm light.
                 10 weeks of battery life. Waterproof (IPX8). 8 GB storage.

── Section 3 – Tools Called ────────────────────────

  1. get_order(order_id="ORD-10028")
  2. get_product(product_id="PROD-010")
  3. search_products(query="Kindle Paperwhite (11th Generation)")

── Section 4 – Cheaper Recommendations ────────────

  Here are similar or cheaper products matching category Books & Media:

  1. Anker 737 Power Bank (PowerCore 24K)    💲 $149.99  ⭐ 4.7/5.0
  2. Logitech MX Master 3S Wireless Mouse   💲 $99.99   ⭐ 4.8/5.0
```

---

**Input**
```
Is there a cheaper alternative to what I bought in ORD-10021?
```

**Output**
```
✓ Order Found   ✓ Product Identified   ✓ Recommendations Generated

── Section 1 – Order Summary ──────────────────────

  Order ID        : ORD-10021
  Order Status    : ✅ Delivered
  Delivery Status : ✅ Delivered on 13 June 2026
  Order Date      : 10 June 2026
  Total Amount    : $378.86

── Section 2 – Purchased Product ──────────────────

  Product Name : Sony WH-1000XM5 Wireless Headphones
  Product ID   : PROD-001
  Brand        : Sony
  Category     : Electronics
  Price        : $349.99
  Description  : Industry-leading noise cancelling with two processors and
                 eight microphones. Up to 30-hour battery life.

── Section 3 – Tools Called ────────────────────────

  1. get_order(order_id="ORD-10021")
  2. get_product(product_id="PROD-001")
  3. search_products(query="Sony WH-1000XM5 Wireless Headphones")

── Section 4 – Cheaper Recommendations ────────────

  Here are similar or cheaper products matching category Electronics:

  1. Bose QuietComfort 45 Headphones         💲 $279.99  ⭐ 4.6/5.0  💰 Save $70.00
  2. Apple AirPods Pro (2nd Generation)      💲 $249.00  ⭐ 4.7/5.0  💰 Save $100.99
  3. Logitech MX Master 3S Wireless Mouse    💲 $99.99   ⭐ 4.8/5.0  💰 Save $250.00
  4. Anker 737 Power Bank (PowerCore 24K)    💲 $149.99  ⭐ 4.7/5.0  💰 Save $200.00
```

Order + Purchased Product + Alternative Recommendations

A single query that triggers all three tools in sequence:

`get_order` → `get_product` → `search_products`

---

**Input**

```text
Show me my order ORD-10021 and suggest cheaper alternatives.
```

---

**Output**

```text
🤖

⚙️ Agent Reasoning (Tool Execution)

✓ Order Found
✓ Product Identified
✓ Recommendations Generated

──────────────────────────────────────────────────

### Section 1 – Order Summary

• Order ID: ORD-10021

• Order Status: ✅ Delivered

• Delivery Status: ✅ Delivered on 13 June 2026

• Order Date: 10 June 2026

• Total Amount: $378.86

──────────────────────────────────────────────────

### Section 2 – Purchased Product

• Product Name: Sony WH-1000XM5 Wireless Headphones

• Product ID: PROD-001

• Brand: Sony

• Category: Electronics

• Price: $349.99

• Short Description:
Industry-leading noise cancelling with two processors and eight microphones.
Up to 30-hour battery life.
Crystal clear hands-free calling.

──────────────────────────────────────────────────

### Section 3 – Agent Reasoning

The chatbot executed the following tools in order:

1. get_order(order_id="ORD-10021")

2. get_product(product_id="PROD-001")

3. search_products(query="Sony WH-1000XM5 Wireless Headphones")

──────────────────────────────────────────────────

### Section 4 – Recommendations

Here are some similar or cheaper products matching category Electronics and brand Sony.

🔎 Cheaper alternatives to Sony WH-1000XM5 Wireless Headphones ($349.99)

──────────────────────────────────────────────────

🛍️ Bose QuietComfort 45 Headphones

⭐ Rating: 4.6 / 5

💲 Price: $279.99

💰 Save: $70.00 (20% off)

Acclaimed noise cancellation technology.
TriPort acoustic architecture for balanced audio.

💡 Recommended because:
• Same category
• Similar features
• Lower price

──────────────────────────────────────────────────

🛍️ Apple AirPods Pro (2nd Generation)

⭐ Rating: 4.7 / 5

💲 Price: $249.00

💰 Save: $100.99 (28% off)

Active Noise Cancellation,
Adaptive Transparency,
Personalized Spatial Audio.

💡 Recommended because:
• Same category
• Similar features
• Lower price

---

*End of examples.*
