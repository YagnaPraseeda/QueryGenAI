# QueryGenAI

`QueryGenAI` is an interview-ready natural language to SQL project built from scratch with Python, SQLite, Pandas, Dash, Plotly, and optional Groq-powered SQL generation.

## What it does

- Ingests CSV datasets into a local SQLite warehouse
- Builds an analytics view for easier downstream querying
- Converts natural language questions into SQL using Groq or a local fallback engine
- Validates generated SQL so only read-only `SELECT` statements run
- Displays KPIs, charts, generated SQL, and query results in a Dash dashboard

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

If `GROQ_API_KEY` is missing, the app still works using a deterministic fallback translator for common analytics questions.

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

## Sample questions

- `What is total revenue by month?`
- `Show the top 5 products by revenue`
- `Which region has the highest revenue?`
- `What is the average order value by segment?`
- `List the most recent 10 orders`

## Test

```bash
pytest
```
