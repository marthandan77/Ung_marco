# Streamlit Community Cloud Deployment

## Entry Point

Use this file when creating the app:

```text
streamlit_app.py
```

Streamlit Community Cloud runs the app from the repository root, so keep
`requirements.txt`, `.streamlit/config.toml`, and `streamlit_app.py` at the
root.

## Python Version

Choose Python `3.12` in Streamlit Community Cloud Advanced settings before the
first deploy. `hmmlearn` has Python 3.12 wheels; Python 3.14 may require a C++
compiler and is not the recommended cloud runtime.

Community Cloud does not use `runtime.txt` to set Python. If the app is created
with the wrong Python version, delete and redeploy it with Python 3.12 selected.

## Secrets

Add these values in the Streamlit Community Cloud secrets editor. Do not commit
real secrets to GitHub.

```toml
MARKET_DATA_PROVIDER = "auto"
NEWS_PROVIDER = "auto"
YFINANCE_CACHE_DIR = "data/yfinance_cache"
HMM_CACHE_ENABLED = "true"
HMM_CACHE_DIR = "data/hmm_signal_cache"
ETF_PROFILE = "UNG"
ETF_TICKER = ""

ALPACA_API_KEY_ID = "replace_me"
ALPACA_SECRET_KEY = "replace_me"
ALPACA_STOCK_FEED = "iex"
ALPACA_TRADING_BASE_URL = "https://paper-api.alpaca.markets"

EIA_API_KEY = "replace_me"
EIA_STORAGE_SERIES_ID = "NG.NW2_EPG0_SWO_R48_BCF.W"
```

Use `ALPACA_STOCK_FEED = "sip"` only if the account has SIP access.

## Deploy Steps

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, create a new app from the repo.
3. Set the entrypoint to `streamlit_app.py`.
4. Open Advanced settings and select Python `3.12`.
5. Paste the secrets block above with real key values.
6. Deploy.

## GitHub Actions

This repo includes two GitHub-hosted workflows:

- `.github/workflows/streamlit-smoke.yml`: runs on push, pull request, or manual
  dispatch. It installs dependencies with Python 3.12, verifies compiled
  packages like `hmmlearn`, compiles the app, and starts Streamlit long enough
  to check the health endpoint.
- `.github/workflows/nightly-forecast.yml`: runs on a weekday schedule or manual
  dispatch. It runs feed preflight, optional EIA/Alpaca backfills, the daily
  forecast, and uploads CSV/cache artifacts for review.

Add the same provider keys to GitHub repository secrets if you want the nightly
workflow to run real backfills:

```text
ALPACA_API_KEY_ID
ALPACA_SECRET_KEY
ALPACA_STOCK_FEED
ALPACA_TRADING_BASE_URL
EIA_API_KEY
EIA_STORAGE_SERIES_ID
```

`ALPACA_STOCK_FEED`, `ALPACA_TRADING_BASE_URL`, and `EIA_STORAGE_SERIES_ID` have
workflow defaults, but setting them explicitly is clearer.

## Runtime Notes

The app can run preflight checks, daily forecasts, EIA news backfills, and
Alpaca option backfills. Runtime files under `data/` are local to the cloud app
container and are not committed back to GitHub. The nightly GitHub workflow
uploads runtime CSV/cache files as 30-day artifacts. For durable production
state beyond downloadable artifacts, move scorecards, HMM cache rows, option
snapshots, and news rows to Postgres or another persistent store.

## Sources

- Streamlit dependency files: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
- Streamlit file organization: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization
- Streamlit secrets: https://docs.streamlit.io/develop/concepts/connections/secrets-management
- Streamlit Python version settings: https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-python
