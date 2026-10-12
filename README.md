# MarketLens

**See the market. Understand the risk.** An independent market trends and risk analytics workspace by Manoj Kumar Reddy.

Python + Pandas + NumPy + SQLite on the backend; responsive HTML/CSS and dependency-free SVG charts on the frontend. Designed to demonstrate data engineering, SQL, statistical reasoning, and product thinking without inventing an AI predictor.

## Run locally

Requires Python 3.11+.

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Open http://127.0.0.1:8790. The first run downloads a public Apple historical example dataset. If unavailable, import a daily CSV or fetch a public crypto dataset from the app. There is no fabricated fallback data. Imported datasets are held in memory and written to the local SQLite database; the UI catalog resets on restart, so reimport custom CSVs after restarting. Runtime data is ignored by Git.

## Features

- Historical stock study: real Apple daily OHLCV sample (2015–2017), explicitly labelled historical.
- Data cleaning: invalid dates, nonfinite/negative prices, impossible OHLC ranges, negative volume, and duplicate dates reported. Last valid duplicate wins; no missing-value interpolation.
- Returns, trailing 20-observation annualized sample volatility, volume changes, volume anomalies, drawdown, historical 95% loss threshold and tail mean loss.
- **Replay through a date**: calculations use observations on or before the cutoff. Tests ensure future price changes cannot alter an earlier result.
- **Evidence receipts**: input counts, gap warnings, source, method version and SHA-256 of the selected clean window. Export JSON and a Markdown brief with five calculated observations.
- **Risk laboratory**: hypothetical exposure and shock controls, separate from historical risk statistics.
- **SQL explorer**: actual SQLite LAG queries with visible query and result table. No arbitrary SQL endpoint.
- **Live demonstration**: optional 30-second polling of Coinbase BTC/ETH public quotes; separate refresh of completed daily candles. Quotes are polled, not streamed; daily analysis never uses today's incomplete candle.
- CSV import stays local. Provider errors leave the previous analysis dataset intact and show a visible error.
- Accessible labels, responsive layouts, keyboard focus, reduced-motion support, no frontend framework or chart CDN dependency. Optional Google fonts fall back to local sans-serif.

## Data and methods

Historical example: https://github.com/plotly/datasets/blob/master/finance-charts-apple.csv (downloaded at runtime; data not redistributed in this repository).

Public crypto API: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles and https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-ticker. Access is subject to the provider's terms and regional availability.

`return[t] = close[t] / close[t-1] - 1`. Volatility is the trailing 20-return sample standard deviation times sqrt(252) for equity or sqrt(365) for crypto. Drawdown is close divided by the running maximum within the selected window, minus one. Volume ratio uses the *previous* 20 observations. Historical VaR is max(0, minus the 5th percentile of returns); tail mean uses observations at or below that quantile. Pandas default linear quantile interpolation is used. All percentages are displayed in percentage points.

Price returns are not dividend-inclusive total returns. Apple sample OHLC values use raw close, not the supplied adjusted-close column; corporate actions may distort results. One instrument per import. Daily-only data. Volume units depend on asset class. Date-gap checks (>4 calendar days equity, >1 crypto) are heuristics, not exchange-calendar validation. Missing sessions can turn a close-to-close observation into a multi-day return. No silent claims of prediction, causality, or data accuracy. A high retained-row percentage is **not** a confidence score.

This project is not an S&P 500 universe tracker. It starts with one reproducible stock dataset and allows users to import additional instruments. Free equity market data is not represented as live exchange data. No Nasdaq affiliation, brokerage connectivity, trade execution, or investment recommendations.

## Architecture

```text
CSV / public provider → schema + OHLC validation → clean Pandas frame
                             ↓                       ↓
                      SQLite warehouse       causal analytics
                             ↓                       ↓
                       SQL LAG query       JSON + evidence receipt
                             └──────── dashboard ─────┘
```

`engine.py`: deterministic analytics and SQL persistence. `server.py`: loopback-only HTTP API and provider adapters. `web/`: UI. `sql/analysis.sql`: auditable query. `tests/`: numerical and temporal tests.

## Verification

```sh
python -m unittest discover -s tests -v
node --check web/app.js
```

GitHub Actions runs these checks. Tests cover cleaning, return/drawdown arithmetic, no future-data leakage, volume baseline exclusion, zero-volume handling, SQL/Pandas agreement, input rejection, and asset-specific annualization.

## Deployment boundary

This is a **local single-user application**, not an authenticated multi-user SaaS. It binds only to localhost; do not expose this development HTTP server directly to the internet. A public repository publishes source code, not the running backend. Production hosting needs authentication, request limits, a production application server and per-user dataset isolation. The public quote provider requires no API key; do not add secrets to source control.

## Inspiration and originality

Inspired by the market analytics learning brief and the data-warehouse focus of https://github.com/Marwan-xDiab/S-P-500-Stock-Market-Analysis. This implementation is original; no source or dashboard assets were copied. Its emphasis is reproducible evidence, data-quality visibility and historical replay. No claim is made that these techniques are unprecedented.

Code is MIT licensed; external datasets and APIs retain their own terms.
