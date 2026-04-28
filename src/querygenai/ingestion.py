from __future__ import annotations

from pathlib import Path

import pandas as pd

from querygenai.config import settings
from querygenai.database import execute_script, sqlite_connection


DDL = """
DROP VIEW IF EXISTS sales_enriched;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS products;

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    segment TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    region TEXT NOT NULL
);

CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit_price REAL NOT NULL
);

CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    order_date TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    discount REAL NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE VIEW sales_enriched AS
SELECT
    o.order_id,
    o.order_date,
    substr(o.order_date, 1, 7) AS order_month,
    c.customer_id,
    c.customer_name,
    c.segment,
    c.city,
    c.state,
    c.region,
    p.product_id,
    p.product_name,
    p.category,
    p.unit_price,
    o.quantity,
    o.discount,
    round(o.quantity * p.unit_price, 2) AS gross_revenue,
    round(o.quantity * p.unit_price * (1 - o.discount), 2) AS net_revenue
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN products p ON o.product_id = p.product_id;
"""


def _load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def ingest_sample_data() -> Path:
    settings.processed_data_dir.mkdir(parents=True, exist_ok=True)
    execute_script(settings.database_path, DDL)

    customers = _load_csv(settings.raw_data_dir / "customers.csv")
    products = _load_csv(settings.raw_data_dir / "products.csv")
    orders = _load_csv(settings.raw_data_dir / "orders.csv")

    with sqlite_connection(settings.database_path) as connection:
        customers.to_sql("customers", connection, if_exists="append", index=False)
        products.to_sql("products", connection, if_exists="append", index=False)
        orders.to_sql("orders", connection, if_exists="append", index=False)
        connection.commit()

    return settings.database_path


def ensure_database() -> Path:
    if settings.database_path.exists():
        return settings.database_path
    return ingest_sample_data()
