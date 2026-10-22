"""Project 1 - Olist e-commerce: clean -> model -> SQL -> exports for Power BI."""
import sqlite3
from pathlib import Path
import pandas as pd
RAW = Path("data/raw")
OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)
DATE_COLS = ["order_purchase_timestamp", "order_delivered_customer_date",
             "order_estimated_delivery_date"]
def load():
    orders = pd.read_csv(RAW / "orders.csv", parse_dates=DATE_COLS)
    items = pd.read_csv(RAW / "order_items.csv")
    products = pd.read_csv(RAW / "products.csv")
    names = pd.read_csv(RAW / "product_category_name_translation.csv")
    reviews = pd.read_csv(RAW / "order_reviews.csv")
    customers = pd.read_csv(RAW / "customers.csv")
    return orders, items, products, names, reviews, customers
def build_fact(orders, items, products, names, reviews, customers):
    # 1) keep only completed deliveries with a delivery date
    orders = (orders[orders["order_status"] == "delivered"]
              .dropna(subset=["order_delivered_customer_date"])
              .drop_duplicates("order_id"))
    # 2) some orders have several reviews -> average to one row per order
    reviews = reviews.groupby("order_id", as_index=False)["review_score"].mean()
    # 3) English category names; missing ones become "unknown"
    products = products.merge(names, on="product_category_name", how="left")
    products["category"] = products["product_category_name_english"].fillna("unknown")
    items = items.merge(products[["product_id", "category"]], on="product_id", how="left")
    items["category"] = items["category"].fillna("unknown")
    items["revenue"] = items["price"] + items["freight_value"]
    # 4) one big fact table at order-item grain
    fact = (items.merge(orders, on="order_id")
                 .merge(reviews, on="order_id", how="left")
                 .merge(customers[["customer_id", "customer_state"]],
                        on="customer_id", how="left"))
    # 5) derived columns = the "feature engineering" of analytics
    fact["order_month"] = fact["order_purchase_timestamp"].dt.to_period("M").astype(str)
    fact["delivery_days"] = (fact["order_delivered_customer_date"]
                             - fact["order_purchase_timestamp"]).dt.days
    fact["days_late"] = (fact["order_delivered_customer_date"]
                         - fact["order_estimated_delivery_date"]).dt.days
    fact["is_late"] = (fact["days_late"] > 0).astype(int)
    return fact
def quality_checks(fact):
    assert fact["revenue"].ge(0).all(), "negative revenue found"
    assert not fact.duplicated(["order_id", "order_item_id"]).any(), "duplicate lines"
    print("Rows:", len(fact), "| Missing review %:",
          round(fact["review_score"].isna().mean() * 100, 1))
QUERIES = {
    "monthly_revenue": """
        SELECT order_month,
               ROUND(SUM(revenue), 2)                        AS revenue,
               COUNT(DISTINCT order_id)                      AS orders,
               ROUND(SUM(revenue) / COUNT(DISTINCT order_id), 2) AS avg_order_value
        FROM fact_sales GROUP BY order_month ORDER BY order_month;""",
    "top_categories": """
        SELECT category, ROUND(SUM(revenue), 2) AS revenue,
               RANK() OVER (ORDER BY SUM(revenue) DESC) AS rnk
        FROM fact_sales GROUP BY category ORDER BY revenue DESC LIMIT 10;""",
         "late_vs_review": """
        SELECT is_late, COUNT(*) AS order_lines,
               ROUND(AVG(review_score), 2) AS avg_review
        FROM fact_sales GROUP BY is_late;""",
}
def main():
    fact = build_fact(*load())
    quality_checks(fact)
    fact.to_csv(OUT / "fact_sales.csv", index=False)           # Power BI source
    with sqlite3.connect(OUT / "olist.db") as con:
        fact.to_sql("fact_sales", con, if_exists="replace", index=False)
        for name, sql in QUERIES.items():
            result = pd.read_sql_query(sql, con)
            result.to_csv(OUT / f"{name}.csv", index=False)
            print(f"\n== {name} ==\n{result.head(10)}")
if __name__ == "__main__":
    main()