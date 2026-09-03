"""
CSE Market Regime & Sector Rotation Dashboard.

Run with: streamlit run app.py

Pages:
  - Market Overview: ASPI trend, regime timeline
  - Sector Rotation: which sectors lead/lag by regime
  - Foreign Activity: net foreign investor flows
  - Company Explorer: individual ticker price history
  - Event Study: dividend ex-date price reaction explorer
  - About / Methodology: data provenance and limitations

DESIGN NOTE (for future maintainers): all data loading, file paths,
dataframe keys, and filtering/aggregation logic are UNCHANGED from the
original functional version of this file. Everything added here is
presentation-layer only: design tokens, injected CSS, chart theming,
and small HTML-rendering helpers (kpi_card, ticker tape, page headers,
info/empty-state panels). Search for "==== DATA LOGIC" comments to find
the exact points where the original computations happen untouched.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"

st.set_page_config(
    page_title="CSE Market Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================ DESIGN TOKENS
# Grounded in the subject: a stock-exchange trading terminal at night.
# Deep ink-navy base (not pure black), a ticker-gold primary accent
# (evokes the exchange bell / scrolling tape rather than a generic SaaS
# blue), teal as a cool secondary, and green/red held to their real
# financial meaning (gains/losses) rather than spent as decoration.
COLORS = {
    "bg": "#080B13",
    "bg_alt": "#0D1220",
    "surface": "#121729",
    "surface_alt": "#171D33",
    "border": "#242B45",
    "border_soft": "#1A2038",
    "text": "#E7E9F3",
    "text_muted": "#8890AC",
    "text_dim": "#5B6280",
    "gold": "#F0B429",
    "gold_dim": "#B8860F",
    "teal": "#2DD4BF",
    "green": "#34D399",
    "red": "#FB7185",
    "amber": "#FBBF24",
    "slate": "#7C88A8",
}
C = COLORS  # short alias used throughout

REGIME_COLORS = {
    "Bull / Stable Growth": C["green"],
    "Volatile Recovery": C["amber"],
    "Crisis / Sell-off": C["red"],
    "Bear / Quiet Decline": C["slate"],
}

NAV_OPTIONS = {
    "🏠  Market Overview": "Market Overview",
    "🔄  Sector Rotation": "Sector Rotation",
    "🌍  Foreign Activity": "Foreign Activity",
    "🔍  Company Explorer": "Company Explorer",
    "📊  Event Study": "Event Study",
    "📖  About / Methodology": "About / Methodology",
}

PAGE_META = {
    "Market Overview": ("MARKET INTELLIGENCE", "Market Overview",
                         "ASPI trend and algorithmically detected market regimes."),
    "Sector Rotation": ("SECTOR ANALYSIS", "Sector Rotation",
                         "Which sectors lead and lag within each detected regime."),
    "Foreign Activity": ("CAPITAL FLOWS", "Foreign Investor Activity",
                          "Net foreign vs. local investor flows over time."),
    "Company Explorer": ("SECURITY LOOKUP", "Company Price Explorer",
                          "Individual ticker price history, 2021–2025."),
    "Event Study": ("EVENT STUDY", "Dividend Event Study",
                     "Abnormal price reaction around dividend ex-dates."),
    "About / Methodology": ("DOCUMENTATION", "About / Methodology",
                             "Data provenance, scope decisions, and known limitations."),
}


# ================================================================ CSS INJECT
def inject_css():
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap');

:root {{
    --bg: {C['bg']}; --bg-alt: {C['bg_alt']};
    --surface: {C['surface']}; --surface-alt: {C['surface_alt']};
    --border: {C['border']}; --border-soft: {C['border_soft']};
    --text: {C['text']}; --text-muted: {C['text_muted']}; --text-dim: {C['text_dim']};
    --gold: {C['gold']}; --teal: {C['teal']};
    --green: {C['green']}; --red: {C['red']}; --amber: {C['amber']}; --slate: {C['slate']};
}}

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, sans-serif;
}}

/* ---- page background: subtle radial glow, not flat black ---- */
[data-testid="stAppViewContainer"] {{
    background:
        radial-gradient(ellipse 1200px 600px at 15% -10%, rgba(240,180,41,0.06), transparent 60%),
        radial-gradient(ellipse 1000px 500px at 100% 0%, rgba(45,212,191,0.05), transparent 55%),
        var(--bg);
}}
[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}

/* ---- sidebar ---- */
[data-testid="stSidebar"] {{
    background: var(--bg-alt);
    border-right: 1px solid var(--border-soft);
}}
[data-testid="stSidebar"] > div:first-child {{ padding-top: 1.2rem; }}

.brand-block {{
    padding: 0 0.4rem 1.1rem 0.4rem;
    margin-bottom: 0.8rem;
    border-bottom: 1px solid var(--border-soft);
}}
.brand-name {{
    font-family: 'Sora', sans-serif; font-weight: 700; font-size: 1.15rem;
    color: var(--text); letter-spacing: -0.01em;
    display: flex; align-items: center; gap: 0.45rem;
}}
.brand-dot {{
    width: 8px; height: 8px; border-radius: 50%; background: var(--gold);
    box-shadow: 0 0 8px 1px rgba(240,180,41,0.7);
    animation: pulse 2.4s ease-in-out infinite;
}}
.brand-sub {{
    font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem;
    color: var(--text-dim); margin-top: 0.3rem; letter-spacing: 0.03em;
}}
@keyframes pulse {{
    0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.35; }}
}}

/* nav radio -> pill list */
div[role="radiogroup"] {{ gap: 0.15rem; }}
div[role="radiogroup"] label {{
    padding: 0.55rem 0.7rem !important;
    border-radius: 9px;
    transition: background 0.15s ease, color 0.15s ease;
    font-size: 0.88rem;
    color: var(--text-muted);
}}
div[role="radiogroup"] label:hover {{ background: var(--surface); color: var(--text); }}
div[role="radiogroup"] label:has(input:checked) {{
    background: linear-gradient(90deg, rgba(240,180,41,0.14), rgba(240,180,41,0.02));
    color: var(--gold) !important;
    font-weight: 600;
    border-left: 2px solid var(--gold);
}}
div[role="radiogroup"] label > div:first-child {{ display: none; }}

.sidebar-footer {{
    margin-top: 1.4rem; padding-top: 0.9rem; border-top: 1px solid var(--border-soft);
    font-family: 'IBM Plex Mono', monospace; font-size: 0.66rem; color: var(--text-dim);
    line-height: 1.6;
}}
.sidebar-footer b {{ color: var(--text-muted); }}

/* ---- main content entrance ---- */
.main .block-container {{
    padding-top: 1.3rem; max-width: 1300px;
    animation: fadeInUp 0.45s ease-out both;
}}
@keyframes fadeInUp {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
@media (prefers-reduced-motion: reduce) {{
    .main .block-container {{ animation: none; }}
    .brand-dot {{ animation: none; }}
}}

/* ---- ticker tape (signature element) ---- */
.ticker-wrap {{
    overflow: hidden; white-space: nowrap;
    background: var(--surface);
    border: 1px solid var(--border-soft);
    border-radius: 10px;
    padding: 0.55rem 0;
    margin-bottom: 1.4rem;
    position: relative;
}}
.ticker-wrap::before, .ticker-wrap::after {{
    content: ""; position: absolute; top: 0; bottom: 0; width: 36px; z-index: 2;
}}
.ticker-wrap::before {{ left: 0; background: linear-gradient(90deg, var(--surface), transparent); }}
.ticker-wrap::after {{ right: 0; background: linear-gradient(270deg, var(--surface), transparent); }}
.ticker-track {{
    display: inline-block; white-space: nowrap;
    animation: ticker-scroll 38s linear infinite;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.82rem;
}}
.ticker-wrap:hover .ticker-track {{ animation-play-state: paused; }}
@keyframes ticker-scroll {{
    from {{ transform: translateX(0); }}
    to {{ transform: translateX(-50%); }}
}}
@media (prefers-reduced-motion: reduce) {{
    .ticker-track {{ animation: none; overflow-x: auto; }}
}}
.ticker-item {{ padding: 0 1.3rem; color: var(--text-muted); }}
.ticker-item b {{ color: var(--text); font-weight: 600; }}
.ticker-sep {{ color: var(--border); }}

/* ---- page header ---- */
.page-eyebrow {{
    font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem;
    letter-spacing: 0.14em; color: var(--gold); font-weight: 500;
    margin-bottom: 0.35rem;
}}
.page-title {{
    font-family: 'Sora', sans-serif; font-weight: 700;
    font-size: clamp(1.5rem, 2.4vw, 2rem); color: var(--text);
    letter-spacing: -0.02em; margin-bottom: 0.3rem;
}}
.page-desc {{ color: var(--text-muted); font-size: 0.94rem; margin-bottom: 1.3rem; }}

/* ---- kpi cards ---- */
.kpi-card {{
    background: var(--surface);
    border: 1px solid var(--border-soft);
    border-radius: 12px;
    padding: 1rem 1.1rem;
    height: 100%;
    transition: border-color 0.15s ease, transform 0.15s ease;
}}
.kpi-card:hover {{ border-color: var(--border); transform: translateY(-1px); }}
.kpi-label {{
    font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem;
    letter-spacing: 0.08em; color: var(--text-dim); text-transform: uppercase;
    margin-bottom: 0.45rem;
}}
.kpi-value {{
    font-family: 'Sora', sans-serif; font-weight: 700; font-size: 1.55rem;
    color: var(--text); line-height: 1.1;
}}
.kpi-sub {{ font-size: 0.78rem; margin-top: 0.4rem; color: var(--text-muted); }}
.kpi-positive .kpi-value {{ color: var(--green); }}
.kpi-negative .kpi-value {{ color: var(--red); }}
.kpi-gold .kpi-value {{ color: var(--gold); }}
.kpi-teal .kpi-value {{ color: var(--teal); }}

.regime-badge {{
    display: inline-block; padding: 0.15rem 0.6rem; border-radius: 100px;
    font-size: 0.85rem; font-weight: 600; font-family: 'Sora', sans-serif;
}}

/* ---- info / empty panels ---- */
.info-panel {{
    background: var(--surface-alt);
    border-left: 3px solid var(--gold);
    border-radius: 6px;
    padding: 0.7rem 0.95rem;
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-bottom: 1.1rem;
    line-height: 1.55;
}}
.info-panel b {{ color: var(--text); }}
.empty-state {{
    border: 1px dashed var(--border);
    border-radius: 10px;
    padding: 2.2rem 1.5rem;
    text-align: center;
    color: var(--text-dim);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
}}

.section-label {{
    font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem;
    letter-spacing: 0.1em; color: var(--text-dim); text-transform: uppercase;
    margin: 1.6rem 0 0.6rem 0;
}}

/* ---- widget skinning ---- */
div[data-baseweb="select"] > div {{
    background: var(--surface) !important;
    border-color: var(--border-soft) !important;
    border-radius: 8px !important;
}}
[data-testid="stDataFrame"] {{
    border: 1px solid var(--border-soft); border-radius: 10px; overflow: hidden;
}}
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {{
    background: rgba(240,180,41,0.16) !important; color: var(--gold) !important;
}}

/* focus visibility (accessibility floor) */
button:focus-visible, [role="radio"]:focus-visible, div[data-baseweb="select"]:focus-within {{
    outline: 2px solid var(--gold) !important; outline-offset: 2px;
}}

/* scrollbar */
::-webkit-scrollbar {{ width: 9px; height: 9px; }}
::-webkit-scrollbar-track {{ background: var(--bg-alt); }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 6px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--text-dim); }}
</style>
""", unsafe_allow_html=True)


# ============================================================ RENDER HELPERS
def page_header(page_key: str):
    eyebrow, title, desc = PAGE_META[page_key]
    st.markdown(f"""
<div class="page-eyebrow">{eyebrow}</div>
<div class="page-title">{title}</div>
<div class="page-desc">{desc}</div>
""", unsafe_allow_html=True)


def kpi_card(label: str, value: str, sub: str = "", tone: str = "neutral") -> str:
    tone_class = {"positive": "kpi-positive", "negative": "kpi-negative",
                  "gold": "kpi-gold", "teal": "kpi-teal", "neutral": ""}.get(tone, "")
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f"""<div class="kpi-card {tone_class}">
<div class="kpi-label">{label}</div>
<div class="kpi-value">{value}</div>
{sub_html}
</div>"""


def render_kpis(items: list[dict]):
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        col.markdown(
            kpi_card(item["label"], item["value"], item.get("sub", ""), item.get("tone", "neutral")),
            unsafe_allow_html=True,
        )


def info_panel(html: str):
    st.markdown(f'<div class="info-panel">{html}</div>', unsafe_allow_html=True)


def empty_state(message: str):
    st.markdown(f'<div class="empty-state">⚠ &nbsp;{message}</div>', unsafe_allow_html=True)


def section_label(text: str):
    st.markdown(f'<div class="section-label">{text}</div>', unsafe_allow_html=True)


def apply_chart_theme(fig, height: int = 440):
    """Consistent dark-terminal theme applied to every Plotly figure."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=C["text_muted"], size=12),
        title_font=dict(family="Sora, sans-serif", color=C["text"], size=15),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=C["text_muted"], size=11),
                    orientation="h", y=-0.18),
        height=height,
        margin=dict(l=10, r=10, t=45, b=10),
        hoverlabel=dict(bgcolor=C["surface_alt"], bordercolor=C["border"],
                         font=dict(color=C["text"], family="IBM Plex Mono", size=11)),
        xaxis=dict(gridcolor=C["border_soft"], zerolinecolor=C["border"], color=C["text_dim"],
                    linecolor=C["border_soft"]),
        yaxis=dict(gridcolor=C["border_soft"], zerolinecolor=C["border"], color=C["text_dim"],
                    linecolor=C["border_soft"]),
    )
    return fig


def render_ticker_tape(data: dict):
    """Signature element: a live scrolling summary strip built from the
    same dataframes every page already loads — not decorative filler."""
    items = []

    regimes = data.get("regimes", pd.DataFrame())
    if not regimes.empty:
        latest = regimes.iloc[-1]
        regime_color = REGIME_COLORS.get(latest["regime"], C["text_muted"])
        items.append(f'ASPI <b>{latest["close"]:,.0f}</b>')
        items.append(f'REGIME <b style="color:{regime_color}">{latest["regime"].upper()}</b>')

    sm = data.get("sector_merged", pd.DataFrame())
    if not sm.empty:
        latest_month = sm["month"].max()
        month_slice = sm[sm["month"] == latest_month].sort_values("mom_return", ascending=False)
        if len(month_slice):
            top = month_slice.iloc[0]
            arrow = "▲" if top["mom_return"] >= 0 else "▼"
            arrow_color = C["green"] if top["mom_return"] >= 0 else C["red"]
            items.append(
                f'TOP SECTOR <b>{top["sector"]}</b> '
                f'<b style="color:{arrow_color}">{arrow} {top["mom_return"]:+.1%}</b>'
            )

    fa = data.get("foreign_activity", pd.DataFrame())
    if not fa.empty:
        net_foreign = fa[(fa["transaction_type"] == "net") & (fa["investor_type"] == "Total Foreign")]
        net_foreign = net_foreign.sort_values("date")
        if len(net_foreign):
            latest_flow = net_foreign.iloc[-1]
            direction = "NET BUYING" if latest_flow["value"] >= 0 else "NET SELLING"
            dcolor = C["green"] if latest_flow["value"] >= 0 else C["red"]
            items.append(f'FOREIGN FLOW <b style="color:{dcolor}">{direction}</b>')
        items.append(f'DATA THROUGH <b>{fa["date"].max():%b %Y}</b>')

    if not items:
        return

    sep = '<span class="ticker-sep">&nbsp;•&nbsp;</span>'
    strip = sep.join(f'<span class="ticker-item">{it}</span>' for it in items)
    # duplicated for a seamless -50% translateX loop
    st.markdown(f"""
<div class="ticker-wrap"><div class="ticker-track">{strip}{sep}{strip}{sep}</div></div>
""", unsafe_allow_html=True)


def style_car_table(df: pd.DataFrame):
    def _color(v):
        if pd.isna(v):
            return ""
        color = C["green"] if v >= 0 else C["red"]
        return f"color: {color}; font-weight: 600;"
    return (
        df.style
        .format({"car": "{:+.2%}", "dividend_rate": "{:.2f}"})
        .map(_color, subset=["car"])
    )


# ==================================================================== DATA
# ==== DATA LOGIC: unchanged from the original — same paths, same keys.
@st.cache_data
def load_data():
    data = {}
    for name, path in [
        ("regimes", PROCESSED / "regime_timeline.parquet"),
        ("sector_ranking", PROCESSED / "sector_rotation_ranking.parquet"),
        ("sector_merged", PROCESSED / "sector_rotation_merged.parquet"),
        ("event_study", PROCESSED / "event_study_dividends.parquet"),
        ("foreign_activity", INTERIM / "foreign_activity.parquet"),
        ("securities", INTERIM / "securities_master.parquet"),
        ("prices", INTERIM / "daily_prices_2021_2025.parquet"),
    ]:
        data[name] = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    return data


inject_css()
data = load_data()

# ==================================================================== SIDEBAR
with st.sidebar:
    st.markdown("""
<div class="brand-block">
  <div class="brand-name"><span class="brand-dot"></span> CSE MARKET TERMINAL</div>
  <div class="brand-sub">REGIME &amp; SECTOR INTELLIGENCE&nbsp;·&nbsp;2021&ndash;2025</div>
</div>
""", unsafe_allow_html=True)

    nav_choice = st.radio("Navigate", list(NAV_OPTIONS.keys()), label_visibility="collapsed")
    page = NAV_OPTIONS[nav_choice]

    regimes_for_footer = data.get("regimes", pd.DataFrame())
    span = (f'{regimes_for_footer["date"].min():%Y-%m} &rarr; {regimes_for_footer["date"].max():%Y-%m}'
            if not regimes_for_footer.empty else "n/a")
    st.markdown(f"""
<div class="sidebar-footer">
  <b>DATA SPAN</b><br>{span}<br><br>
  <b>SOURCE</b><br>Colombo Stock Exchange<br><br>
  <b>STATUS</b><br>Practice project · not investment advice
</div>
""", unsafe_allow_html=True)

render_ticker_tape(data)

# ---------------------------------------------------------------- Overview
if page == "Market Overview":
    page_header(page)
    regimes = data["regimes"]  # ==== DATA LOGIC: unchanged

    if regimes.empty:
        empty_state("Regime data not found. Run <code>python -m src.models.regime_detection</code> first.")
    else:
        latest = regimes.iloc[-1]  # ==== DATA LOGIC: unchanged
        regime_color = REGIME_COLORS.get(latest["regime"], C["text_muted"])
        render_kpis([
            {"label": "Latest ASPI", "value": f'{regimes["close"].iloc[-1]:,.0f}', "tone": "gold"},
            {"label": "Current Regime",
             "value": f'<span class="regime-badge" style="background:{regime_color}22;color:{regime_color}">{latest["regime"]}</span>',
             "tone": "neutral"},
            {"label": "Data Span",
             "value": f'{regimes["date"].min():%Y-%m}', "sub": f'through {regimes["date"].max():%Y-%m}'},
        ])

        section_label("ASPI COLORED BY DETECTED REGIME")
        fig = go.Figure()  # ==== DATA LOGIC: unchanged (regime scatter)
        for regime, color in REGIME_COLORS.items():
            subset = regimes[regimes["regime"] == regime]
            if subset.empty:
                continue
            fig.add_trace(go.Scatter(
                x=subset["date"], y=subset["close"], mode="markers",
                name=regime, marker=dict(size=3.5, color=color, opacity=0.85),
            ))
        fig = apply_chart_theme(fig, height=460)
        st.plotly_chart(fig, use_container_width=True)

        section_label("REGIME SUMMARY STATISTICS")
        summary = regimes.groupby("regime").agg(  # ==== DATA LOGIC: unchanged
            trading_days=("date", "count"),
            avg_20d_return=("roll_return_20d", "mean"),
            avg_annualized_vol=("roll_vol_20d", "mean"),
            avg_drawdown=("drawdown", "mean"),
        ).round(4)
        st.dataframe(summary, use_container_width=True)

        info_panel(
            "Regimes are detected via <b>KMeans clustering</b> on rolling return/volatility/"
            "drawdown features, then labeled by rule (not learned). Cross-checked against known "
            "events: COVID-19 (2020-03), the 2022 sovereign default, and the 2022 political "
            "crisis all correctly fall in <b>'Crisis / Sell-off'</b>. See About / Methodology."
        )

# ---------------------------------------------------------------- Sector Rotation
elif page == "Sector Rotation":
    page_header(page)
    ranking = data["sector_ranking"]  # ==== DATA LOGIC: unchanged

    if ranking.empty:
        empty_state("Sector rotation data not found. Run <code>python -m src.features.sector_rotation</code> first.")
    else:
        info_panel(
            "Analysis window: <b>2021&ndash;2025 only</b>, to stay within one consistent sector "
            "classification scheme (CSE changed sector taxonomy around 2016 — see "
            "About / Methodology). Some thin sectors show extreme % swings from a small "
            "market-cap base; treat outliers with caution."
        )
        regime_options = ranking["regime"].unique().tolist()  # ==== DATA LOGIC: unchanged
        selected_regime = st.selectbox("Select regime", regime_options)

        subset = ranking[ranking["regime"] == selected_regime].sort_values(  # ==== DATA LOGIC: unchanged
            "avg_monthly_return", ascending=False
        )

        top15 = subset.head(15).iloc[::-1]  # reverse for horizontal bar top-to-bottom read order
        bar_colors = [C["green"] if v >= 0 else C["red"] for v in top15["avg_monthly_return"]]
        fig = go.Figure(go.Bar(
            x=top15["avg_monthly_return"], y=top15["sector"], orientation="h",
            marker_color=bar_colors, marker_line_width=0,
        ))
        fig.update_layout(title=f"Top sectors during '{selected_regime}'",
                           xaxis_title="Avg monthly market-cap growth", xaxis_tickformat=".0%")
        fig = apply_chart_theme(fig, height=500)
        st.plotly_chart(fig, use_container_width=True)

        section_label("FULL RANKING")
        display_df = subset.copy()
        display_df["avg_monthly_return"] = display_df["avg_monthly_return"].map("{:+.2%}".format)
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Foreign Activity
elif page == "Foreign Activity":
    page_header(page)
    fa = data["foreign_activity"]  # ==== DATA LOGIC: unchanged

    if fa.empty:
        empty_state("Foreign activity data not found.")
    else:
        net = fa[fa["transaction_type"] == "net"]  # ==== DATA LOGIC: unchanged
        investor_options = net["investor_type"].unique().tolist()
        selected = st.multiselect("Investor category", investor_options,
                                   default=["Total Foreign", "Total Local"])

        subset = net[net["investor_type"].isin(selected)]  # ==== DATA LOGIC: unchanged
        subset = subset[subset["date"] >= "2018-01-01"]

        palette = [C["gold"], C["teal"], C["green"], C["red"], C["amber"], C["slate"]]
        fig = px.line(subset, x="date", y="value", color="investor_type",
                       color_discrete_sequence=palette)
        fig.update_layout(title="Net purchases (Rs.) — positive = net buying")
        fig.update_traces(line=dict(width=2))
        fig = apply_chart_theme(fig, height=460)
        st.plotly_chart(fig, use_container_width=True)

        info_panel(
            "Net = Purchases &minus; Sales for that investor category. Sri Lanka's 2022 "
            "sovereign default period is visible as a shift in foreign vs. local flows — "
            "worth comparing against the Market Overview regime timeline."
        )

# ---------------------------------------------------------------- Company Explorer
elif page == "Company Explorer":
    page_header(page)
    prices = data["prices"]  # ==== DATA LOGIC: unchanged
    securities = data["securities"]

    if prices.empty:
        empty_state("Price data not found.")
    else:
        ord_prices = prices[prices["main_type"] == "N"]  # ==== DATA LOGIC: unchanged
        tickers = sorted(ord_prices["ticker"].unique())
        default_idx = tickers.index("COMB") if "COMB" in tickers else 0
        ticker = st.selectbox("Select ticker", tickers, index=default_idx)

        company_row = securities[securities["ticker"] == ticker]  # ==== DATA LOGIC: unchanged
        company_name = company_row.iloc[0]["company_name"] if not company_row.empty else ticker

        hist = ord_prices[ord_prices["ticker"] == ticker].sort_values("date")  # ==== DATA LOGIC: unchanged

        ret_20d_sub, ret_20d_tone = "n/a", "neutral"
        if len(hist) > 20:
            ret_20d = hist["close"].iloc[-1] / hist["close"].iloc[-21] - 1  # ==== DATA LOGIC: unchanged
            ret_20d_sub = f"{ret_20d:+.1%}"
            ret_20d_tone = "positive" if ret_20d >= 0 else "negative"

        render_kpis([
            {"label": "Security", "value": ticker, "sub": company_name, "tone": "gold"},
            {"label": "Latest Close",
             "value": f'Rs. {hist["close"].iloc[-1]:,.2f}' if len(hist) else "n/a"},
            {"label": "20-Day Return", "value": ret_20d_sub, "tone": ret_20d_tone},
            {"label": "Trading Days", "value": f"{len(hist):,}"},
        ])

        section_label("CLOSING PRICE")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist["date"], y=hist["close"], mode="lines", name="Close",
            line=dict(color=C["gold"], width=1.8),
            fill="tozeroy", fillcolor="rgba(240,180,41,0.06)",
        ))
        fig.update_layout(title=f"{ticker} — closing price", yaxis_title="Price (Rs.)")
        fig = apply_chart_theme(fig, height=440)
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- Event Study
elif page == "Event Study":
    page_header(page)
    study = data["event_study"]  # ==== DATA LOGIC: unchanged

    if study.empty:
        empty_state(
            "Event study output is empty. Restore <code>data/raw/Dividends.xls</code> "
            "and run <code>python -m features.event_study</code> first."
        )
    else:
        info_panel(
            "Cumulative Abnormal Return (CAR) = stock return &minus; ASPI return, summed over "
            "a &plusmn;5 trading-day window around the dividend ex-date. Simplified "
            "market-adjusted model (assumes beta=1); implausible daily returns (&gt;50%, "
            "likely data errors in the raw source) are filtered out. See About / Methodology."
        )
        pos_share = (study["car"] > 0).mean()  # ==== DATA LOGIC: unchanged
        render_kpis([
            {"label": "Events Analyzed", "value": f"{len(study):,}"},
            {"label": "Median CAR", "value": f'{study["car"].median():+.1%}',
             "tone": "positive" if study["car"].median() >= 0 else "negative"},
            {"label": "Share Positive CAR", "value": f"{pos_share:.1%}", "tone": "teal"},
        ])

        section_label("DISTRIBUTION OF CAR AROUND EX-DIVIDEND DATES")
        fig = px.histogram(study, x="car", nbins=60, color_discrete_sequence=[C["gold"]])
        fig.add_vline(x=0, line_dash="dash", line_color=C["text_dim"])
        fig.update_layout(xaxis_title="Cumulative Abnormal Return", xaxis_tickformat=".0%")
        fig = apply_chart_theme(fig, height=400)
        st.plotly_chart(fig, use_container_width=True)

        section_label("EVENT DETAIL")
        ticker_filter = st.selectbox("Filter by ticker (optional)",  # ==== DATA LOGIC: unchanged
                                      ["All"] + sorted(study["ticker"].unique().tolist()))
        table = study if ticker_filter == "All" else study[study["ticker"] == ticker_filter]
        st.dataframe(style_car_table(table.sort_values("ex_date", ascending=False)),
                     use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- About
else:
    page_header(page)
    st.markdown("""
This is a **practice project** built to develop hands-on understanding of
Colombo Stock Exchange (CSE) statistics data before starting a separate,
unrelated final-year research project (firm-level financial distress
prediction). It intentionally focuses on **market-level time series and
event analysis** rather than company-level classification.

### Scope decisions (documented, not hidden)
- **Daily price data**: 2021-2025 only. CSE's historical price archives use
  two other, structurally incompatible formats before 2021 (per-company
  header blocks for 2011-2020; a minimal 3-column format for 1991-2000).
  Parsing all three eras generically was judged out of scope for a practice
  project and is noted as a future extension.
- **Sector taxonomy**: CSE changed its sector classification scheme around
  2016 (old ~21-category scheme → GICS-aligned scheme). Sector-rotation
  analysis here is restricted to 2021-2025 to stay within one consistent
  taxonomy; old and new sector labels are deliberately **not** cross-mapped.
- **No per-company sector master file exists** in this dataset — CSE's
  "sector" files are already sector-level aggregates. Sector rotation
  therefore runs at the sector-index level, not via a company→sector join.
- **Regime detection**: KMeans (k=4) on rolling return/volatility/drawdown
  features, with clusters labeled by rule based on their centroid
  statistics — not a Hidden Markov Model. Sanity-checked against known
  events: COVID-19 market closure, the 2022 sovereign default, and the 2022
  political crisis all correctly land in the detected "Crisis / Sell-off"
  regime.
- **Event study**: simplified market-adjusted model (beta = 1), not a full
  market model with estimated beta. Daily returns beyond ±50% are treated
  as data errors and excluded (one dividend event initially showed a
  98,500% CAR, traced to a single implausible day's return in the raw
  source file).

### Known data-quality issues found and handled
- Header rows are inconsistently positioned across files and years —
  handled with a reusable header-detection utility.
- A literal string `"Market Closed Due To COVID -19"` appears in place of a
  numeric value in the foreign activity file — coerced to NaN.
- Some tickers trade multiple share classes (ordinary/non-voting) under the
  same company code, causing duplicate (ticker, date) rows — resolved by
  restricting to ordinary (N) shares for per-ticker analysis.
- Sector names have decades of spelling/abbreviation drift ("Bank Finance
  Ins" vs "Banks, Finance & Insurance") — merged where safe; genuine
  taxonomy changes were not merged.

### Suggested next steps (not built here)
- Hidden Markov Model regime detection as a comparison to the KMeans approach
- Market-model event study with estimated per-stock beta
- Historical price ingestion for 2011-2020 and 1991-2000 (different formats)
    """)
