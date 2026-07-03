# ETF Forecast Manager

Long-only ETF strategy research engine for a sell-to-buy volatility harvest workflow.
The default profile remains `UNG`.

This repository starts with a daily Forecast Manager. The engine pools real-data signals into a strict weighted matrix, then toggles between long ETF exposure and cash:

- Algo HMM signal: 40%
- ETF call/put option-chain signal: 30%
- ETF news/event signal: 30% when the active profile requires a news feed

The current portfolio defaults are based on the project starting state:

- UNG shares: 30,900
- Average cost: 11.545 USD
- Strategy: long only, no short selling

The long-term product goal is a cloud-ready, GitHub-hosted adaptive Forecast
Manager that can learn from its own Scorecard Manager and generalize to any ETF
profile inserted later. See `ROADMAP.md` for the product architecture.

## Files

- `ung_long_only_strategy.py`: modular strategy engine and CLI runner.
- `streamlit_app.py`: Streamlit Community Cloud dashboard entrypoint.
- `requirements.txt`: Python dependencies.
- `PREMORTEM.md`: failure-mode review before live intraday use.
- `ROADMAP.md`: cloud, auto-learning, and multi-ETF product direction.
- `STREAMLIT_DEPLOYMENT.md`: GitHub and Streamlit Community Cloud deployment steps.
- `.github/workflows/streamlit-smoke.yml`: GitHub Actions build/app smoke test.
- `.github/workflows/nightly-forecast.yml`: scheduled/manual forecast artifact workflow.
- `.env.example`: local/API secret template.

## Run

Use Python 3.12 for the smoothest HMM dependency support. The engine hard-requires `hmmlearn`; it does not fall back to an internal HMM when `hmmlearn` is missing.

```bash
pip install -r requirements.txt
python ung_long_only_strategy.py --start 2018-01-01 --tail 60 --csv ung_execution_ledger.csv --scorecard-csv ung_scorecard.csv --scorecard-summary-csv ung_scorecard_summary.csv
```

Use `--tail 0` to print the full ledger.

Run the Streamlit dashboard locally:

```bash
streamlit run streamlit_app.py
```

For Streamlit Community Cloud, deploy `streamlit_app.py` from the repository
root and select Python 3.12 in Advanced settings. Add secrets through the
Streamlit Cloud secrets editor. See `STREAMLIT_DEPLOYMENT.md`.

For GitHub-hosted runtime checks, add Alpaca/EIA values to repository secrets
and run the `Nightly Forecast Artifacts` workflow. It uploads ledger,
scorecard, and runtime cache artifacts for review.

List built-in profiles:

```bash
python ung_long_only_strategy.py --list-profiles
```

Run the default `UNG` profile explicitly:

```bash
python ung_long_only_strategy.py --profile UNG --start 2018-01-01 --tail 60
```

Prompt the build for missing API keys, feed warnings, and cache gaps:

```bash
python ung_long_only_strategy.py --profile UNG --check-feeds
```

Run a new ETF with the generic profile:

```bash
python ung_long_only_strategy.py --ticker SPY --start 2024-01-01 --tail 20
```

Run the intraday machine by itself:

```bash
python ung_long_only_strategy.py --intraday-only --intraday-interval 5m --intraday-period 5d --intraday-tail 20 --intraday-csv ung_intraday_bars.csv
```

Or attach intraday output to the normal daily run with `--intraday`.

Smoke-test the intraday scorecard command path:

```bash
python ung_long_only_strategy.py --ticker SPY --start 2026-06-26 --end 2026-07-03 --intraday-scorecard --intraday-period 5d --intraday-interval 5m
```

For real intraday scorecard rows, the daily run must include enough history to produce shifted signals. With the default settings that means 500 HMM feature rows, 20 option snapshots for options signals, and real news cache data when the profile requires news. Long HMM backfills require `hmmlearn`; install it before running the daily forecast pipeline.

Backfill the missing option/news caches before a normal forecast run:

```bash
python ung_long_only_strategy.py --profile UNG --start 2024-02-01 --backfill-news --backfill-options --options-backfill-limit 20 --backfill-only
```

Use `--backfill-news-provider eia` to run only the official EIA storage feed or `--backfill-news-provider forexfactory` to run only ForexFactory.

## API Setup

Copy `.env.example` to `.env` and add local credentials there. Do not commit `.env`.

- `ALPACA_API_KEY_ID` and `ALPACA_SECRET_KEY`: preferred market-data credentials for ETF stock bars.
- `ALPACA_TRADING_BASE_URL=https://paper-api.alpaca.markets`: contract metadata endpoint used by the Alpaca historical options backfill.
- `ETF_PROFILE=UNG`: default named profile.
- `ETF_TICKER=`: optional ticker override. When set to a ticker that is not in the registry, the engine uses a generic ETF profile.
- `MARKET_DATA_PROVIDER=auto`: uses Alpaca when credentials are present, otherwise falls back to `yfinance`.
- `ALPACA_STOCK_FEED=iex`: free Alpaca stock feed default. Use `sip` only when the account has the required subscription.
- `INTRADAY_INTERVAL=5m` and `INTRADAY_PERIOD=5d`: default intraday fetch settings for scheduled jobs.
- `YFINANCE_CACHE_DIR=data/yfinance_cache`: keeps fallback provider cache files inside ignored runtime storage.
- `HMM_CACHE_ENABLED=true` and `HMM_CACHE_DIR=data/hmm_signal_cache`: keep rolling HMM signal results in ignored runtime storage so repeated scheduled runs skip previously scored windows. Use `--no-hmm-cache` to force a clean recompute.
- `NEWS_PROVIDER=auto`: fetches ForexFactory's weekly JSON calendar and, when `EIA_API_KEY` is set, official EIA Natural Gas Storage data.
- `EIA_API_KEY`: required for official EIA Natural Gas Storage backfill.
- `EIA_STORAGE_SERIES_ID=NG.NW2_EPG0_SWO_R48_BCF.W`: Lower 48 working gas storage series used by the EIA feed.

The current option-chain snapshot still uses `yfinance` because it includes open-interest and IV fields. Historical options backfill uses Alpaca option bars to populate volume-premium fear-score snapshots; open-interest and IV fields remain blank for backfilled rows because the historical bars endpoint does not provide them.

## Current Modules

1. `ETFProfileRegistry`: selects the default `UNG` profile or creates a generic ETF profile for a new ticker.
2. `MarketDataClient`: fetches ETF OHLCV through Alpaca when credentials are present, with `yfinance` fallback.
3. `IntradayDataMachine`: fetches interval bars through Alpaca/yfinance and labels `PREMARKET`, `RTH`, `AFTER_HOURS`, and `OVERNIGHT` rows.
4. `AlgoSignalCore`: rolling 500-day HMM regime detector using absolute log returns and Parkinson volatility.
5. `UNGOptionsChainSignalCore`: snapshots real ETF calls/puts, calculates put/call premium ratio, open-interest ratio, ATM straddle percentage, and ATM IV skew.
6. `NewsSentimentCore`: loads cached real event sentiment or fetches ForexFactory and official EIA Natural Gas Storage event data when the profile requires it.
7. `ForecastManager`: shifts required trading signals by 1 day and applies active profile weights only when every required signal is present.
8. `ScorecardManager`: compares shifted signals against 1-day, 5-day, and 10-day forward daily outcomes from the signal-day open.
9. `IntradayScorecardManager`: compares shifted daily signals against `PREMARKET`, `RTH`, `AFTER_HOURS`, `OVERNIGHT`, and `OUTSIDE_RTH` intraday outcomes.
10. `SystemStatusManager`: reports active profile, provider/feed, Alpaca credential presence, warm-up counts, cache status, and latest forecast readiness.
11. `LongOnlyExecutionEngine`: toggles between long ETF exposure and cash, with an 8% stop-loss circuit breaker.

## Real Data Discipline

The active forecast does not use mock or neutral placeholder data. If HMM, options, or a profile-required news signal is missing, the Forecast Manager marks the row as `DATA_NOT_READY` and the execution engine holds the current state.

The HMM machine persists date-and-feature-fingerprinted signal rows to `data/hmm_signal_cache/`. Cached rows are reused only when ticker, profile, HMM settings, random seed, cache version, date, and the exact rolling feature-window fingerprint match.

The option-chain machine persists snapshots to `data/options_snapshots/`. It requires 20 real snapshots before emitting an options signal. This avoids inventing option history from a single chain.

The news machine requires real cached event/sentiment data when the active profile enables it. The default UNG profile can use ForexFactory's weekly JSON calendar export and official EIA Natural Gas Storage history. EIA rows are dated to the normal report date, not the inventory week-ending date, to avoid lookahead.

The intraday scorecard only scores dates where daily shifted signals and real intraday bars overlap. A five-day intraday fetch is useful for smoke tests, but it is not enough sample size for model promotion.

## Next Machines

- Auto-Learning Machine: tune thresholds and model weights from scorecard results.
- AutoLearning Profile Promotion: let scorecard-approved weights and thresholds be promoted per ETF profile.
- Telegram Alert Machine: send signal alerts.
- Streamlit Mobile Dashboard: show signal, portfolio, scorecard, and model health.
- IBKR Execution Machine: prebuilt but disabled by default until explicitly enabled.

## Data Notes

The daily prototype can use `yfinance` for fallback bars and current option-chain snapshots. Alpaca is the preferred production market-data path when credentials are present. The intraday machine labels regular and outside-hours sessions so later scoring can separate RTH from extended-hours behavior. For UNG event context, the current free feed is ForexFactory Natural Gas Storage data; later versions should add official EIA cross-checks, weather demand proxies, and broader energy news.

This is research tooling, not financial advice or live execution guidance.
