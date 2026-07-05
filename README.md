# XAU/USD Streamlit Advisor

Streamlit dashboard for manual XAU/USD market analysis. The app reads chart data, checks macro/news context, calculates transparent setup scores, applies strict rejection filters, and displays an advisory status with planned entry, risk level, and target levels.

Main rule: **no setup is better than a weak setup**.

## Features

- Streamlit dashboard with five pages: Live Advisor, Chart Scanner, News/Macro, Parameter Control, and Signal Log.
- Version 1 opens reliably with generated sample OHLC data.
- CSV upload is available for real OHLC data with `open`, `high`, `low`, and `close` columns.
- Indicators: EMA, VWAP, ATR, RSI, ADX, swing levels, 7-day range, and support/resistance mapping.
- Manual parameter tuning with Conservative, Balanced Strict, and Aggressive presets.
- Strict rejection filters for weak setups.
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

## Next data step

The repository includes `yfinance` in `requirements.txt`, but the current root app uses sample/CSV data first for reliability. The next Codex task should add live `XAUUSD=X`/`GC=F` provider loading behind a toggle, then keep CSV as fallback.
