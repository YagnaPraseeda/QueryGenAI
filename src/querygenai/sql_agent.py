from __future__ import annotations

import re
from dataclasses import dataclass

from groq import Groq

from querygenai.config import settings
from querygenai.database import introspect_schema, run_query


SYSTEM_PROMPT = """
You are a senior analytics engineer translating business questions into SQLite SQL.
Return only one valid SQLite SELECT statement.
Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, ATTACH, PRAGMA, or multiple statements.
Prefer the sales_enriched view unless a base table is truly required.
Use LIMIT 10 for open-ended listing questions.
"""


@dataclass
class QueryResult:
    question: str
    sql: str
    rows: list[dict]
    source: str


class SQLSafetyError(ValueError):
    """Raised when SQL fails validation."""


class UnsupportedQueryError(ValueError):
    """Raised when the local fallback cannot interpret a question."""


class SQLQueryService:
    def __init__(self) -> None:
        self.database_path = settings.database_path
        self.schema = introspect_schema(self.database_path) if self.database_path.exists() else ""
        self.client = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None

    def refresh_schema(self) -> None:
        self.schema = introspect_schema(self.database_path)

    def answer_question(self, question: str) -> QueryResult:
        sql, source = self.generate_sql(question)
        validated_sql = self.validate_sql(sql)
        dataframe = run_query(self.database_path, validated_sql)
        return QueryResult(
            question=question,
            sql=validated_sql,
            rows=dataframe.to_dict(orient="records"),
            source=source,
        )

    def generate_sql(self, question: str) -> tuple[str, str]:
        fallback_sql: str | None
        fallback_error: UnsupportedQueryError | None = None
        try:
            fallback_sql = self.generate_fallback_sql(question)
        except UnsupportedQueryError as error:
            fallback_sql = None
            fallback_error = error

        if not self.client:
            if fallback_sql:
                return fallback_sql, "fallback"
            raise fallback_error or UnsupportedQueryError("The question could not be interpreted.")

        user_prompt = f"""
Schema:
{self.schema}

Question:
{question}
"""
        try:
            completion = self.client.chat.completions.create(
                model=settings.groq_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT.strip()},
                    {"role": "user", "content": user_prompt.strip()},
                ],
            )
            candidate = completion.choices[0].message.content or ""
            return self.extract_sql(candidate), "groq"
        except Exception:
            if fallback_sql:
                return fallback_sql, "fallback"
            raise fallback_error or UnsupportedQueryError(
                "Groq was unavailable and the local fallback could not interpret the question."
            )

    def extract_sql(self, response: str) -> str:
        fenced = re.search(r"```(?:sql)?\s*(.*?)```", response, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()
        return response.strip()

    def validate_sql(self, sql: str) -> str:
        normalized = sql.strip().rstrip(";")
        lowered = normalized.lower()

        if not lowered.startswith("select"):
            raise SQLSafetyError("Only SELECT statements are allowed.")
        if ";" in normalized:
            raise SQLSafetyError("Multiple statements are not allowed.")

        blocked_terms = [
            "insert ",
            "update ",
            "delete ",
            "drop ",
            "alter ",
            "create ",
            "attach ",
            "pragma ",
        ]
        if any(term in lowered for term in blocked_terms):
            raise SQLSafetyError("Generated SQL contains a blocked operation.")

        return normalized + ";"

    def generate_fallback_sql(self, question: str) -> str:
        normalized = question.lower()
        limit = self._extract_limit(normalized, default=10)
        product_prefix = self._extract_phrase_after_keyword(normalized, ["starts with", "start with", "begins with"])
        product_contains = self._extract_phrase_after_keyword(normalized, ["contains", "contain", "including"])
        product_suffix = self._extract_phrase_after_keyword(normalized, ["ends with", "end with"])

        if "product" in normalized and "name" in normalized and product_prefix:
            sanitized_prefix = self._sanitize_like_value(product_prefix)
            return f"""
SELECT DISTINCT product_name
FROM products
WHERE LOWER(product_name) LIKE '{sanitized_prefix}%'
ORDER BY product_name
LIMIT {limit}
""".strip()

        if "product" in normalized and "name" in normalized and product_contains:
            sanitized_contains = self._sanitize_like_value(product_contains)
            return f"""
SELECT DISTINCT product_name
FROM products
WHERE LOWER(product_name) LIKE '%{sanitized_contains}%'
ORDER BY product_name
LIMIT {limit}
""".strip()

        if "product" in normalized and "name" in normalized and product_suffix:
            sanitized_suffix = self._sanitize_like_value(product_suffix)
            return f"""
SELECT DISTINCT product_name
FROM products
WHERE LOWER(product_name) LIKE '%{sanitized_suffix}'
ORDER BY product_name
LIMIT {limit}
""".strip()

        if "top" in normalized and "product" in normalized:
            limit = self._extract_limit(normalized, default=5)
            return f"""
SELECT product_name, category, ROUND(SUM(net_revenue), 2) AS total_revenue
FROM sales_enriched
GROUP BY product_name, category
ORDER BY total_revenue DESC
LIMIT {limit}
""".strip()

        if ("list" in normalized or "show" in normalized) and "product" in normalized:
            return f"""
SELECT product_id, product_name, category, unit_price
FROM products
ORDER BY product_name
LIMIT {limit}
""".strip()

        if ("list" in normalized or "show" in normalized) and "customer" in normalized:
            return f"""
SELECT customer_id, customer_name, segment, city, state, region
FROM customers
ORDER BY customer_name
LIMIT {limit}
""".strip()

        if ("list" in normalized or "show" in normalized) and "order" in normalized:
            return f"""
SELECT order_id, order_date, customer_name, product_name, quantity, net_revenue
FROM sales_enriched
ORDER BY order_date DESC
LIMIT {limit}
""".strip()

        if "month" in normalized or "monthly" in normalized:
            return """
SELECT order_month, ROUND(SUM(net_revenue), 2) AS total_revenue
FROM sales_enriched
GROUP BY order_month
ORDER BY order_month
""".strip()

        if "region" in normalized:
            return """
SELECT region, ROUND(SUM(net_revenue), 2) AS total_revenue
FROM sales_enriched
GROUP BY region
ORDER BY total_revenue DESC
""".strip()

        if "segment" in normalized and ("average" in normalized or "avg" in normalized):
            return """
SELECT segment, ROUND(AVG(net_revenue), 2) AS average_order_value
FROM sales_enriched
GROUP BY segment
ORDER BY average_order_value DESC
""".strip()

        if "recent" in normalized or "latest" in normalized:
            return f"""
SELECT order_id, order_date, customer_name, product_name, quantity, net_revenue
FROM sales_enriched
ORDER BY order_date DESC
LIMIT {limit}
""".strip()

        if "category" in normalized and ("revenue" in normalized or "sales" in normalized):
            return """
SELECT category, ROUND(SUM(net_revenue), 2) AS total_revenue
FROM sales_enriched
GROUP BY category
ORDER BY total_revenue DESC
""".strip()

        raise UnsupportedQueryError(
            "Fallback mode could not interpret that question. Try a query like "
            "'show the top 5 products by revenue', 'list customers', or "
            "'show product names that start with insight'."
        )

    @staticmethod
    def _extract_limit(question: str, default: int) -> int:
        match = re.search(r"\b(\d+)\b", question)
        if not match:
            return default
        return max(1, min(int(match.group(1)), 50))

    @staticmethod
    def _extract_phrase_after_keyword(question: str, keywords: list[str]) -> str | None:
        for keyword in keywords:
            pattern = rf"{re.escape(keyword)}\s+([a-z0-9][a-z0-9\s_-]*)"
            match = re.search(pattern, question)
            if not match:
                continue

            phrase = match.group(1).strip(" .,!?:;\"'")
            filler_suffixes = [
                "just the product names",
                "just the product name",
                "just the names",
                "just the name",
                "only the product names",
                "only the names",
            ]
            for suffix in filler_suffixes:
                if phrase.endswith(suffix):
                    phrase = phrase[: -len(suffix)].strip()

            return phrase or None

        return None

    @staticmethod
    def _sanitize_like_value(value: str) -> str:
        return value.replace("'", "''").strip()
