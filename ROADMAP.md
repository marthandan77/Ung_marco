# UNG ETF Manager Roadmap

This project is intended to move from local research tooling to a cloud-ready,
GitHub-hosted adaptive Forecast Manager.

## Product Direction

- Build locally, then push the repository to GitHub.
- Keep the code cloud-ready: no local-only secrets, no hard-coded paths, no
  committed runtime data, and all provider credentials loaded from environment
  variables.
- Make the Forecast Manager dynamic: model weights and thresholds should be
  tuned from Scorecard Manager results instead of staying permanently fixed.
- Keep every prediction auditable: no hidden mock data, no synthetic readiness,
  and no unscored signal changes.
- Generalize beyond UNG so a new ETF ticker can be inserted without rewriting
  the strategy engine.

## Target Architecture

1. `ConfigManager`
   - Loads ticker, position defaults, provider choices, API credentials, warm-up
     windows, scorecard horizons, and cloud/runtime settings.
   - Supports per-ETF overrides.

2. `MarketDataRouter`
   - Chooses Alpaca, yfinance fallback, and future provider adapters by
     capability and availability.
   - Emits provider health, stale-data warnings, and fallback status.

3. `ForecastManager`
   - Combines real signals only after each required machine is ready.
   - Starts with explicit baseline weights, then accepts learned weights after
     scorecard validation.

4. `ScorecardManager`
   - Scores each signal and composite forecast against forward outcomes.
   - Produces per-signal, per-horizon hit rate, directional return, drawdown,
     and sample sufficiency.

5. `AutoLearningManager`
   - Learns weights, thresholds, and signal confidence from scorecard history.
   - Uses walk-forward validation and minimum-sample gates before promoting any
     learned configuration.
   - Keeps rollback metadata for every promoted model configuration.

6. `ETFProfileRegistry`
   - Stores ticker-specific settings: underlying asset context, option liquidity
     assumptions, volatility proxy, event/news keywords, warm-up rules, and
     portfolio defaults.

7. `CloudRuntime`
   - Runs scheduled data refresh, forecast generation, scorecard updates, and
     alerts from environment-configured cloud jobs.
   - Writes portable artifacts such as CSV/JSON/SQLite/Postgres records instead
     of local-only state.

## Current Build Status

- Daily Forecast Manager: built.
- Daily Scorecard Manager: built.
- Alpaca stock-bars adapter: built and verified with local `.env` credentials.
- Intraday Data Machine with RTH/outside-hours labels: built.
- Intraday Scorecard Extension with RTH/outside-hours outcomes: built.
- Readiness/status reporting: built.
- Persistent HMM signal cache with feature-window fingerprints: built.
- Multi-ETF profile registry: built, with `UNG` default and generic fallback profiles.
- yfinance daily/intraday/options fallback: built and reachable.
- ForexFactory Natural Gas Storage event adapter: built and reachable.
- EIA Natural Gas Storage backfill adapter: built, requires `EIA_API_KEY`.
- Alpaca historical option-bars backfill adapter: built, requires Alpaca option-data access.
- Streamlit Community Cloud dashboard entrypoint: built.
- GitHub Actions Streamlit smoke workflow: built.
- GitHub Actions scheduled forecast/backfill artifact workflow: built.
- AutoLearningManager: not built yet.
- Durable database storage/runtime packaging: not built yet.

## Next Build Priorities

1. Add durable database storage for Streamlit/GitHub runtime state.
2. Benchmark and tune first-run rolling HMM backfills before large cloud jobs.
3. Build AutoLearningManager with strict scorecard promotion gates.
4. Add profile-level learned weight/threshold promotion and rollback metadata.
5. Add weather/news cross-checks for the UNG profile.
