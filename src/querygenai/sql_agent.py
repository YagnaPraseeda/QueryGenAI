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
        fallback_sql = self.generate_fallback_sql(question)
        if not self.client:
            return fallback_sql, "fallback"

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
            return fallback_sql, "fallback"

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

        if "top" in normalized and "product" in normalized:
            limit = self._extract_limit(normalized, default=5)
            return f"""
SELECT product_name, category, ROUND(SUM(net_revenue), 2) AS total_revenue
FROM sales_enriched
GROUP BY product_name, category
ORDER BY total_revenue DESC
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
            limit = self._extract_limit(normalized, default=10)
            return f"""
SELECT order_id, order_date, customer_name, product_name, quantity, net_revenue
FROM sales_enriched
ORDER BY order_date DESC
LIMIT {limit}
""".strip()

        return """
SELECT category, ROUND(SUM(net_revenue), 2) AS total_revenue
FROM sales_enriched
GROUP BY category
ORDER BY total_revenue DESC
""".strip()

    @staticmethod
    def _extract_limit(question: str, default: int) -> int:
        match = re.search(r"\b(\d+)\b", question)
        if not match:
            return default
        return max(1, min(int(match.group(1)), 50))

