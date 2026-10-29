# Verification record

- Environment: Windows, Python 3.12; direct dependencies pinned in requirements.txt.
- Full synthetic export executed successfully: 1,000 orders, 247 late, 75.3% on time, 0.889 mean delay days across all orders.
- Five standard-library unittest checks passed, including Streamlit AppTest interactions. The suite reported 1.349 seconds in the final functional run before a layout-only adjustment.
- Hand-calculated fixture covers an early arrival, an exactly-on-time arrival and a two-day-late arrival: expected on-time rate 2/3 and mean positive delay 2/3 days.
- Data integrity checks cover deterministic generation, unique IDs, missing columns, duplicate rows, complete fields and dates after placement.
- AppTest checks cover East selection, empty selections and reset. Empty data displays a message instead of a division error.
- Local HTTP health endpoint returned `ok`. Browser review used localhost port 8502 because the restricted execution sandbox could not open sockets. The documented default port remains 8501.
- Browser confirmed the full-cohort KPIs, then East-only results of 256 orders, 69.9% on time and 1.13 delay days/order. Reset restored 1,000 orders and 75.3%.
- Browser screenshot saved as dashboard.png. The figure exports were visually checked for readable labels. The screenshot shows the viewport; scroll the live dashboard to see the trend and recommendations.
- No hosted deployment, public publishing or real-company data was used. The review server was temporary; launch it with the README commands when needed.

These checks validate this small demonstration, not enterprise readiness, causal conclusions or real-world delivery performance.
