# Project Status

The repository has been converted into the XAU/USD Streamlit Advisor project on branch `codex/xauusd-streamlit-advisor`.

## Implemented

- Root `app.py` Streamlit dashboard.
- Manual parameter sidebar.
- Conservative, Balanced Strict, and Aggressive presets.
- Chart scanner with EMA, VWAP, ATR, RSI, ADX.
- Market map with 7-day range, support/resistance, swing levels, and middle-range filter.
- BUY/SELL/WAIT/HOLD scoring.
- Strict veto engine.
- Manual news block.
- Legacy `streamlit_app.py` wrapper pointing to `app.py`.
- GitHub workflow smoke checks.

## Current data path

- Version 1 uses sample data by default so the app opens reliably.
- CSV upload is available for real OHLC data.
- yfinance dependency is present for the next provider step.

## Next recommended step

Add live provider integration in `app.py` or a small `src/live_data.py` module, then deploy to Streamlit Cloud with `app.py` as the entrypoint.
