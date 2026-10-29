"""A small, local delivery dashboard. All records are fictional; seed = 42."""

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SEED = 42
TEAL = "#007F78"
ORANGE = "#D97732"


def generate_orders(n=1000, seed=SEED):
    """Create a fixed scenario, not a simulation calibrated to real companies."""
    rng = np.random.default_rng(seed)
    region = rng.choice(["North", "South", "East", "West"], n)
    method = rng.choice(["Standard", "Express", "Economy"], n, p=[0.5, 0.25, 0.25])
    category = rng.choice(["Electronics", "Industrial supplies", "Home goods", "Apparel"], n)
    order_date = pd.Timestamp("2025-01-01") + pd.to_timedelta(rng.integers(0, 354, n), unit="D")
    transit_days = pd.Series(method).map({"Standard": 4, "Express": 2, "Economy": 7}).to_numpy()
    promised_date = order_date + pd.to_timedelta(transit_days, unit="D")

    # Deliberate teaching assumptions: these effects are invented, not findings.
    late_probability = 0.12 + 0.13 * (region == "East") + 0.16 * (method == "Economy")
    late_probability += 0.07 * (category == "Electronics") + 0.10 * (order_date.month >= 10)
    late = rng.random(n) < late_probability
    offset = np.where(late, rng.integers(1, 7, n), rng.integers(-1, 1, n))
    actual_date = promised_date + pd.to_timedelta(offset, unit="D")
    orders = pd.DataFrame({
        "order_id": [f"ORD-{i:04d}" for i in range(1, n + 1)],
        "order_date": order_date, "promised_delivery_date": promised_date,
        "actual_delivery_date": actual_date, "shipping_method": method,
        "product_category": category, "region": region,
        "order_value": np.round(rng.uniform(25, 1500, n), 2),
    })
    return prepare_orders(orders)


def prepare_orders(orders):
    """Validate required fields and derive one consistent set of KPI columns."""
    orders = orders.copy()
    required = ["order_id", "order_date", "promised_delivery_date", "actual_delivery_date",
                "shipping_method", "product_category", "region", "order_value"]
    if set(required) - set(orders.columns):
        raise ValueError("Required order columns are missing.")
    if orders[required].isna().any().any() or orders["order_id"].duplicated().any():
        raise ValueError("Orders must have complete fields and unique IDs.")
    for column in ["order_date", "promised_delivery_date", "actual_delivery_date"]:
        orders[column] = pd.to_datetime(orders[column], errors="raise")
    if (orders["order_value"] <= 0).any():
        raise ValueError("Order values must be positive.")
    if (orders["promised_delivery_date"] < orders["order_date"]).any() or (
        orders["actual_delivery_date"] < orders["order_date"]).any():
        raise ValueError("Delivery dates cannot precede order dates.")
    signed_delay = (orders["actual_delivery_date"] - orders["promised_delivery_date"]).dt.days
    orders["delay_days"] = signed_delay.clip(lower=0)
    orders["on_time"] = signed_delay <= 0
    orders["order_month"] = orders["order_date"].dt.strftime("%Y-%m")
    return orders


def metrics(orders):
    """Average delay includes zero days for early and on-time orders."""
    count = len(orders)
    return {"orders": count, "late_orders": int((~orders["on_time"]).sum()),
            "on_time_pct": float(100 * orders["on_time"].mean()) if count else None,
            "avg_delay_days": float(orders["delay_days"].mean()) if count else None}


def performance(orders, dimension):
    """Keep denominators visible alongside every group-level rate."""
    groups = orders.groupby(dimension).agg(
        orders=("order_id", "size"), on_time_pct=("on_time", "mean"),
        avg_delay_days=("delay_days", "mean"))
    groups["on_time_pct"] *= 100
    return groups.reset_index()


def filter_orders(orders, regions, methods, categories, start, end):
    return orders.loc[
        orders["region"].isin(regions) & orders["shipping_method"].isin(methods)
        & orders["product_category"].isin(categories)
        & orders["order_date"].between(pd.Timestamp(start), pd.Timestamp(end))
    ].copy()


def recommendations(orders):
    """Suggest investigation, not a causal conclusion, from observed groups."""
    actions = [
        ("region", "Review the region's delivery exceptions and handoffs"),
        ("shipping_method", "Review carrier promises and dispatch timing"),
        ("product_category", "Check category-specific handling and fulfillment steps"),
    ]
    notes = []
    for dimension, action in actions:
        groups = performance(orders, dimension)
        groups = groups[groups["orders"] >= 10]
        if groups.empty:
            notes.append(f"Collect more {dimension.replace('_', ' ')} observations; no group has 10 orders.")
            continue
        worst = groups.sort_values(["avg_delay_days", "orders"], ascending=False).iloc[0]
        notes.append(f"{worst[dimension]}: {worst['avg_delay_days']:.2f} delay days/order; "
                     f"{worst['on_time_pct']:.1f}% on time across {int(worst['orders'])} orders. {action}.")
    return notes


def export_report():
    """Reproduce the full-dataset CSV, measured KPIs and shareable static figure."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    orders = generate_orders()
    (ROOT / "data").mkdir(exist_ok=True)
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    orders.to_csv(ROOT / "data" / "synthetic_orders.csv", index=False)
    summary = metrics(orders)
    (out / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    notes = recommendations(orders)
    (out / "recommendations.md").write_text(
        "# Synthetic scenario: investigation suggestions\n\n" + "\n".join(f"- {x}" for x in notes)
        + "\n\nThese associations reflect the generator, not actual business evidence.\n", encoding="utf-8")
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), layout="constrained")
    for dimension, filename, title, axis in [
        ("region", "by_region.csv", "On-time delivery by region", axes[0]),
        ("shipping_method", "by_shipping_method.csv", "On-time delivery by shipping", axes[1]),
        ("product_category", "by_category.csv", "On-time delivery by category", axes[2]),
    ]:
        group = performance(orders, dimension)
        group.to_csv(out / filename, index=False)
        axis.barh(group[dimension], group["on_time_pct"], color=TEAL)
        axis.set(title=title, xlabel="On time (%)", xlim=(0, 100))
        axis.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"SYNTHETIC DELIVERY SCENARIO | {summary['orders']:,} orders | seed {SEED}",
                 fontsize=13, fontweight="bold")
    fig.savefig(out / "delivery_summary.png", dpi=160)
    plt.close(fig)
    monthly = performance(orders, "order_month")
    monthly.to_csv(out / "monthly_performance.csv", index=False)
    fig, axis = plt.subplots(figsize=(10, 4), layout="constrained")
    axis.plot(monthly["order_month"], monthly["on_time_pct"], marker="o", color=TEAL)
    axis.set(title="Synthetic cohort: on-time delivery by order month", ylabel="On time (%)", ylim=(0, 100))
    axis.tick_params(axis="x", rotation=45)
    fig.savefig(out / "monthly_performance.png", dpi=160)
    plt.close(fig)
    print(json.dumps(summary, indent=2))
    print("\n".join(notes))


def run_dashboard():
    import plotly.express as px
    import streamlit as st

    st.set_page_config(page_title="Delivery Intelligence | Hitesh Mahajan", page_icon="📦", layout="wide")
    # Keep full date ranges readable in the desktop sidebar.
    st.markdown("<style>@media(min-width:768px){[data-testid='stSidebar']{min-width:300px;}}"
                ".block-container{padding-top:3rem;}</style>", unsafe_allow_html=True)
    st.caption("OPERATIONS ANALYTICS  /  HITESH MILIND MAHAJAN")
    st.title("Delivery performance")
    st.write("Find where delivery promises slip, then choose what to investigate first.")
    st.info("SYNTHETIC DEMO · 1,000 fictional delivered orders · seed 42 · No real company data")
    orders = generate_orders()
    dimensions = {"region": "Regions", "shipping_method": "Shipping methods", "product_category": "Categories"}
    options = {key: sorted(orders[key].unique().tolist()) for key in dimensions}
    date_range = (orders["order_date"].min().date(), orders["order_date"].max().date())

    def reset_filters():
        for key, choices in options.items():
            st.session_state[key] = choices
        st.session_state["dates"] = date_range

    st.sidebar.title("Explore the orders")
    st.sidebar.caption("All KPIs and recommendations follow these filters.")
    # Initialize state once; reset uses the same keys without competing defaults.
    st.session_state.setdefault("dates", date_range)
    for key, choices in options.items():
        st.session_state.setdefault(key, choices)
    dates = st.sidebar.date_input("Order date range",
                                  min_value=date_range[0], max_value=date_range[1], key="dates")
    selected = {}
    for key, label in dimensions.items():
        selected[key] = st.sidebar.multiselect(label, options[key], key=key)
    st.sidebar.button("Reset filters", on_click=reset_filters, width="stretch")
    st.sidebar.caption("Local only. No login, paid API or external data connection.")
    if len(dates) != 2:
        st.warning("Select both a start and an end date.")
        st.stop()
    view = filter_orders(orders, selected["region"], selected["shipping_method"],
                         selected["product_category"], dates[0], dates[1])
    if view.empty:
        st.warning("No orders match these filters. Choose a value in every filter or reset filters.")
        st.stop()
    result = metrics(view)
    st.caption(f"SHOWING {len(view):,} OF {len(orders):,} ORDERS · Group trends use order date")
    cards = st.columns(4)
    cards[0].metric("Delivered orders", f"{result['orders']:,}", border=True)
    cards[1].metric("On-time delivery", f"{result['on_time_pct']:.1f}%", border=True,
                    help="Delivered on or before the promised date / all filtered orders.")
    cards[2].metric("Average delay", f"{result['avg_delay_days']:.2f} days", border=True,
                    help="Mean of max(actual date - promised date, 0), including zero-delay orders.")
    cards[3].metric("Late orders", f"{result['late_orders']:,}", border=True)
    left, right = st.columns(2)
    for container, dimension, title, measure in [
        (left, "region", "Where promises are met", "on_time_pct"),
        (right, "shipping_method", "Where delay accumulates", "avg_delay_days"),
    ]:
        with container:
            st.subheader(title)
            group = performance(view, dimension)
            figure = px.bar(group, x=dimension, y=measure, text_auto=".1f", hover_data=["orders"],
                            color_discrete_sequence=[TEAL if measure == "on_time_pct" else ORANGE],
                            labels={dimension: "", "on_time_pct": "On time (%)", "avg_delay_days": "Delay days / order"})
            if measure == "on_time_pct":
                figure.update_yaxes(range=[0, 100])
            figure.update_layout(height=290, margin=dict(t=20, b=20))
            st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
    st.subheader("Delivery promises over time")
    monthly = performance(view, "order_month")
    line = px.line(monthly, x="order_month", y="on_time_pct", markers=True,
                   hover_data=["orders"], color_discrete_sequence=[TEAL],
                   labels={"order_month": "Order month", "on_time_pct": "On time (%)"})
    line.update_yaxes(range=[0, 100])
    line.update_layout(height=270, margin=dict(t=15, b=15))
    st.plotly_chart(line, width="stretch", config={"displayModeBar": False})
    st.subheader("Investigate next")
    st.caption("Highest average delay among groups with at least 10 orders. Associations are not causes.")
    for note in recommendations(view):
        st.write(f"• {note}")
    with st.expander("Category performance & order details"):
        st.dataframe(performance(view, "product_category").round(2), hide_index=True, width="stretch")
        st.dataframe(view.drop(columns="order_month"), hide_index=True, width="stretch")
    st.download_button("Download filtered orders (CSV)", view.to_csv(index=False),
                        "filtered_synthetic_orders.csv", "text/csv")
    with st.expander("Metric definitions & scenario assumptions"):
        st.markdown("**On time:** actual delivery date is on/before promised delivery date. "
                    "**Delay:** late calendar days, with early deliveries clipped to zero. "
                    "**Average delay:** all filtered orders, not just late orders. "
                    "**Trend:** grouped by order month; this is a completed-order cohort. "
                    "Order values use fictional currency units. The generator deliberately raises lateness "
                    "probability for East, Economy, Electronics and October–December. "
                    "Do not interpret the resulting differences as real-world findings.")


if __name__ == "__main__":
    if "--export" in sys.argv:
        export_report()
    else:
        run_dashboard()
