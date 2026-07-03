"""Streamlit dashboard for the ETF Forecast Manager."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ung_long_only_strategy import (
    ETFProfileRegistry,
    ETFStrategyPipeline,
    StrategyConfig,
    SystemStatusManager,
    _alpaca_credentials,
    _env_bool,
    _eia_api_key,
    build_feed_preflight_report,
    load_env_file,
)


st.set_page_config(
    page_title="ETF Forecast Manager",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)


def apply_streamlit_secrets() -> None:
    try:
        secrets = st.secrets
    except Exception:
        return

    try:
        secret_items = list(secrets.items())
    except Exception:
        return

    for key, value in secret_items:
        if isinstance(value, (str, int, float, bool)):
            os.environ[str(key)] = str(value)


def build_config(profile_name: str, ticker: str | None) -> StrategyConfig:
    profile = None if ticker else profile_name
    config = ETFProfileRegistry.build_config(profile_name=profile, ticker=ticker)
    return replace(
        config,
        alpaca_trading_base_url=(
            os.getenv("ALPACA_TRADING_BASE_URL", "").strip()
            or config.alpaca_trading_base_url
        ),
        eia_storage_series_id=(
            os.getenv("EIA_STORAGE_SERIES_ID", "").strip()
            or config.eia_storage_series_id
        ),
        hmm_cache_dir=(
            os.getenv("HMM_CACHE_DIR", "").strip() or config.hmm_cache_dir
        ),
        hmm_cache_enabled=_env_bool("HMM_CACHE_ENABLED", config.hmm_cache_enabled),
    )


@st.cache_data(ttl=600, show_spinner=False)
def run_daily_pipeline(
    profile_name: str,
    ticker: str | None,
    start: str,
    end: str,
) -> dict[str, Any]:
    config = build_config(profile_name, ticker)
    pipeline = ETFStrategyPipeline(config)
    ledger = pipeline.run(start=start, end=end)
    return {
        "ledger": ledger,
        "forecast": ledger.attrs.get("forecast", pd.DataFrame()),
        "daily_data": ledger.attrs.get("daily_data", pd.DataFrame()),
        "readiness_report": ledger.attrs.get("readiness_report", []),
        "scorecard": ledger.attrs.get("scorecard", pd.DataFrame()),
        "scorecard_summary": ledger.attrs.get("scorecard_summary", pd.DataFrame()),
        "scorecard_report": ledger.attrs.get("scorecard_report", []),
    }


def run_news_backfill(config: StrategyConfig, start: str, end: str) -> pd.DataFrame:
    pipeline = ETFStrategyPipeline(config)
    return pipeline.news_core.fetch_eia_storage_and_cache(start=start, end=end)


def run_options_backfill(
    config: StrategyConfig,
    start: str,
    end: str,
    limit: int,
) -> pd.DataFrame:
    pipeline = ETFStrategyPipeline(config)
    data = pipeline.data_client.fetch(start=start, end=end)
    return pipeline.options_core.backfill_alpaca_history(
        data=data,
        start=start,
        end=end,
        max_dates=limit,
    )


def status_value(value: bool) -> str:
    return "SET" if value else "MISSING"


def render_preflight(config: StrategyConfig) -> None:
    report = build_feed_preflight_report(config)
    for line in report:
        st.write(f"- {line}")


def render_metric_grid(config: StrategyConfig) -> None:
    status = SystemStatusManager(config)
    options = status.options_cache_status()
    news = status.news_cache_status()
    alpaca_key_id, alpaca_secret_key = _alpaca_credentials()

    columns = st.columns(5)
    columns[0].metric("Alpaca", status_value(bool(alpaca_key_id and alpaca_secret_key)))
    columns[1].metric("EIA", status_value(bool(_eia_api_key())))
    columns[2].metric(
        "Options",
        f"{options['rows']}/{config.options_warmup_snapshots}",
        options["latest_date"],
    )
    columns[3].metric("News Rows", str(news["rows"]), news["latest_date"])
    columns[4].metric("HMM Cache", str(status.hmm_cache_status()["rows"]))


def show_dataframe(frame: pd.DataFrame, rows: int = 60) -> None:
    if frame.empty:
        st.info("No rows available.")
        return
    display = frame.tail(rows) if rows > 0 else frame
    st.dataframe(display, use_container_width=True, height=420)


load_env_file()
apply_streamlit_secrets()

profile_options = [line.split(":", 1)[0] for line in ETFProfileRegistry.describe_profiles()]
with st.sidebar:
    st.header("Run")
    profile_name = st.selectbox("Profile", profile_options, index=0)
    ticker_override = st.text_input("Ticker override", value="").strip().upper()
    today = date.today()
    start_date = st.date_input("Start", value=today - timedelta(days=365 * 3))
    end_date = st.date_input("End", value=today)
    tail_rows = st.number_input("Rows", min_value=10, max_value=500, value=60, step=10)
    options_limit = st.number_input(
        "Option backfill dates",
        min_value=1,
        max_value=80,
        value=20,
        step=1,
    )
    run_forecast = st.button("Run Forecast", type="primary", use_container_width=True)
    run_eia = st.button("Backfill EIA News", use_container_width=True)
    run_options = st.button("Backfill Options", use_container_width=True)

ticker_value = ticker_override or None
config = build_config(profile_name, ticker_value)

st.title("ETF Forecast Manager")
render_metric_grid(config)

tabs = st.tabs(["Status", "Forecast", "Scorecard", "Backfill"])

with tabs[0]:
    st.subheader("Preflight")
    render_preflight(config)

with tabs[1]:
    if run_forecast:
        with st.spinner("Running forecast pipeline"):
            try:
                st.session_state["forecast_result"] = run_daily_pipeline(
                    profile_name=profile_name,
                    ticker=ticker_value,
                    start=start_date.isoformat(),
                    end=end_date.isoformat(),
                )
            except Exception as exc:
                st.error(f"Forecast failed: {exc}")
            else:
                result = st.session_state["forecast_result"]
                for line in result["readiness_report"]:
                    st.write(f"- {line}")
                show_dataframe(result["ledger"], int(tail_rows))
    elif "forecast_result" in st.session_state:
        result = st.session_state["forecast_result"]
        for line in result["readiness_report"]:
            st.write(f"- {line}")
        show_dataframe(result["ledger"], int(tail_rows))
    else:
        st.info("Forecast has not been run in this session.")

with tabs[2]:
    if "forecast_result" in st.session_state:
        result = st.session_state["forecast_result"]
        for line in result["scorecard_report"]:
            st.write(f"- {line}")
        st.subheader("Summary")
        show_dataframe(result["scorecard_summary"], rows=200)
        st.subheader("Rows")
        show_dataframe(result["scorecard"], rows=int(tail_rows))
    else:
        st.info("Run a forecast to populate scorecard views.")

with tabs[3]:
    if run_eia:
        with st.spinner("Backfilling EIA Natural Gas Storage"):
            try:
                rows = run_news_backfill(
                    config,
                    start=start_date.isoformat(),
                    end=end_date.isoformat(),
                )
            except Exception as exc:
                st.error(f"EIA backfill failed: {exc}")
            else:
                st.success(f"EIA rows cached: {len(rows)}")
                show_dataframe(rows, rows=200)

    if run_options:
        with st.spinner("Backfilling Alpaca option bars"):
            try:
                rows = run_options_backfill(
                    config,
                    start=start_date.isoformat(),
                    end=end_date.isoformat(),
                    limit=int(options_limit),
                )
            except Exception as exc:
                st.error(f"Options backfill failed: {exc}")
            else:
                st.success(f"Option dates processed: {len(rows)}")
                show_dataframe(rows, rows=200)

    if not run_eia and not run_options:
        st.info("No backfill job has been run in this session.")
