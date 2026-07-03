# UNG ETF Manager Pre-Mortem

This pre-mortem lists the most likely ways the build can fail before it becomes a reliable intraday sell-to-buy manager.

## 1. False Readiness

Risk: The system emits a composite score while one of the machines is missing real data.

Mitigation now: The Forecast Manager requires all three shifted real signals. Missing HMM, options, or news data produces `DATA_NOT_READY`, not a synthetic score.

Next: Add a Streamlit model-health panel with per-machine status, timestamp, and stale-data warnings.

## 2. Options History Cold Start

Risk: A single current option chain is treated like a historical options model.

Mitigation now: UNG option chains are persisted as real snapshots and the options module needs 20 snapshots before it emits a signal.

Next: Use Alpaca options or another historical options API to backfill UNG option-chain history.

## 3. HMM Overfit Or Regime Instability

Risk: The rolling HMM discovers unstable states that look clean in-sample but fail out-of-sample.

Mitigation now: The model fits only on the rolling 500-day window, its output is shifted by one day before execution, and the Scorecard Manager scores shifted signals against 1-day, 5-day, and 10-day forward daily outcomes.

Next: Score state persistence and transition stability inside the Scorecard Manager.

## 4. Daily Engine Used For Intraday Harvest

Risk: Daily bars cannot capture RTH/outside-RTH volatility harvest conditions.

Mitigation now: The daily engine and daily scorecard are clearly scoped as the first Forecast Manager, not the final intraday trader.

Next: Add an Intraday Data Machine with 1-minute or 5-minute bars, RTH/outside-RTH session flags, liquidity filters, and same-session scorecard horizons.

## 5. News And Event Sentiment Gaps

Risk: News/event sentiment is unavailable, unreleased, or stale, causing the Forecast Manager to block signals.

Mitigation now: No mock sentiment is used. The news module requires cached real sentiment/event data. ForexFactory Natural Gas Storage events are ignored until actual and forecast values are both available.

Next: Add a timestamp-aware news freshness rule, official EIA cross-checks, and NOAA weather demand proxies.

## 6. Stop-Loss Execution Assumption

Risk: A daily stop-loss assumes execution near the stop price even when gaps or after-hours liquidity make that impossible.

Mitigation now: The engine uses the worse of open price or stop price when the daily low breaches the stop.

Next: Intraday engine should model stop execution with interval bars and liquidity checks.

## 7. GitHub And Secret Hygiene

Risk: API keys or broker credentials are accidentally committed.

Mitigation now: `.env` and `.streamlit/secrets.toml` are ignored.

Next: Add `.env.example`, Streamlit secrets documentation, and a pre-commit secret scan.

## 8. Future IBKR Automation Risk

Risk: A future live trading module places orders from an unvalidated signal.

Mitigation now: IBKR execution is not implemented or enabled.

Next: Build IBKR as a disabled module with dry-run prompts, order preview, position reconciliation, and an explicit enable flag.
