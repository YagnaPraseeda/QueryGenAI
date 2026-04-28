from __future__ import annotations

from dash import Dash, Input, Output, State, callback, dash_table, dcc, html
import plotly.express as px

from querygenai.config import settings
from querygenai.database import run_query
from querygenai.ingestion import ensure_database
from querygenai.sql_agent import SQLQueryService, SQLSafetyError


def _metric_card(label: str, value: str) -> html.Div:
    return html.Div(
        className="metric-card",
        children=[
            html.Div(label, className="metric-label"),
            html.Div(value, className="metric-value"),
        ],
    )


def _build_layout() -> html.Div:
    monthly_revenue = run_query(
        settings.database_path,
        """
        SELECT order_month, ROUND(SUM(net_revenue), 2) AS total_revenue
        FROM sales_enriched
        GROUP BY order_month
        ORDER BY order_month
        """,
    )
    category_revenue = run_query(
        settings.database_path,
        """
        SELECT category, ROUND(SUM(net_revenue), 2) AS total_revenue
        FROM sales_enriched
        GROUP BY category
        ORDER BY total_revenue DESC
        """,
    )
    summary = run_query(
        settings.database_path,
        """
        SELECT
            COUNT(DISTINCT order_id) AS total_orders,
            COUNT(DISTINCT customer_id) AS total_customers,
            ROUND(SUM(net_revenue), 2) AS total_revenue,
            ROUND(AVG(net_revenue), 2) AS average_order_value
        FROM sales_enriched
        """,
    ).iloc[0]

    monthly_chart = px.line(
        monthly_revenue,
        x="order_month",
        y="total_revenue",
        markers=True,
        title="Monthly Revenue",
    )
    category_chart = px.bar(
        category_revenue,
        x="category",
        y="total_revenue",
        color="category",
        title="Revenue by Category",
    )
    category_chart.update_layout(showlegend=False)

    return html.Div(
        className="page",
        children=[
            html.Div(
                className="hero",
                children=[
                    html.Div(
                        [
                            html.H1("QueryGenAI"),
                            html.P("Natural language to SQL analytics on a local SQLite warehouse."),
                        ]
                    ),
                    html.Div(
                        className="metrics",
                        children=[
                            _metric_card("Revenue", f"${summary['total_revenue']:,.2f}"),
                            _metric_card("Orders", f"{int(summary['total_orders'])}"),
                            _metric_card("Customers", f"{int(summary['total_customers'])}"),
                            _metric_card("Avg Order", f"${summary['average_order_value']:,.2f}"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="workspace",
                children=[
                    html.Div(
                        className="panel query-panel",
                        children=[
                            html.H2("Ask a business question"),
                            dcc.Input(
                                id="question-input",
                                type="text",
                                placeholder="Example: Show the top 5 products by revenue",
                                className="question-input",
                            ),
                            html.Button("Run Query", id="run-query", n_clicks=0, className="run-button"),
                            html.Div(id="query-status", className="status"),
                            html.Pre(id="generated-sql", className="generated-sql"),
                        ],
                    ),
                    html.Div(
                        className="panel charts-panel",
                        children=[
                            dcc.Graph(figure=monthly_chart, config={"displayModeBar": False}),
                            dcc.Graph(figure=category_chart, config={"displayModeBar": False}),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="panel results-panel",
                children=[
                    html.H2("Query Results"),
                    dash_table.DataTable(
                        id="results-table",
                        page_size=10,
                        style_table={"overflowX": "auto"},
                        style_cell={"padding": "12px", "textAlign": "left", "fontFamily": "Segoe UI"},
                        style_header={"backgroundColor": "#d9e6f2", "fontWeight": "bold"},
                    ),
                ],
            ),
        ],
    )


def create_dashboard() -> Dash:
    ensure_database()
    app = Dash(__name__)
    app.title = "QueryGenAI"
    app.layout = _build_layout()

    app.index_string = """
    <!DOCTYPE html>
    <html>
        <head>
            {%metas%}
            <title>{%title%}</title>
            {%favicon%}
            {%css%}
            <style>
                body {
                    margin: 0;
                    font-family: Georgia, "Times New Roman", serif;
                    background:
                        radial-gradient(circle at top left, rgba(217, 230, 242, 0.9), transparent 35%),
                        linear-gradient(135deg, #f6efe3 0%, #edf4fb 45%, #dce9f6 100%);
                    color: #14213d;
                }
                .page {
                    padding: 32px;
                    max-width: 1380px;
                    margin: 0 auto;
                }
                .hero {
                    display: grid;
                    gap: 20px;
                    grid-template-columns: 1.5fr 1fr;
                    align-items: start;
                    margin-bottom: 24px;
                }
                .hero h1 {
                    margin: 0 0 8px 0;
                    font-size: 3rem;
                    line-height: 1;
                }
                .hero p {
                    margin: 0;
                    font-size: 1.05rem;
                    max-width: 680px;
                }
                .metrics {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                    gap: 12px;
                }
                .metric-card, .panel {
                    background: rgba(255, 255, 255, 0.78);
                    border: 1px solid rgba(20, 33, 61, 0.12);
                    border-radius: 8px;
                    box-shadow: 0 14px 40px rgba(20, 33, 61, 0.08);
                    backdrop-filter: blur(10px);
                }
                .metric-card {
                    padding: 18px;
                }
                .metric-label {
                    font-size: 0.9rem;
                    color: #5c677d;
                    margin-bottom: 6px;
                }
                .metric-value {
                    font-size: 1.7rem;
                    font-weight: 700;
                }
                .workspace {
                    display: grid;
                    grid-template-columns: minmax(320px, 460px) 1fr;
                    gap: 20px;
                    margin-bottom: 20px;
                }
                .panel {
                    padding: 20px;
                }
                .panel h2 {
                    margin-top: 0;
                }
                .question-input {
                    width: 100%;
                    padding: 14px;
                    border-radius: 8px;
                    border: 1px solid #9fb3c8;
                    margin-bottom: 12px;
                    font-size: 1rem;
                    box-sizing: border-box;
                }
                .run-button {
                    background: #14213d;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 18px;
                    cursor: pointer;
                    font-size: 0.95rem;
                }
                .status {
                    margin-top: 14px;
                    min-height: 24px;
                    color: #7a1f1f;
                }
                .generated-sql {
                    margin-top: 12px;
                    padding: 14px;
                    background: #10233f;
                    color: #f4f7fb;
                    border-radius: 8px;
                    white-space: pre-wrap;
                    min-height: 90px;
                }
                @media (max-width: 980px) {
                    .hero, .workspace {
                        grid-template-columns: 1fr;
                    }
                    .page {
                        padding: 18px;
                    }
                    .hero h1 {
                        font-size: 2.3rem;
                    }
                }
            </style>
        </head>
        <body>
            {%app_entry%}
            <footer>
                {%config%}
                {%scripts%}
                {%renderer%}
            </footer>
        </body>
    </html>
    """

    service = SQLQueryService()

    @callback(
        Output("query-status", "children"),
        Output("generated-sql", "children"),
        Output("results-table", "data"),
        Output("results-table", "columns"),
        Input("run-query", "n_clicks"),
        State("question-input", "value"),
        prevent_initial_call=True,
    )
    def run_business_query(_: int, question: str | None):
        if not question:
            return "Enter a question to run a query.", "", [], []

        try:
            result = service.answer_question(question)
            rows = result.rows
            columns = [{"name": col, "id": col} for col in rows[0].keys()] if rows else []
            status = f"Query source: {result.source}"
            return status, result.sql, rows, columns
        except SQLSafetyError as error:
            return str(error), "", [], []
        except Exception as error:
            return f"Query failed: {error}", "", [], []

    return app
