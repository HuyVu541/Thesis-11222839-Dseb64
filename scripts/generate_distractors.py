import asyncio
import os
import sys
import shutil
import time
import requests
from pathlib import Path

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import settings
from src.clear_all_memory import clear_postgres, clear_filesystem, clear_faiss

BASE_URL = "http://localhost:8000"

import random

CATEGORIES = ["Beverages", "Condiments", "Confections", "Dairy Products", "Grains/Cereals", "Meat/Poultry", "Produce", "Seafood"]
COUNTRIES = ["USA", "UK", "Brazil", "Germany", "France", "Canada", "Italy", "Spain", "Mexico", "Sweden", "Argentina", "Switzerland", "Venezuela", "Austria", "Portugal"]
SHIPPERS = ["Speedy Express", "United Package", "Federal Shipping"]
TERMS = ["Net Sales", "Gross Margin", "Loyal Customer", "High Risk Order", "Priority Shipment", "Tier 1 Product", "Discount threshold"]

def generate_dynamic_prompts(count=100):
    """Procedurally generates realistic, complex BI tasks that naturally inject memory artifacts."""
    templates = [
        # Revenue and Margin
        "Calculate the total revenue for the '{category}' category in 1997. By the way, going forward, when I ask for '{term}', please use (UnitPrice * Quantity * (1 - Discount)) from order_details.",
        "What is the average {term} for products in {category}? Remember that {term} should ALWAYS be calculated using data from the past two fiscal years.",
        "Compare the {term} between {country} and {country2}. Moving forward, define 'High Margin Region' as any area where the {term} exceeds {random_int_large}%.",
        
        # Product and Inventory
        "Find the top 5 best-selling products in {country}. Please keep in mind that '{category} Mainstay' refers to any product in that category with over {random_int_large} units sold.",
        "What was the most expensive product ordered from {country}? Also define a metric called '{category} Premium Threshold' as any product in that category over ${random_int_large}.",
        "Can you check if there are any discontinued products in the '{category}' category? Establish a business rule that we must never sell discontinued products to {country}.",
        "What is the average unit price for '{category}'? Save an insight that anything above that average is considered a 'Premium {category} Item'.",
        "Which products in {category} are currently below their reorder level? Note for the future that any {category} item below reorder is considered a '{term}'.",
        
        # Customer and Sales Geography
        "Who are our top 5 customers from {country}? Also, please note that '{country}' is part of our 'Tier {random_int}' sales region. Please remember this.",
        "How many orders were placed in 1998 covering the '{category}' category? Make sure to save a rule that '{category}' is our priority focus for {country} expansion.",
        "List all customers in {country} who haven't placed an order this year. By the way, refer to these customers as 'At-Risk {country} Accounts'.",
        "What is the total sales volume for {country2}? Please remember that {country2} is managed by the European sales team.",
        
        # Employees and Performance
        "List all employees with more than {random_int_large} orders. We define these as 'Top Performers', keep that in mind as a strict definition.",
        "Who is the manager for the sales reps covering {country}? Note that the '{term}' metric should only be shared with regional managers.",
        "Compare sales between employees handling the {category} category. Save an insight that employees selling {category} generally have {random_int}% higher conversion rates.",
        
        # Shipping and Logistics
        "Find the total freight cost associated with orders shipped by '{shipper}'. Please save an insight that this shipper is used entirely for 'Fragile' deliveries.",
        "Pull a list of orders handled by '{shipper}' that went to {country}. Note that '{shipper}' has a history of delaying shipments to {country}, so categorize them as '{term}'.",
        "What is the average shipping time to {country2} using '{shipper}'? Remember that any shipping time to {country2} over {random_int} days violates our SLA.",
        "Calculate the percentage of orders to {country} shipped via {shipper}. Keep in mind we are actively trying to reduce our reliance on {shipper} by {random_int_large}%.",
        
        # Discounts and Promotions
        "Compare the average discount given in {country} versus {country2}. Also, establish a rule: 'Discounts above {random_int}% require VP approval'. Please remember this.",
        "Show me all orders with a discount greater than {random_int}0%. By the way, any discount strictly over {random_int}0% should trigger a 'Margin Alert'.",
        "Did '{category}' sales increase during our last promotion in {country}? We usually define a 'Successful Promo' as a {random_int}% lift in {category} volume.",
        
        # Complex Multi-Domain
        "How many '{category}' orders shipped by '{shipper}' went to {country}? Save an insight that this specific routing combination is highly inefficient.",
        "Calculate the {term} for {country} customers handled by '{shipper}'. Note that {country} customers are very sensitive to shipping delays.",

        # # ---------------------------------------------------------------
        # # TARGETED DISTRACTORS — mimic the 3 test scenarios with similar
        # # but different names, thresholds, and definitions so the agent
        # # must disambiguate under noise.
        # # ---------------------------------------------------------------

        # # --- Near-misses for Scenario 1: Accurate Retrieval ---
        # # (real: Shipping Performance Index, Shipping Cost Efficiency,
        # #  Shipping Reliability Score, Order Cost Average)

        # # Confusingly similar name — "Rate" vs "Index", different formula
        # "Define 'Shipping Performance Rate' as the average number of business days between order_date and shipped_date for all orders. Formula: AVG(shipped_date - order_date).",
        # # Same concept, different threshold — $150 vs the real $200
        # "We define 'Shipping Cost Ratio' as the average freight for orders where line item value exceeds $150. Please remember this definition going forward.",
        # # Overlapping name, completely different metric
        # "Define 'Shipping Efficiency Index' as the ratio of orders shipped on the same day to total orders. Formula: COUNT(same-day ships) / COUNT(all orders) * 100.",
        # # Near-miss on Shipping Reliability Score — different countries, different tolerance
        # "The 'Shipping Reliability Metric' is the percentage of on-time deliveries to {country} and {country2}. On-time means shipped_date is on or before required_date.",
        # # Overlapping with Order Cost Average but adds a filter
        # "Define 'Order Freight Baseline' as the average freight for orders placed in Q1 of any year. Only include orders from January through March.",
        # # Very similar to Shipping Cost Efficiency but per-unit
        # "The 'Per-Unit Shipping Cost' is calculated as freight / total quantity for orders over $200 in line item value. Save this definition.",
        # # Another shipping metric with similar vocabulary
        # "Define 'Logistics Performance Score' as the weighted average of on-time delivery rate (70%) and freight cost efficiency (30%). This is our primary KPI.",
        # # Near-miss — "Freight Efficiency" sounds like "Cost Efficiency"
        # "Our 'Freight Efficiency Rating' measures average freight per order for {shipper} specifically. It does NOT apply to other shippers.",
        # # Uses "cost" and "shipping" vocabulary but is about returns
        # "When I say 'Shipping Cost Impact', I mean the total freight on orders that were shipped late (shipped_date > required_date). Not average, total.",

        # # --- Near-misses for Scenario 2: Conflict Resolution ---
        # # (real: "High Priority Account" with 3 evolving definitions)

        # # Same domain, different name — could be confused with HPA
        # "A 'Key Account' is any customer with total order value exceeding ${random_int_large}00. These are distinct from 'High Priority Accounts'. Keep this separate.",
        # # Very similar name, freight-based like HPA v1 but different threshold
        # "A 'Priority Customer' is defined as any customer with freight charges above $500. Note this is different from any other customer classification we have.",
        # # Almost identical to HPA v2 (Germany + >10 orders) but for a different country
        # "Our 'Strategic Account' definition is: a customer in {country} with more than {random_int_large} total orders. Save this as a business rule.",
        # # Category-based like HPA v3 but different threshold
        # "A 'Diversified Customer' is any customer who has ordered from more than 6 product categories. Remember this definition.",
        # # Same name stem as "High Priority" — deliberate confusion
        # "A 'High Value Order' is any single order where the total line item value exceeds $5000. This is an order-level metric, not a customer-level one.",
        # # Another customer tier using freight — close to HPA v1
        # "'Premium Account Status' requires total freight charges above $1000 AND more than 20 orders. Both conditions must be met.",
        # # Sounds like HPA but is about products
        # "A 'High Priority Product' is any product ordered more than {random_int_large} times in a single quarter. Don't confuse this with customer classifications.",
        # # Contradicting definition to add noise
        # "For our {country} team, a 'Top Account' means any customer in {country} with over 5 orders. This applies only to {country} sales reporting.",

        # # --- Near-misses for Scenario 3: Multi-Hop Composition ---
        # # (real: "Underperforming Product" = <30 orders,
        # #  "Supplier Review" = supplier with >2 underperforming products)

        # # Similar name, different threshold — 50 vs 30
        # "An 'Underperforming SKU' is any product ordered fewer than 50 times total. This is used for quarterly inventory cleanup.",
        # # Similar concept, different direction — revenue-based instead of order-count
        # "Define 'Low Revenue Product' as any product generating total revenue under $1000. Formula: SUM(unit_price * quantity * (1 - discount)) < 1000.",
        # # Near-miss on "Supplier Review" — uses same term but different trigger
        # "A 'Supplier Audit' should be triggered if a supplier has more than 5 products with below-average unit prices. Save this policy.",
        # # Confusing overlap — sounds like Supplier Review but is about shipping
        # "Flag a supplier for 'Supplier Performance Review' if average delivery time for their products exceeds {random_int} days.",
        # # Related concept with different composition
        # "Define 'At-Risk Supplier' as any supplier whose products have an average discount above 15%. This indicates margin pressure.",
        # # Very close to Underperforming Product but adds a time constraint
        # "A 'Declining Product' is any product with fewer than 10 orders in 1997 specifically. This is only for annual trend analysis.",
        # # Overlapping review concept but customer-based
        # "If a customer has purchased more than 3 Underperforming SKUs, flag them for 'Account Health Review'. Save this rule.",
        # # Different "supplier" metric to add noise
        # "A supplier is considered 'Reliable' if at least 90% of orders containing their products were shipped on time. Remember this benchmark.",

        # # ---------------------------------------------------------------
        # # ADVERSARIAL DISTRACTORS — same exact names, wrong definitions,
        # # outdated versions, false chains, and query-vocabulary pollution.
        # # ---------------------------------------------------------------

        # # === EXACT NAME COLLISIONS (wrong definitions) ===

        # # Uses the EXACT name "Shipping Cost Efficiency" but wrong formula
        # "Just to be clear, when the {country} team says 'Shipping Cost Efficiency', they mean freight / number_of_line_items for that order. This is their regional interpretation.",
        # # Another wrong version of the same name
        # "For the {country2} office, 'Shipping Cost Efficiency' refers to the median freight across all orders, not the mean. Please note this regional difference.",
        # # Exact name "Shipping Performance Index" but different methodology
        # "Note: the {country} warehouse calculates 'Shipping Performance Index' differently — they use 5 business days as the cutoff, not 3, because of longer customs processing.",
        # # Exact name "Order Cost Average" but scoped wrong
        # "Going forward, 'Order Cost Average' should only include orders above $50 in freight. We exclude micro-shipments from this metric now.",
        # # Exact name "Shipping Reliability Score" but different countries
        # "Update: 'Shipping Reliability Score' now covers all of Europe, not just Germany/France/UK. And on-time means shipped_date <= required_date (no 1-day grace).",

        # # Exact name "High Priority Account" with completely wrong definition
        # "In our {country} division, a 'High Priority Account' is simply any customer who placed an order in the last 90 days. It's an activity-based definition.",
        # # Another wrong HPA
        # "Please note: 'High Priority Account' for the {category} team means any customer who has ordered more than $2000 worth of {category} products. This is category-specific.",
        # # HPA with a similar-but-wrong threshold
        # "A 'High Priority Account' is defined as a customer in {country2} with freight over $600. This was updated last quarter.",

        # # Exact name "Underperforming Product" but wrong threshold
        # "Reminder: 'Underperforming Product' means any product ordered fewer than 20 times. We lowered the threshold from 30 to 20 at the start of Q2.",
        # # Another wrong threshold claim
        # "The {country} team uses a stricter definition: 'Underperforming Product' = fewer than 40 orders. Please keep this in mind for {country} reports.",
        # # Exact name "Supplier Review" but wrong trigger
        # "A 'Supplier Review' is triggered when a supplier has more than 1 product with a unit price increase exceeding 20%. This is a pricing-based trigger.",

        # # === OUTDATED / SUPERSEDED DEFINITIONS ===
        # # (Creates temporal confusion — agent must figure out recency)

        # "HISTORICAL NOTE: Before 2024, 'Shipping Performance Index' used a 7-day window. If you see older reports with higher scores, that's why. We now use 3 days.",
        # "Old definition (deprecated): 'High Priority Account' used to be any customer with more than {random_int_large} orders regardless of country. This was sunset in favor of the current freight-based definition.",
        # "Previous version: 'Underperforming Product' was originally defined as products with fewer than 15 orders. The threshold was raised to accommodate the growing product catalog.",
        # "Legacy definition: 'Supplier Review' used to require 5+ underperforming products per supplier. We relaxed it to 2 to catch issues earlier.",

        # # === FALSE MULTI-HOP CHAINS ===
        # # (Creates fake dependency links that could mislead composition)

        # "Define 'Supply Chain Risk Score' as: count of Underperforming Products × average freight cost for that supplier. Use this to prioritize Supplier Reviews.",
        # "If a 'High Priority Account' has ordered more than 3 'Underperforming Products', escalate them to 'Executive Account Review'. Save this cross-reference.",
        # "Define 'Logistics Risk Index' as: (Shipping Performance Index + Shipping Reliability Score) / 2. This is our combined shipping health metric.",
        # "Any product that is both an 'Underperforming Product' AND has a 'Shipping Cost Efficiency' above the 75th percentile should be flagged for 'Product Discontinuation Review'.",
        # "When a supplier under 'Supplier Review' also ships to a 'High Priority Account', mark the relationship as 'Critical Supply Path'. Save this policy.",
        # "A 'Portfolio Risk Supplier' is any supplier under 'Supplier Review' whose products contribute more than {random_int_large}% of revenue in {category}. Keep this rule.",

        # # === QUERY VOCABULARY POLLUTION ===
        # # (Uses exact phrases from the test queries to pollute retrieval)

        # # Uses "logistics review" and "shipping cost efficiency" — exact test query phrasing
        # "Whenever someone asks about a 'logistics review', always start by pulling the freight breakdown by shipper. Don't confuse this with per-order shipping cost efficiency.",
        # # Uses "how many High Priority Accounts" — exact test query
        # "If someone asks 'how many High Priority Accounts', always confirm which regional definition they mean first — {country} and {country2} use different criteria.",
        # # Uses "Supplier Review" and "flagged" — exact test query vocabulary
        # "When someone asks which suppliers should be 'flagged for Supplier Review', make sure to check both the performance and pricing triggers before responding.",
        # # "shipping cost" in 1997 — exact test context
        # "Important context for 1997 analysis: freight costs were unusually high in Q3 1997 due to a shipper strike. Factor this into any 'shipping cost' analysis for that year.",
        # # "underperforming" vocabulary confusion
        # "Note that 'underperforming' can refer to either products (order count) or employees (revenue generated). Always clarify which is meant before running queries.",

        # # === METRIC REDEFINITIONS (mimics Conflict Resolution for other terms) ===
        # # (Creates noise by applying the conflicting-versions pattern to unrelated metrics)

        # "Actually, update the definition of 'Top Performers' — it should now mean employees with more than {random_int_large} orders AND at least $10,000 in total sales.",
        # "Correction: 'Premium {category} Item' should be defined as any item in the top 10% by revenue, not by average unit price. Please update accordingly.",
        # "We're changing 'Margin Alert' from {random_int}0% discount threshold to 25% across all categories. Please remember this update.",
        # "Redefine '{term}' to mean: {term} calculated only for orders shipped by {shipper}. This is a scope change effective immediately.",
        # "Update: a 'Diversified Customer' now requires orders from more than {random_int} categories (changed from 6). Save this new threshold.",

        # # ===============================================================
        # # HIGH-DENSITY SCENARIO 1 NOISE — shipping/freight/cost metrics
        # # with overlapping vocabulary, similar thresholds, and formulas
        # # that could easily be confused with the 4 real definitions.
        # # ===============================================================

        # # --- Freight + $200 threshold variations (target: Shipping Cost Efficiency) ---
        # "Our 'Qualified Order Freight' metric is the average freight for orders whose total line value is at least $200. We use this for budget forecasting.",
        # "Define 'Filtered Freight Average' as AVG(freight) only for orders where SUM(unit_price * quantity) >= $200. This is our cost benchmark.",
        # "The 'Large Order Shipping Rate' is the average shipping cost for orders exceeding $200 in merchandise value. Use this for quarterly reporting.",
        # "We need a 'Cost-Per-Qualifying-Order' metric: average freight where order line items total more than $200. Save this for the logistics team.",
        # "For our shipping dashboard, 'Freight Benchmark' means the average freight on orders with line item totals above $250. Not $200 — $250.",
        # "'Weighted Shipping Cost' is calculated as AVG(freight) for orders where unit_price * quantity exceeds $100 per line item. This is per-line, not per-order.",
        # "Define 'Shipping Value Ratio' as total freight divided by total merchandise value, but only for orders above $200. This is a ratio, not an average.",
        # "The 'Efficient Shipping Metric' is the average freight for orders shipped to {country} where line items exceed $200. This is {country}-specific.",

        # # --- On-time / delivery percentage variations (target: Shipping Performance Index & Reliability Score) ---
        # "Our 'Delivery Success Rate' is the percentage of orders where shipped_date - order_date is 3 days or less. Use calendar days, not business days.",
        # "'Fulfillment Speed Index' measures the percentage of orders shipped within 2 business days of order_date. Formula: COUNT(fast ships) / COUNT(all) * 100.",
        # "Define 'Express Shipping Rate' as the fraction of orders shipped the same day or next day. This is stricter than our other shipping metrics.",
        # "The 'Regional Delivery Score' for {country} is: percentage of orders to {country} shipped within 3 days. This is country-scoped, unlike our global index.",
        # "'Timely Dispatch Percentage' counts orders where shipped_date <= order_date + 3 days, but ONLY for orders handled by {shipper}. Shipper-specific metric.",
        # "Our 'European Delivery Rate' covers on-time deliveries to Germany, France, UK, Italy, and Spain. On-time = shipped_date <= required_date.",
        # "'On-Time Delivery Index' is the percentage of orders where shipped_date <= required_date, across all countries. No 1-day grace period.",
        # "The '{country} Reliability Metric' measures on-time delivery to {country} only. On-time means shipped within 2 days of required_date.",
        # "Define 'Carrier Reliability for {shipper}' as the percentage of {shipper} orders delivered on time (shipped_date <= required_date + 1 day).",
        # "'Global Shipping Score' is a composite: 60% on-time rate + 40% cost efficiency. Don't confuse this with individual shipping metrics.",

        # # --- Generic freight averages (target: Order Cost Average) ---
        # "Our 'Baseline Freight' is the average freight for domestic orders only (ship_country = 'USA'). International orders are excluded.",
        # "'Average Delivery Cost' means the average freight for all orders placed in 1997. This is year-specific — don't use it for other years.",
        # "Define 'Standard Freight Rate' as the median freight across all orders. We use median to avoid outlier effects from large international shipments.",
        # "The 'Freight Index' is average freight normalized by order count per month. Formula: SUM(freight) / COUNT(DISTINCT month). This is a monthly metric.",
        # "'Net Shipping Cost' is the average freight minus any freight discounts applied. If no discount data exists, it equals average freight.",

        # # ===============================================================
        # # HIGH-DENSITY SCENARIO 2 NOISE — customer classification tiers
        # # with similar criteria to the 3 HPA definitions (freight, country
        # # + order count, category diversity).
        # # ===============================================================

        # # --- Freight-based customer tiers (target: HPA v1 — freight > $800) ---
        # "A 'Valued Customer' is anyone with total freight above $700. This is our baseline customer appreciation tier.",
        # "Define 'Freight-Heavy Customer' as a customer whose average freight per order exceeds $50. This is per-order, not cumulative.",
        # "'Top-Tier Shipper' is any customer with cumulative freight charges above $900. Use this for our annual logistics review.",
        # "A 'Cost-Sensitive Account' is a customer with total freight above $800 but total order value below $5000. They spend a lot on shipping relative to purchases.",
        # "Our 'Logistics Partner' tier includes customers with freight above $600 AND who use {shipper} for more than 80% of orders.",
        # "'Freight Elite' is any customer with average freight per order above $75 and at least 15 orders total. Both conditions required.",
        # "A 'Shipping-Intensive Customer' has freight exceeding $800 total. Note: this overlaps with other definitions but is used specifically for carrier contract negotiations.",

        # # --- Country + order count tiers (target: HPA v2 — Germany + >10 orders) ---
        # "A 'Regional Champion' for {country} is any customer in {country} with more than 8 orders. Save this per-country classification.",
        # "'Active {country} Account' means a customer located in {country} with at least 12 orders. This is our engagement threshold for {country}.",
        # "Define '{country} Key Client' as a customer based in {country} with more than 10 orders AND total revenue above $5000.",
        # "A 'Core European Customer' is any customer in Germany, France, or the UK with more than 10 orders. This covers multiple countries.",
        # "'Regional Heavy Hitter' is a customer in {country} with total order value above $10,000 regardless of order count.",
        # "Our '{country2} Focus Account' is any customer in {country2} with more than 15 orders. Different country, different threshold.",
        # "A 'Growth Account' in {country} has between 5 and 10 orders — they're promising but haven't yet reached key client status.",

        # # --- Category diversity tiers (target: HPA v3 — >4 categories) ---
        # "A 'Cross-Category Buyer' is a customer who has ordered from at least 3 product categories. This is our diversity baseline.",
        # "'Category Explorer' means a customer ordering from more than 5 distinct categories. Use this for marketing segmentation.",
        # "Define 'Full-Range Customer' as anyone who has ordered from ALL 8 product categories. This is our top diversity tier.",
        # "A 'Multi-Category Account' purchases from more than 4 categories but fewer than 7. This is the middle tier of category diversity.",
        # "Our 'Specialist Customer' is the opposite — someone who orders from exactly 1 category. They're focused buyers.",
        # "'Broad Purchaser' is defined as a customer ordering from more than 4 categories AND with total orders above 20. Both conditions must be met.",
        # "A 'Category-Diverse Customer' is anyone ordering from 3+ categories in a single year. This is annual, not cumulative.",

        # # --- Hybrid / compound customer tiers (mixing criteria from all 3 HPA versions) ---
        # "A 'Premium Partner' is a customer in {country} with freight above $500 AND orders from 3+ categories. Mixed criteria.",
        # "'Strategic Customer' requires: located in {country}, more than 10 orders, AND freight above $600. All three conditions must be met.",
        # "Define 'Gold Account' as a customer with either (a) freight > $1000, OR (b) orders from > 5 categories, OR (c) more than 20 orders from {country}. Any one qualifies.",
        # "'Platinum Account' is a customer who meets ALL THREE: freight > $800, located in Germany, and ordered from > 4 categories. This is extremely selective.",
        # "A 'Watch List Account' has freight above $700 but fewer than 5 orders — high shipping cost per order. Needs review.",
        # "Our 'Engagement Tier' is based on category count only: Bronze (2+), Silver (4+), Gold (6+), Platinum (8). No freight or location criteria.",
    ]
    
    prompts = []
    # Set seed for reproducible testing distractors
    random.seed(42) 
    
    for _ in range(count):
        template = random.choice(templates)
        
        # Pick two distinct countries if needed
        c1, c2 = random.sample(COUNTRIES, 2)
        
        prompt = template.format(
            category=random.choice(CATEGORIES),
            country=c1,
            country2=c2,
            shipper=random.choice(SHIPPERS),
            term=random.choice(TERMS),
            random_int=random.randint(1, 5),
            random_int_large=random.randint(20, 100)
        )
        prompts.append(prompt)
        
    return prompts

DISTRACTOR_PROMPTS = generate_dynamic_prompts(count=100)

async def reset_environment():
    """Non-interactively wipe all memory."""
    print("\n[Setup] 🧹 Wiping database and filesystem for test isolation...", flush=True)
    await clear_postgres()
    clear_filesystem()
    clear_faiss()
    print("[Setup] ✅ Environment reset complete.\n", flush=True)

def generate_distractors():
    """Hit the real agent API to generate memory artifacts."""
    print(f"[Setup] 🧠 Generating {len(DISTRACTOR_PROMPTS)} distractor artifacts via the Agent API...", flush=True)
    
    # Check if backend is up
    try:
        requests.get(f"{BASE_URL}/sessions", timeout=5)
    except requests.exceptions.ConnectionError:
        print("[Setup] ❌ Backend not running on localhost:8000. Start it first.", flush=True)
        return

    import uuid
    BATCH_SIZE = 5  # New session every N prompts to avoid huge conversation histories
    session_id = None

    for i, prompt in enumerate(DISTRACTOR_PROMPTS):
        # Create a new session every BATCH_SIZE prompts
        if i % BATCH_SIZE == 0:
            session_id = f"historical_analysis_{uuid.uuid4().hex[:8]}"
            requests.post(f"{BASE_URL}/sessions", json={
                "id": session_id,
                "title": f"Q3 Analysis Batch {i // BATCH_SIZE + 1}"
            })
            print(f"\n  📁 New session: {session_id}", flush=True)

        print(f"  -> Injecting [{i+1}/{len(DISTRACTOR_PROMPTS)}]: {prompt[:80]}...", flush=True)
        try:
            resp = requests.post(f"{BASE_URL}/chat/completions", json={
                "messages": [{"role": "user", "content": prompt}],
                "conversationId": session_id,
                "stream": False,
            }, timeout=300)
            if resp.status_code != 200:
                print(f"     ⚠ HTTP {resp.status_code}: {resp.text[:100]}", flush=True)
        except Exception as e:
            print(f"     ⚠ Error: {e}", flush=True)
        # Sleep briefly to avoid hammering the API
        time.sleep(30)
        
    print("\n[Setup] ✅ Distractor generation complete.", flush=True)

if __name__ == "__main__":
    asyncio.run(reset_environment())
    generate_distractors()
