from querygenai.sql_agent import SQLQueryService, SQLSafetyError


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
