from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd


@contextmanager
def sqlite_connection(database_path: Path):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def run_query(database_path: Path, query: str) -> pd.DataFrame:
    with sqlite_connection(database_path) as connection:
        return pd.read_sql_query(query, connection)


def execute_script(database_path: Path, script: str) -> None:
    with sqlite_connection(database_path) as connection:
        connection.executescript(script)
        connection.commit()


def introspect_schema(database_path: Path) -> str:
    with sqlite_connection(database_path) as connection:
        tables = pd.read_sql_query(
            """
            SELECT name
            FROM sqlite_master
            WHERE type IN ('table', 'view')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """,
            connection,
        )["name"].tolist()

        lines: list[str] = []
        for table_name in tables:
            table_info = pd.read_sql_query(
                f"PRAGMA table_info({table_name})",
                connection,
            )
            columns = ", ".join(
                f"{row['name']} {row['type']}" for _, row in table_info.iterrows()
            )
            lines.append(f"{table_name}: {columns}")

        return "\n".join(lines)

