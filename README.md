# QueryGenAI

`QueryGenAI` is a natural language to SQL analytics project built with Python, SQLite, Pandas, Dash, Plotly, and Groq-powered SQL generation with a local fallback mode.

## What it does

- Ingests CSV datasets into a local SQLite warehouse
- Builds an analytics view for easier downstream querying
- Converts natural language questions into SQL using Groq or a local fallback engine
- Validates generated SQL so only read-only `SELECT` statements run
- Displays KPIs, charts, generated SQL, and query results in a Dash dashboard
- Shows whether a query came from `groq` or `fallback`

## Project structure

```text
QueryGenAI/
  data/raw/                Sample CSV inputs
  data/processed/          SQLite database created at runtime
  src/querygenai/          Application code
  tests/                   Lightweight regression tests
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

Create a `.env` file if you want live Groq-backed SQL generation:

```env
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

If `GROQ_API_KEY` is missing, the app still works using a deterministic fallback translator for common analytics questions. When a question is outside the fallback rule set, the app now returns a clear error instead of silently showing unrelated results.

## Run

Load the sample data into SQLite:

```bash
querygenai ingest
```

Ask a question from the command line:

```bash
querygenai ask "Show monthly revenue by category"
```

Start the dashboard:

```bash
querygenai dashboard
```

If port `8050` is already in use:

```bash
querygenai dashboard --port 8051
```

## Sample questions

- `What is total revenue by month?`
- `Show the top 5 products by revenue`
- `Which region has the highest revenue?`
- `What is the average order value by segment?`
- `List the most recent 10 orders`
- `List customers`
- `Show the product names starts with insight`

## Fallback mode

Without Groq, the local fallback handles a small set of common patterns such as:

- Revenue by month, region, category, and top products
- Recent orders
- Customer and product listing queries
- Product name prefix and contains filters

This keeps the project usable even if an API key is unavailable.

## Test

```bash
pytest
```
