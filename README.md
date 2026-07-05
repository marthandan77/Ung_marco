# XAU/USD Streamlit Advisor

Streamlit dashboard for manual XAU/USD market analysis. The app reads chart data, checks macro/news context, calculates transparent setup scores, applies strict rejection filters, and displays an advisory status with planned entry, risk level, and target levels.

Main rule: **no setup is better than a weak setup**.

## Features

- Streamlit dashboard with five pages: Live Advisor, Chart Scanner, News/Macro, Parameter Control, and Signal Log.
- No-key market data path using `yfinance` with `XAUUSD=X` and `GC=F` fallback.
- Macro proxies using DXY and US 10Y yield where available.
- Indicators: EMA, VWAP, ATR, RSI, ADX, swing levels, 7-day range, previous-day range, and session ranges.
- Manual parameter tuning with Conservative, Balanced Strict, and Aggressive presets.
- SQLite signal log.
- No broker execution and no automatic parameter tuning.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Decision pipeline

```text
Data quality check
-> news/macro check
-> chart scan
-> score calculation
-> veto filters
-> final advisory output
```

## Notes

The first version uses free/simple data sources so it can run quickly from GitHub and Streamlit. Paid market data and calendar APIs can be added later through Streamlit secrets.
