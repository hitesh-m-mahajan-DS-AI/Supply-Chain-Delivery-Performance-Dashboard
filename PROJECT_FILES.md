# Project 1: folder structure and copyable source files

Files are already created. These blocks are provided for review or copying. Generated data and binary images are recreated by `python app.py --export`; dashboard.png is a captured browser screenshot.

```text
projects/01-delivery-performance-dashboard/
  app.py
  test_dashboard.py
  requirements.txt
  .gitignore
  .streamlit/config.toml
  README.md
  PROJECT_FILES.md
  data/synthetic_orders.csv
  outputs/
    metrics.json
    by_region.csv
    by_shipping_method.csv
    by_category.csv
    monthly_performance.csv
    recommendations.md
    delivery_summary.png
    monthly_performance.png
    dashboard.png
    verification.md
```

## app.py

```python
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
```

## test_dashboard.py

```python
"""Run with: python -m unittest -v. Checks KPI meaning and real UI interactions."""
import unittest
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal
from streamlit.testing.v1 import AppTest

from app import filter_orders, generate_orders, metrics, prepare_orders, recommendations


class DashboardChecks(unittest.TestCase):
    def test_seed_and_date_integrity(self):
        first = generate_orders()
        assert_frame_equal(first, generate_orders())
        self.assertEqual(len(first), 1000)
        self.assertTrue(first["order_id"].is_unique)
        self.assertTrue((first["actual_delivery_date"] >= first["order_date"]).all())
        self.assertFalse(first.isna().any().any())

    def test_kpis_include_early_and_exactly_on_time(self):
        # Hand-calculated fixture: early, exactly on time, and two days late.
        source = pd.DataFrame({
            "order_id": ["A", "B", "C"], "order_date": ["2025-01-01"] * 3,
            "promised_delivery_date": ["2025-01-05"] * 3,
            "actual_delivery_date": ["2025-01-04", "2025-01-05", "2025-01-07"],
            "shipping_method": ["Standard"] * 3, "product_category": ["Apparel"] * 3,
            "region": ["North"] * 3, "order_value": [50, 100, 150],
        })
        result = metrics(prepare_orders(source))
        self.assertEqual(result["late_orders"], 1)
        self.assertAlmostEqual(result["on_time_pct"], 200 / 3)
        self.assertAlmostEqual(result["avg_delay_days"], 2 / 3)

    def test_missing_and_duplicate_data_are_rejected(self):
        orders = generate_orders(3)
        with self.assertRaises(ValueError):
            prepare_orders(orders.drop(columns="order_date"))
        with self.assertRaises(ValueError):
            prepare_orders(pd.concat([orders, orders.iloc[[0]]]))

    def test_empty_filter_and_small_sample(self):
        orders = generate_orders()
        empty = filter_orders(orders, [], ["Express"], ["Apparel"], "2025-01-01", "2025-12-31")
        self.assertEqual(metrics(empty)["orders"], 0)
        self.assertIsNone(metrics(empty)["on_time_pct"])
        self.assertEqual(len(recommendations(orders.head(1))), 3)

    def test_app_filter_empty_and_reset(self):
        app = AppTest.from_file(str(Path(__file__).with_name("app.py")), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "1,000")
        app.sidebar.multiselect(key="region").set_value(["East"]).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, f"{(generate_orders()['region'] == 'East').sum():,}")
        app.sidebar.multiselect(key="region").set_value([]).run()
        self.assertTrue(app.warning)
        self.assertEqual(len(app.metric), 0)
        app.sidebar.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "1,000")


if __name__ == "__main__":
    unittest.main()
```

## requirements.txt

```text
numpy==2.5.4
pandas==3.1.0
streamlit==1.66.1
plotly==6.9.0
matplotlib==3.11.2
```

## .gitignore

```text
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.env
.env.*
!.env.example
.streamlit/secrets.toml
*.log
```

## .streamlit/config.toml

```toml
[theme]
primaryColor = "#007F78"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F2F6F7"
textColor = "#142D3D"
font = "sans serif"

[browser]
gatherUsageStats = false

[server]
headless = true
address = "127.0.0.1"
```

## README.md

````markdown
# Supply Chain Delivery Performance Dashboard

An interactive delivery-performance dashboard that derives order-level service KPIs, compares operational segments and exports reproducible analytical evidence from a fixed synthetic order cohort.

> Data boundary: all 1,000 orders and delivery outcomes are synthetic. Results describe the generated scenario, not an observed company.

## Contents

- [Overview](#overview)
- [Dataset and data contract](#dataset-and-data-contract)
- [Architecture and components](#architecture-and-components)
- [Processing pipeline](#processing-pipeline)
- [Configuration and metric definitions](#configuration-and-metric-definitions)
- [Recorded results and evidence](#recorded-results-and-evidence)
- [Interpretation and operational use](#interpretation-and-operational-use)
- [Running locally](#running-locally)
- [Validation and reproducibility](#validation-and-reproducibility)
- [Project structure](#project-structure)
- [Technology stack](#technology-stack)
- [Limitations and next steps](#limitations-and-next-steps)
- [Further technical documentation](#further-technical-documentation)

## Overview

Which product categories, shipping methods and regions have the greatest delivery delays, and where should an operations manager investigate first?

The dashboard compares delivery promises with actual delivery dates, shows the order counts behind each comparison and updates every chart and recommendation when filters change.

## Dataset and data contract

- **Source:** the `generate_orders()` function in [app.py](app.py). No external download, login or paid service is needed.
- **Generated file:** [data/synthetic_orders.csv](data/synthetic_orders.csv), 1,000 rows with 11 columns including derived fields.
- **Reproducibility:** NumPy random generator, seed **42**. Order dates: **1 January to 20 December 2025**. All deliveries are complete in this historical fictional scenario.
- **Why synthetic:** a controlled, complete schema permits reproducible validation of every delivery-date field. It is not evidence that suitable real delivery datasets do not exist.

| Column | Meaning |
|---|---|
| order_id | Unique fictional order ID; one row per order |
| order_date | Order placement date; also used for date filters and monthly cohorts |
| promised_delivery_date | Promised arrival date |
| actual_delivery_date | Recorded arrival date |
| shipping_method | Standard, Express or Economy |
| product_category | Apparel, Electronics, Home goods or Industrial supplies |
| region | North, South, East or West; fictional regions |
| order_value | Positive value in fictional currency units; not used to weight delivery KPIs |
| delay_days | Maximum of actual minus promised calendar days and zero |
| on_time | True for arrival on or before the promise |
| order_month | Order date's month, used for the trend chart |

Generator assumptions are deliberately visible: base lateness probability is 12%, with additions of 13 percentage points for East, 16 for Economy, 7 for Electronics and 10 for October-December orders. These are teaching assumptions, not real-world estimates. Late orders receive 1-6 days of delay; other orders arrive on the promise or one day early. Promised transit is 4/2/7 days for Standard/Express/Economy. Finite random samples need not reproduce the expected ranking for every category.

## Architecture and components

```mermaid
flowchart LR
    N0["Seed-42 order generator"]
    N1["Date and identifier validation"]
    N2["Shared KPI and grouping functions"]
    N3["Streamlit filters and Plotly charts"]
    N4["CSV, JSON and matplotlib exports"]
    N0 --> N1 --> N2 --> N3 --> N4
```

| Component | Entry points or assets | Responsibility |
|---|---|---|
| [app.py](app.py) | generate_orders / prepare_orders | Deterministic cohort generation, date validation and derived delivery fields. |
| [app.py](app.py) | metrics / performance / filter_orders | One authoritative calculation path for KPIs, grouped comparisons and filtered views. |
| [app.py](app.py) | recommendations / export_report | Minimum-sample investigation rules and full-cohort saved reports. |
| [app.py](app.py) | run_dashboard | Streamlit controls, interactive charts, reset behavior and filtered CSV download. |
| [test_dashboard.py](test_dashboard.py) | Automated checks | Hand-counted KPI fixtures, deterministic generation and UI filtering/empty-state checks. |

## Processing pipeline

1. Generate the fixed fictional order cohort and validate unique IDs, complete fields, positive values and delivery-date ordering.
2. Derive one consistent set of on-time and delay columns.
3. Calculate order count, on-time percentage, mean delay and late-order count.
4. Compare region, shipping and category groups, retaining denominators.
5. Plot monthly on-time rates by order-date cohort and apply interactive filters.
6. Suggest three investigation priorities from observed group averages, requiring at least 10 orders per group.
7. Export reproducible data, measured metrics, group summaries and a static figure.

## Configuration and metric definitions

| Control or measure | Definition |
|---|---|
| Cohort | 1,000 completed orders, NumPy generator seed 42 |
| On-time indicator | `actual_delivery_date <= promised_delivery_date` |
| Delay | `max(actual_delivery_date - promised_delivery_date, 0)` in calendar days |
| On-time percentage | `100 * on_time_orders / selected_orders` |
| Mean delay | Sum of nonnegative delays divided by all selected orders, including zero-delay orders |
| Trend cohort | Order month, rather than delivery month |
| Investigation sample floor | At least 10 orders per candidate group |

Region, shipping method, product category and the inclusive order-date range constrain the same underlying view. Empty selections do not produce fabricated percentages. Monetary order values neither weight delivery KPIs nor establish a cost of delay.

## Recorded results and evidence

These numbers were computed from the generated full cohort. Dashboard values change with filters.

| Metric | Actual computed value |
|---|---:|
| Delivered orders | 1,000 |
| On-time orders | 753 |
| Late orders | 247 |
| On-time delivery rate | 75.3% |
| Average delay across all orders | 0.889 days |

**Definitions:** on-time rate = on-time orders / all selected orders. Average delay includes zero-delay early/on-time orders; it is **not** average delay among late orders. Dates use calendar days. Every group is unweighted by order value.

[Application screenshot](outputs/dashboard.png)

![Computed delivery comparisons for the fictional cohort](outputs/delivery_summary.png)

![Computed monthly delivery trend](outputs/monthly_performance.png)

Raw evidence: [metrics](outputs/metrics.json), [regions](outputs/by_region.csv), [shipping methods](outputs/by_shipping_method.csv), [categories](outputs/by_category.csv), [monthly cohorts](outputs/monthly_performance.csv), [recommendations](outputs/recommendations.md).

Verification includes hand-calculated early/on-time/late examples, deterministic generation, invalid data, filter behaviour, empty selections and reset. See [test_dashboard.py](test_dashboard.py). Runtime and browser review details are in [outputs/verification.md](outputs/verification.md).

## Interpretation and operational use

- **East:** 69.9% on time and 1.13 delay days per order across 256 orders. In this scenario, start by reviewing regional exceptions and handoffs; the dashboard does not establish a cause.
- **Economy:** 62.1% on time and 1.34 delay days per order across 264 orders. Investigate dispatch timing and whether the promise matches the service rather than automatically switching every order to Express.
- **Industrial supplies:** the highest sampled category average, 0.92 delay days per order across 237 orders. Review category-specific handling, while noting the small differences between category averages. The generator's Electronics assumption does not guarantee Electronics will rank worst in this finite sample.

These are suggestions for investigating the **fictional scenario**. No actual operational intervention, savings or delivery improvement was measured.

## Running locally

Prerequisite: Python **3.12+** and a terminal; verified using Python 3.12. No cloud account, API key or GPU is required. From the repository root, use these three commands in your Python environment:

```powershell
cd projects/01-delivery-performance-dashboard
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open **http://127.0.0.1:8501**. Stop the server with Ctrl+C. In this prepared workspace the tested interpreter is `../../.venv/Scripts/python.exe`; it can replace `python` in the last two commands. That local environment is ignored by Git and is not required on another laptop.

Optional maintenance, separate from launching: `python app.py --export` regenerates the CSV and full-cohort outputs; `python -m unittest -v` runs the checks. The app itself regenerates the same cohort in memory, so it remains usable even if generated CSVs are missing. The export and UI share the same generator and KPI functions.

## Validation and reproducibility

The automated suite contains **5 tests**. It checks the following implementation boundaries:

Test implementation: [test_dashboard.py](test_dashboard.py).

- Seed and date integrity.
- Kpis include early and exactly on time.
- Missing and duplicate data are rejected.
- Empty filter and small sample.
- App filter empty and reset.

From the project directory, run:

```powershell
python -m unittest -v
```

Recorded execution and any browser-review evidence is retained in [outputs/verification.md](outputs/verification.md). Reported figures correspond to saved execution artifacts; running a report generator can overwrite its generated outputs. Package requirements, source checksums and fixed parameters define the reproducibility boundary; elapsed times and some model/solver outputs can vary across environments.

## Project structure

```text
01-delivery-performance-dashboard/
  app.py
  PROJECT_FILES.md
  README.md
  requirements.txt
  test_dashboard.py
  data/
    Bundled inputs, provenance and prepared data
  outputs/
    Recorded metrics, audit files, tables and figures
```

Generated environments, database files, model artifacts and compiled assets follow the project's [.gitignore](.gitignore). The [copyable source bundle](PROJECT_FILES.md) mirrors the README and contains individual file blocks.

## Technology stack

Python, NumPy, pandas, Streamlit, Plotly, matplotlib and standard-library unittest. Streamlit/Plotly provide interactive charts; matplotlib produces the saved PNG. Direct dependencies are pinned to the versions verified in this workspace. No paid services or external runtime connections.

## Limitations and next steps

- All records and lateness assumptions are invented; results cannot validate real-company performance or business savings.
- Only delivered orders are included. A live operational dashboard would also need pending, overdue and cancelled orders with a clearly defined reporting date.
- Different service promises affect comparisons. Order counts, service mix, seasonality and uncertainty need consideration before action; these charts show associations.
- Monthly rates use order date, not actual delivery date. Partial filtered months may have different sample sizes.
- The MVP has no real carrier integration, persistent database, authentication, statistical significance analysis or deployment service.
- Future improvements: public real delivery data with documented permission, unresolved-order handling and uncertainty estimates.

## Further technical documentation

- [Pinned Python dependencies](requirements.txt)
- [Recorded execution and verification evidence](outputs/verification.md)
- [Folder structure and individually copyable source files](PROJECT_FILES.md)

[Back to contents](#contents)
````
