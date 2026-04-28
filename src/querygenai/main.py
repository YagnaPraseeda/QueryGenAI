from __future__ import annotations

import argparse
from pprint import pprint

from querygenai.ingestion import ensure_database, ingest_sample_data
from querygenai.sql_agent import SQLQueryService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QueryGenAI command line interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ingest", help="Load sample CSV data into SQLite")

    ask_parser = subparsers.add_parser("ask", help="Ask a natural language question")
    ask_parser.add_argument("question", help="Business question to translate into SQL")

    dashboard_parser = subparsers.add_parser("dashboard", help="Start the Dash dashboard")
    dashboard_parser.add_argument("--host", default="127.0.0.1")
    dashboard_parser.add_argument("--port", default=8050, type=int)
    dashboard_parser.add_argument("--debug", action="store_true")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        database_path = ingest_sample_data()
        print(f"Ingested sample data into {database_path}")
        return

    if args.command == "ask":
        ensure_database()
        service = SQLQueryService()
        result = service.answer_question(args.question)
        print("SQL:")
        print(result.sql)
        print("\nRows:")
        pprint(result.rows)
        print(f"\nSource: {result.source}")
        return

    if args.command == "dashboard":
        from querygenai.dashboard import create_dashboard

        app = create_dashboard()
        app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
