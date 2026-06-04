import os
import psycopg2
import pandas as pd
import streamlit as st
import plotly.express as px

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DataForge — Olist Analytics",
    layout="wide",
    page_icon="📦",
)

st.title("📦 Olist E-commerce Analytics")
st.caption("Brazilian e-commerce · 2016–2018 · Powered by DataForge")

# ── Database ───────────────────────────────────────────────────────────────────

def _conn_params() -> dict:
    return dict(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = psycopg2.connect(**_conn_params())
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        conn.close()


# ── Filter helpers ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_filter_options():
    states = run_query(
        "SELECT DISTINCT state FROM warehouse.dim_customer ORDER BY state"
    )["state"].tolist()
    bounds = run_query(
        "SELECT MIN(full_date) AS mn, MAX(full_date) AS mx FROM warehouse.dim_date"
    )
    return states, bounds.iloc[0]["mn"], bounds.iloc[0]["mx"]


def _state_clause(states: tuple) -> str:
    return "AND dc.state = ANY(%s)" if states else ""


def _params(start, end, states: tuple) -> tuple:
    return (start, end, list(states)) if states else (start, end)


# ── Data loaders (all server-side aggregation) ─────────────────────────────────

@st.cache_data(ttl=300)
def load_kpis(start, end, states: tuple):
    sql = f"""
        SELECT
            COALESCE(SUM(fo.price), 0)              AS total_revenue,
            COUNT(DISTINCT fo.order_id)              AS total_orders,
            COALESCE(SUM(fo.freight_value), 0)       AS total_freight,
            COALESCE(SUM(fo.price), 0)
              / NULLIF(COUNT(DISTINCT fo.order_id), 0) AS avg_order_value
        FROM warehouse.fact_orders fo
        JOIN warehouse.dim_date     dd ON fo.date_key     = dd.date_key
        JOIN warehouse.dim_customer dc ON fo.customer_key = dc.customer_key
        WHERE dd.full_date BETWEEN %s AND %s
        {_state_clause(states)}
    """
    return run_query(sql, _params(start, end, states)).iloc[0]


@st.cache_data(ttl=300)
def load_top_category(start, end, states: tuple) -> str:
    sql = f"""
        SELECT COALESCE(dp.category_name, 'unknown') AS cat, SUM(fo.price) AS rev
        FROM warehouse.fact_orders fo
        JOIN warehouse.dim_date     dd ON fo.date_key     = dd.date_key
        JOIN warehouse.dim_customer dc ON fo.customer_key = dc.customer_key
        LEFT JOIN warehouse.dim_product dp ON fo.product_key = dp.product_key
        WHERE dd.full_date BETWEEN %s AND %s
        {_state_clause(states)}
        GROUP BY 1 ORDER BY rev DESC LIMIT 1
    """
    df = run_query(sql, _params(start, end, states))
    return df.iloc[0]["cat"].replace("_", " ").title() if not df.empty else "—"


@st.cache_data(ttl=300)
def load_monthly_trend(start, end, states: tuple) -> pd.DataFrame:
    sql = f"""
        SELECT
            DATE_TRUNC('month', dd.full_date)::date AS month,
            SUM(fo.price)                           AS revenue,
            COUNT(DISTINCT fo.order_id)             AS orders
        FROM warehouse.fact_orders fo
        JOIN warehouse.dim_date     dd ON fo.date_key     = dd.date_key
        JOIN warehouse.dim_customer dc ON fo.customer_key = dc.customer_key
        WHERE dd.full_date BETWEEN %s AND %s
        {_state_clause(states)}
        GROUP BY 1 ORDER BY 1
    """
    return run_query(sql, _params(start, end, states))


@st.cache_data(ttl=300)
def load_top_categories(start, end, states: tuple, n: int = 10) -> pd.DataFrame:
    sql = f"""
        SELECT
            COALESCE(dp.category_name, 'unknown') AS category,
            SUM(fo.price)                          AS revenue,
            COUNT(DISTINCT fo.order_id)            AS orders
        FROM warehouse.fact_orders fo
        JOIN warehouse.dim_date     dd ON fo.date_key     = dd.date_key
        JOIN warehouse.dim_customer dc ON fo.customer_key = dc.customer_key
        LEFT JOIN warehouse.dim_product dp ON fo.product_key = dp.product_key
        WHERE dd.full_date BETWEEN %s AND %s
        {_state_clause(states)}
        GROUP BY 1 ORDER BY revenue DESC LIMIT {n}
    """
    df = run_query(sql, _params(start, end, states))
    df["category"] = df["category"].str.replace("_", " ").str.title()
    return df


@st.cache_data(ttl=300)
def load_state_revenue(start, end, states: tuple) -> pd.DataFrame:
    sql = f"""
        SELECT
            dc.state,
            SUM(fo.price)               AS revenue,
            COUNT(DISTINCT fo.order_id) AS orders
        FROM warehouse.fact_orders fo
        JOIN warehouse.dim_date     dd ON fo.date_key     = dd.date_key
        JOIN warehouse.dim_customer dc ON fo.customer_key = dc.customer_key
        WHERE dd.full_date BETWEEN %s AND %s
        {_state_clause(states)}
        GROUP BY 1 ORDER BY revenue DESC
    """
    return run_query(sql, _params(start, end, states))


# ── Sidebar ────────────────────────────────────────────────────────────────────

states_list, min_date, max_date = load_filter_options()

with st.sidebar:
    st.header("Filters")

    date_range = st.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    selected_states = st.multiselect(
        "State",
        options=states_list,
        placeholder="All states",
    )
    st.divider()
    st.caption("Data refreshes every 5 min.")

# Ensure both dates are selected
if not isinstance(date_range, (list, tuple)) or len(date_range) < 2:
    st.info("Please select a complete date range.")
    st.stop()

start_date, end_date = date_range[0], date_range[1]
states_key = tuple(selected_states)          # hashable for st.cache_data

# ── KPI Row ────────────────────────────────────────────────────────────────────

kpis     = load_kpis(start_date, end_date, states_key)
top_cat  = load_top_category(start_date, end_date, states_key)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Revenue",    f"R$ {kpis['total_revenue']:,.0f}")
c2.metric("Total Orders",     f"{int(kpis['total_orders']):,}")
c3.metric("Avg Order Value",  f"R$ {kpis['avg_order_value']:,.0f}")
c4.metric("Top Category",     top_cat)

st.divider()

# ── Revenue trend ──────────────────────────────────────────────────────────────

trend = load_monthly_trend(start_date, end_date, states_key)

if not trend.empty:
    trend["month"] = pd.to_datetime(trend["month"])
    fig_trend = px.line(
        trend,
        x="month", y="revenue",
        title="Monthly Revenue",
        labels={"month": "", "revenue": "Revenue (R$)"},
        markers=True,
        color_discrete_sequence=["#1f77b4"],
    )
    fig_trend.update_layout(hovermode="x unified")
    st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# ── Bottom charts ──────────────────────────────────────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    cats = load_top_categories(start_date, end_date, states_key)
    if not cats.empty:
        cats_sorted = cats.sort_values("revenue")
        fig_cat = px.bar(
            cats_sorted,
            x="revenue", y="category",
            orientation="h",
            title="Top 10 Product Categories",
            labels={"revenue": "Revenue (R$)", "category": ""},
            color="revenue",
            color_continuous_scale="Blues",
        )
        fig_cat.update_coloraxes(showscale=False)
        st.plotly_chart(fig_cat, use_container_width=True)

with col_right:
    state_rev = load_state_revenue(start_date, end_date, states_key)
    if not state_rev.empty:
        fig_state = px.bar(
            state_rev,
            x="state", y="revenue",
            title="Revenue by State",
            labels={"state": "State", "revenue": "Revenue (R$)"},
            color="revenue",
            color_continuous_scale="Oranges",
        )
        fig_state.update_coloraxes(showscale=False)
        st.plotly_chart(fig_state, use_container_width=True)

# ── Footer ─────────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    "DataForge · Stack: Python · Airflow · PostgreSQL · dbt · Pandera · Streamlit · Docker"
)
