import pytest

from querygenai.sql_agent import SQLQueryService, SQLSafetyError, UnsupportedQueryError


def test_validate_sql_accepts_select():
    service = SQLQueryService()
    sql = service.validate_sql("SELECT * FROM sales_enriched LIMIT 5")
    assert sql == "SELECT * FROM sales_enriched LIMIT 5;"


def test_validate_sql_blocks_mutation():
    service = SQLQueryService()
    try:
        service.validate_sql("DROP TABLE orders")
    except SQLSafetyError:
        assert True
        return
    assert False, "Expected SQLSafetyError for blocked statement"


def test_fallback_top_products():
    service = SQLQueryService()
    sql = service.generate_fallback_sql("Show top 3 products by revenue")
    assert "LIMIT 3" in sql
    assert "FROM sales_enriched" in sql


def test_fallback_product_name_prefix_lookup():
    service = SQLQueryService()
    sql = service.generate_fallback_sql(
        "show the product names starts with insight, just the product names"
    )
    assert "SELECT DISTINCT product_name" in sql
    assert "FROM products" in sql
    assert "LIKE 'insight%'" in sql


def test_fallback_list_customers():
    service = SQLQueryService()
    sql = service.generate_fallback_sql("list customers")
    assert "FROM customers" in sql
    assert "ORDER BY customer_name" in sql


def test_fallback_raises_for_unknown_question():
    service = SQLQueryService()
    with pytest.raises(UnsupportedQueryError):
        service.generate_fallback_sql("show me something magical and unrelated")
