"""Single-file Dash app copied into every new project sandbox."""
import math
import os

import dash
from dash import dcc, html
import plotly.graph_objects as go


PORT = int(os.environ.get("PORT", "8100"))
HOST = os.environ.get("HOST", "127.0.0.1")


app = dash.Dash(__name__)
app.title = "Quant Research Project"


_X = list(range(60))
_Y = [round(100 + 8 * math.sin(i / 4) + i * 0.6, 2) for i in _X]

_FIG = go.Figure(
    data=go.Scatter(
        x=_X,
        y=_Y,
        mode="lines",
        line=dict(color="#0f172a", width=2),
        fill="tozeroy",
        fillcolor="rgba(15, 23, 42, 0.06)",
        hovertemplate="%{y}<extra></extra>",
    )
)
_FIG.update_layout(
    margin=dict(l=16, r=16, t=8, b=16),
    height=320,
    paper_bgcolor="white",
    plot_bgcolor="white",
    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    yaxis=dict(showgrid=True, gridcolor="#f1f5f9", zeroline=False, tickfont=dict(color="#94a3b8", size=11)),
    font=dict(family="ui-sans-serif, system-ui", color="#0f172a"),
    showlegend=False,
)


app.index_string = """<!DOCTYPE html>
<html lang="en">
<head>
  {%metas%}
  <title>{%title%}</title>
  {%favicon%}
  <style>
    :root { color-scheme: light; }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; background: #ffffff; color: #0f172a;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      -webkit-font-smoothing: antialiased; }
    .wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 64px 24px; }
    .stack { width: 100%; max-width: 760px; display: flex; flex-direction: column; gap: 40px; }
    .hero { display: flex; flex-direction: column; align-items: center; gap: 16px; text-align: center; }
    .badge { display: inline-block; border: 1px solid #e2e8f0; background: #f8fafc; color: #475569;
      font-size: 12px; font-weight: 500; padding: 4px 10px; border-radius: 999px; }
    .title { font-size: 36px; font-weight: 600; letter-spacing: -0.02em; color: #0f172a; margin: 0; }
    .subtitle { max-width: 560px; margin: 0; color: #64748b; font-size: 16px; line-height: 1.6; }
    .card { border: 1px solid #e2e8f0; background: #ffffff; border-radius: 12px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); overflow: hidden; }
    .card-head { display: flex; align-items: center; justify-content: space-between;
      padding: 12px 20px; border-bottom: 1px solid #f1f5f9; }
    .card-title { font-size: 14px; font-weight: 500; color: #0f172a; }
    .muted { font-size: 12px; color: #94a3b8; }
  </style>
  {%css%}
</head>
<body>
  {%app_entry%}
  <footer>
    {%config%}
    {%scripts%}
    {%renderer%}
  </footer>
</body>
</html>"""


app.layout = html.Div(
    className="wrap",
    children=html.Div(
        className="stack",
        children=[
            html.Div(
                className="hero",
                children=[
                    html.Span("Quant Research", className="badge"),
                    html.H1("What would you like to build today?", className="title"),
                    html.P(
                        "Start from a question, not a model. The market rewards patience, honest data, and small experiments repeated with care.",
                        className="subtitle",
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    html.Div(
                        className="card-head",
                        children=[
                            html.Span("Sample series", className="card-title"),
                            html.Span("mock data", className="muted"),
                        ],
                    ),
                    dcc.Graph(id="chart", figure=_FIG, config={"displayModeBar": False}),
                ],
            ),
        ],
    ),
)


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
