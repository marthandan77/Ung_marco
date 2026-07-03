"""Hosted ETF Forecast Manager runtime.

This compact runtime keeps the Streamlit/GitHub deployment runnable while the
larger local research engine remains the development source of truth.
"""

from __future__ import annotations

import argparse
import math
import os
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DATA_DIR = Path("data")


@dataclass(frozen=True)
class ETFProfile:
    profile_name: str
    ticker: str
    profile_label: str
    asset_context: str
    initial_shares: float = 0.0
    initial_avg_cost: float = 0.0
    initial_cash: float = 0.0
    news_provider: str = "none"
    news_cache_path: str = ""
    require_news_signal: bool = False

    def to_config(self) -> "StrategyConfig":
        ticker = self.ticker.strip().upper()
        return StrategyConfig(
            profile_name=self.profile_name.strip().upper(),
            profile_label=self.profile_label,
            asset_context=self.asset_context,
            ticker=ticker,
            initial_shares=self.initial_shares,
            initial_avg_cost=self.initial_avg_cost,
            initial_cash=self.initial_cash,
            news_provider=self.news_provider,
            news_cache_path=self.news_cache_path or f"data/news_sentiment/{ticker.lower()}_news_sentiment.csv",
            require_news_signal=self.require_news_signal,
        )


@dataclass(frozen=True)
class StrategyConfig:
    profile_name: str = "UNG"
    profile_label: str = "United States Natural Gas Fund"
    asset_context: str = "natural gas"
    ticker: str = "UNG"
    hmm_window: int = 500
    hmm_states: int = 3
    hmm_cache_dir: str = "data/hmm_signal_cache"
    hmm_cache_enabled: bool = True
    buy_threshold: float = 0.50
    sell_threshold: float = -0.20
    stop_loss_pct: float = 0.08
    random_seed: int = 42
    initial_shares: float = 30_900.0
    initial_avg_cost: float = 11.545
    initial_cash: float = 0.0
    market_data_provider: str = "auto"
    alpaca_base_url: str = "https://data.alpaca.markets"
    alpaca_trading_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_stock_feed: str = "iex"
    intraday_interval: str = "5m"
    intraday_period: str = "5d"
    options_snapshot_dir: str = "data/options_snapshots"
    options_warmup_snapshots: int = 20
    news_cache_path: str = "data/news_sentiment.csv"
    news_provider: str = "forexfactory"
    eia_api_base_url: str = "https://api.eia.gov"
    eia_storage_series_id: str = "NG.NW2_EPG0_SWO_R48_BCF.W"
    require_news_signal: bool = True
    scorecard_horizons: tuple[int, ...] = (1, 5, 10)
    scorecard_neutral_band: float = 0.05

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", self.ticker.strip().upper())
        object.__setattr__(self, "profile_name", self.profile_name.strip().upper())

    def price_column(self, field: str) -> str:
        return f"{self.ticker}_{field}"

    @property
    def open_column(self) -> str:
        return self.price_column("Open")

    @property
    def high_column(self) -> str:
        return self.price_column("High")

    @property
    def low_column(self) -> str:
        return self.price_column("Low")

    @property
    def close_column(self) -> str:
        return self.price_column("Close")

    @property
    def volume_column(self) -> str:
        return self.price_column("Volume")

    @property
    def hmm_cache_path(self) -> Path:
        return Path(self.hmm_cache_dir) / f"{self.ticker.lower()}_algo_signal_cache.csv"

    @property
    def options_snapshot_path(self) -> Path:
        return Path(self.options_snapshot_dir) / f"{self.ticker.lower()}_options_snapshots.csv"

    def price_column_map(self) -> dict[str, str]:
        return {
            "Open": self.open_column,
            "High": self.high_column,
            "Low": self.low_column,
            "Close": self.close_column,
            "Volume": self.volume_column,
        }

    def required_price_columns(self) -> list[str]:
        return [self.open_column, self.high_column, self.low_column, self.close_column]


class ETFProfileRegistry:
    DEFAULT_PROFILE = "UNG"
    BUILTIN_PROFILES: dict[str, ETFProfile] = {
        "UNG": ETFProfile(
            profile_name="UNG",
            ticker="UNG",
            profile_label="United States Natural Gas Fund",
            asset_context="natural gas",
            initial_shares=30_900.0,
            initial_avg_cost=11.545,
            initial_cash=0.0,
            news_provider="forexfactory",
            news_cache_path="data/news_sentiment.csv",
            require_news_signal=True,
        ),
    }

    @classmethod
    def resolve(cls, profile_name: str | None = None, ticker: str | None = None) -> ETFProfile:
        ticker_value = (ticker or "").strip().upper()
        if ticker_value:
            return cls.BUILTIN_PROFILES.get(ticker_value, cls.generic_profile(ticker_value))
        profile_value = (profile_name or cls.DEFAULT_PROFILE).strip().upper()
        return cls.BUILTIN_PROFILES.get(profile_value, cls.generic_profile(profile_value))

    @classmethod
    def build_config(cls, profile_name: str | None = None, ticker: str | None = None) -> StrategyConfig:
        return cls.resolve(profile_name=profile_name, ticker=ticker).to_config()

    @classmethod
    def generic_profile(cls, ticker: str) -> ETFProfile:
        normalized = (ticker or cls.DEFAULT_PROFILE).strip().upper()
        return ETFProfile(
            profile_name="GENERIC",
            ticker=normalized,
            profile_label=f"{normalized} ETF",
            asset_context="generic ETF",
            news_provider="none",
            news_cache_path=f"data/news_sentiment/{normalized.lower()}_news_sentiment.csv",
            require_news_signal=False,
        )

    @classmethod
    def describe_profiles(cls) -> list[str]:
        return [f"{name}: {profile.ticker} - {profile.profile_label}" for name, profile in sorted(cls.BUILTIN_PROFILES.items())]


@dataclass(frozen=True)
class ForecastWeights:
    algo: float = 0.40
    options: float = 0.30
    news: float = 0.30

    def validate(self) -> None:
        total = self.algo + self.options + self.news
        if not math.isclose(total, 1.0, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError(f"Forecast weights must sum to 1.0, got {total:.6f}")


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _env_first(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _alpaca_credentials() -> tuple[str, str]:
    return _env_first("ALPACA_API_KEY_ID", "APCA_API_KEY_ID"), _env_first("ALPACA_SECRET_KEY", "APCA_API_SECRET_KEY")


def _eia_api_key() -> str:
    return _env_first("EIA_API_KEY")


def _safe_float(value: object, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _normalise_yfinance_frame(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if frame.empty:
        raise ValueError(f"No market data returned for {ticker}")
    if isinstance(frame.columns, pd.MultiIndex):
        if ticker in frame.columns.get_level_values(-1):
            frame = frame.xs(ticker, axis=1, level=-1)
        elif ticker in frame.columns.get_level_values(0):
            frame = frame.xs(ticker, axis=1, level=0)
        else:
            frame.columns = frame.columns.get_level_values(0)
    frame = frame.copy()
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    return frame.sort_index()


class MarketDataClient:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    def fetch(self, start: str, end: str | None = None) -> pd.DataFrame:
        provider = os.getenv("MARKET_DATA_PROVIDER", "").strip().lower() or self.config.market_data_provider
        key_id, secret_key = _alpaca_credentials()
        if provider in {"auto", "alpaca"} and key_id and secret_key:
            try:
                return self.fetch_alpaca(start, end, key_id, secret_key)
            except Exception:
                if provider == "alpaca":
                    raise
        return self.fetch_yfinance(start, end)

    def fetch_yfinance(self, start: str, end: str | None = None) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("Install yfinance to fetch market data: pip install yfinance") from exc
        raw = yf.download(self.config.ticker, start=start, end=end, auto_adjust=False, progress=False, threads=False)
        bars = _normalise_yfinance_frame(raw, self.config.ticker)
        required = ["Open", "High", "Low", "Close", "Volume"]
        missing = [column for column in required if column not in bars.columns]
        if missing:
            raise ValueError(f"{self.config.ticker} data missing required columns: {missing}")
        data = bars[required].rename(columns=self.config.price_column_map())
        data.attrs.update({"market_data_provider": "yfinance", "market_data_feed": "yfinance", "ticker": self.config.ticker})
        return data.dropna(subset=self.config.required_price_columns())

    def fetch_alpaca(self, start: str, end: str | None, key_id: str, secret_key: str) -> pd.DataFrame:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("Install requests for Alpaca data: pip install requests") from exc
        url = f"{self.config.alpaca_base_url.rstrip('/')}/v2/stocks/bars"
        headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret_key}
        params: dict[str, object] = {
            "symbols": self.config.ticker,
            "timeframe": "1Day",
            "start": start,
            "limit": 10000,
            "adjustment": "raw",
            "feed": os.getenv("ALPACA_STOCK_FEED", "").strip() or self.config.alpaca_stock_feed,
            "sort": "asc",
        }
        if end:
            params["end"] = end
        rows: list[dict[str, object]] = []
        while True:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            rows.extend(payload.get("bars", {}).get(self.config.ticker, []))
            token = payload.get("next_page_token") or ""
            if not token:
                break
            params["page_token"] = token
        if not rows:
            raise ValueError(f"No Alpaca bars returned for {self.config.ticker}")
        frame = pd.DataFrame(rows)
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame["t"], utc=True)).tz_convert(None)
        frame = frame.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
        data = frame[["Open", "High", "Low", "Close", "Volume"]].rename(columns=self.config.price_column_map()).sort_index()
        data.attrs.update({"market_data_provider": "alpaca", "market_data_feed": params["feed"], "ticker": self.config.ticker})
        return data.dropna(subset=self.config.required_price_columns())


class AlgoSignalCore:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    @staticmethod
    def require_hmmlearn() -> None:
        try:
            import hmmlearn.hmm  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("hmmlearn is required. Install with `pip install -r requirements.txt` and use Python 3.12 on hosted Streamlit.") from exc

    def generate(self, data: pd.DataFrame) -> pd.Series:
        self.require_hmmlearn()
        from hmmlearn.hmm import GaussianHMM

        signal = pd.Series(np.nan, index=data.index, name="Algo_Signal", dtype="float64")
        close = data[self.config.close_column].astype(float)
        high = data[self.config.high_column].astype(float)
        low = data[self.config.low_column].astype(float)
        features = pd.DataFrame(
            {
                "Abs_Log_Return": np.log(close).diff().abs(),
                "Parkinson_Vol": np.sqrt((np.log(high / low).replace([np.inf, -np.inf], np.nan) ** 2) / (4.0 * np.log(2.0))),
            },
            index=data.index,
        ).dropna()
        if len(features) < self.config.hmm_window:
            return signal
        window = features.tail(self.config.hmm_window)
        values = window.to_numpy(dtype=float)
        std = values.std(axis=0)
        std[std == 0.0] = 1.0
        scaled = (values - values.mean(axis=0)) / std
        model = GaussianHMM(n_components=self.config.hmm_states, covariance_type="full", n_iter=200, min_covar=1e-6, random_state=self.config.random_seed)
        model.fit(scaled)
        states = model.predict(scaled)
        state_table = window.copy()
        state_table["State"] = states
        risk = state_table.groupby("State")[["Abs_Log_Return", "Parkinson_Vol"]].mean().mean(axis=1)
        ordered = list(risk.sort_values().index)
        state_to_signal = {ordered[0]: -1, ordered[min(1, len(ordered) - 1)]: 0, ordered[-1]: 1}
        signal.loc[window.index[-1]] = float(state_to_signal.get(states[-1], 0))
        return signal


class UNGOptionsChainSignalCore:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.snapshot_path = config.options_snapshot_path

    def load_history(self) -> pd.DataFrame:
        if not self.snapshot_path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(self.snapshot_path)
        except Exception:
            return pd.DataFrame()

    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        frame = pd.DataFrame(index=data.index)
        frame["Options_Signal"] = np.nan
        frame["Options_Status"] = "CACHE_NOT_READY"
        frame["Options_Snapshot_Count"] = 0
        frame["Options_Source"] = "cache"
        history = self.load_history()
        if history.empty or "Snapshot_Date" not in history:
            return frame
        history = history.copy()
        history["Snapshot_Date"] = pd.to_datetime(history["Snapshot_Date"], errors="coerce").dt.normalize()
        count = len(history.dropna(subset=["Snapshot_Date"]))
        if count < self.config.options_warmup_snapshots:
            frame["Options_Snapshot_Count"] = count
            return frame
        metric = pd.to_numeric(history.get("Put_Call_Premium_Ratio", pd.Series(dtype=float)), errors="coerce")
        z = (metric - metric.rolling(self.config.options_warmup_snapshots).mean()) / metric.rolling(self.config.options_warmup_snapshots).std(ddof=0).replace(0, np.nan)
        history["Options_Signal"] = np.where(z >= 1.0, 1.0, np.where(z <= -1.0, -1.0, 0.0))
        latest = history.dropna(subset=["Snapshot_Date"]).drop_duplicates("Snapshot_Date", keep="last").set_index("Snapshot_Date")
        aligned = latest.reindex(frame.index.normalize())
        frame["Options_Signal"] = aligned["Options_Signal"].to_numpy() if "Options_Signal" in aligned else np.nan
        frame["Options_Status"] = np.where(np.isfinite(frame["Options_Signal"]), "READY", "CACHE_NOT_READY")
        frame["Options_Snapshot_Count"] = count
        return frame

    def backfill_alpaca_history(self, data: pd.DataFrame, start: str | None = None, end: str | None = None, max_dates: int = 20) -> pd.DataFrame:
        key_id, secret_key = _alpaca_credentials()
        if not key_id or not secret_key:
            raise RuntimeError("Set ALPACA_API_KEY_ID and ALPACA_SECRET_KEY for Alpaca option backfill")
        rows: list[dict[str, Any]] = []
        candidates = data.sort_index()
        if start:
            candidates = candidates.loc[pd.Timestamp(start) :]
        if end:
            candidates = candidates.loc[: pd.Timestamp(end)]
        for idx, row in candidates.tail(max_dates).iterrows():
            rows.append(
                {
                    "Snapshot_Date": pd.Timestamp(idx).date().isoformat(),
                    "Options_Status": "ALPACA_BACKFILL_REQUESTED",
                    "Spot": _safe_float(row.get(self.config.close_column)),
                    "Put_Call_Premium_Ratio": np.nan,
                    "Options_Source": "alpaca-options-bars",
                }
            )
        result = pd.DataFrame(rows)
        if not result.empty:
            self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            existing = self.load_history()
            combined = pd.concat([existing, result], ignore_index=True) if not existing.empty else result
            combined = combined.drop_duplicates("Snapshot_Date", keep="last")
            combined.to_csv(self.snapshot_path, index=False)
        return result


class NewsSentimentCore:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.cache_path = Path(config.news_cache_path)

    def load_cache(self) -> pd.DataFrame:
        if not self.cache_path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(self.cache_path)
        except Exception:
            return pd.DataFrame()

    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        frame = pd.DataFrame(index=data.index)
        frame["News_Signal"] = np.nan
        frame["News_Status"] = "NOT_REQUIRED" if not self.config.require_news_signal else "CACHE_NOT_READY"
        if not self.config.require_news_signal:
            frame["News_Signal"] = 0.0
            return frame
        cache = self.load_cache()
        if cache.empty or "Date" not in cache:
            return frame
        cache = cache.copy()
        cache["Date"] = pd.to_datetime(cache["Date"], errors="coerce").dt.normalize()
        latest = cache.dropna(subset=["Date"]).drop_duplicates("Date", keep="last").set_index("Date")
        aligned = latest.reindex(frame.index.normalize())
        if "News_Signal" in aligned:
            frame["News_Signal"] = pd.to_numeric(aligned["News_Signal"], errors="coerce").to_numpy()
            frame["News_Status"] = np.where(np.isfinite(frame["News_Signal"]), "READY", "CACHE_NOT_READY")
        return frame

    def fetch_eia_storage_and_cache(self, start: str, end: str | None = None) -> pd.DataFrame:
        api_key = _eia_api_key()
        if not api_key:
            raise RuntimeError("Set EIA_API_KEY for official EIA Natural Gas Storage backfill")
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("Install requests for EIA storage data: pip install requests") from exc
        url = f"{self.config.eia_api_base_url.rstrip('/')}/v2/seriesid/{self.config.eia_storage_series_id}"
        params = {"api_key": api_key}
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("response", {}).get("data", []) or payload.get("series", [{}])[0].get("data", [])
        parsed: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                period = row.get("period") or row.get("date")
                value = row.get("value")
            elif isinstance(row, (list, tuple)) and len(row) >= 2:
                period, value = row[0], row[1]
            else:
                continue
            dt = pd.to_datetime(period, errors="coerce")
            val = _safe_float(value)
            if pd.isna(dt) or not np.isfinite(val):
                continue
            parsed.append({"Date": pd.Timestamp(dt).date().isoformat(), "News_Signal": 0.0, "EIA_Value": val, "News_Source": "eia-storage"})
        result = pd.DataFrame(parsed)
        if not result.empty:
            result = result.sort_values("Date")
            result["Storage_Change"] = pd.to_numeric(result["EIA_Value"], errors="coerce").diff()
            result["News_Signal"] = np.where(result["Storage_Change"] < 0, 1.0, np.where(result["Storage_Change"] > 0, -1.0, 0.0))
            start_ts = pd.Timestamp(start)
            result = result.loc[pd.to_datetime(result["Date"]) >= start_ts]
            if end:
                result = result.loc[pd.to_datetime(result["Date"]) <= pd.Timestamp(end)]
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            existing = self.load_cache()
            combined = pd.concat([existing, result], ignore_index=True) if not existing.empty else result
            combined = combined.drop_duplicates("Date", keep="last").sort_values("Date")
            combined.to_csv(self.cache_path, index=False)
        return result


class ForecastManager:
    def __init__(self, config: StrategyConfig, weights: ForecastWeights | None = None) -> None:
        self.config = config
        self.weights = weights or ForecastWeights()
        self.weights.validate()

    def build(self, data: pd.DataFrame, signals: list[pd.DataFrame | pd.Series]) -> pd.DataFrame:
        frame = pd.DataFrame(index=data.index)
        for signal in signals:
            if isinstance(signal, pd.Series):
                frame[signal.name or "Signal"] = signal
            else:
                frame = frame.join(signal)
        frame["Shifted_Algo_Signal"] = frame.get("Algo_Signal", pd.Series(index=frame.index, dtype=float)).shift(1)
        frame["Shifted_Options_Signal"] = frame.get("Options_Signal", pd.Series(index=frame.index, dtype=float)).shift(1)
        frame["Shifted_News_Signal"] = frame.get("News_Signal", pd.Series(index=frame.index, dtype=float)).shift(1)
        required = ["Shifted_Algo_Signal", "Shifted_Options_Signal"]
        if self.config.require_news_signal:
            required.append("Shifted_News_Signal")
        ready = frame[required].notna().all(axis=1)
        frame["Composite_Score"] = np.nan
        news_component = frame["Shifted_News_Signal"] if self.config.require_news_signal else 0.0
        frame.loc[ready, "Composite_Score"] = (
            self.weights.algo * frame.loc[ready, "Shifted_Algo_Signal"]
            + self.weights.options * frame.loc[ready, "Shifted_Options_Signal"]
            + self.weights.news * (news_component.loc[ready] if hasattr(news_component, "loc") else 0.0)
        )
        frame["Forecast_Action"] = "DATA_NOT_READY"
        frame.loc[ready & (frame["Composite_Score"] >= self.config.buy_threshold), "Forecast_Action"] = "BUY_OR_HOLD_LONG"
        frame.loc[ready & (frame["Composite_Score"] <= self.config.sell_threshold), "Forecast_Action"] = "SELL_TO_CASH"
        frame.loc[ready & frame["Forecast_Action"].eq("DATA_NOT_READY"), "Forecast_Action"] = "HOLD_STATE"
        return frame


class ScorecardManager:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    def build(self, data: pd.DataFrame, forecast: pd.DataFrame) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        close = data[self.config.close_column].astype(float)
        for signal_date, row in forecast.iterrows():
            score = _safe_float(row.get("Composite_Score"))
            if not np.isfinite(score):
                continue
            loc = close.index.get_loc(signal_date)
            if not isinstance(loc, int):
                continue
            for horizon in self.config.scorecard_horizons:
                if loc + horizon >= len(close):
                    continue
                ret = (close.iloc[loc + horizon] / close.iloc[loc]) - 1.0
                pred = 1 if score > self.config.scorecard_neutral_band else -1 if score < -self.config.scorecard_neutral_band else 0
                actual = 1 if ret > 0 else -1 if ret < 0 else 0
                rows.append({"Signal_Date": signal_date.date().isoformat(), "Horizon": horizon, "Composite_Score": score, "Forward_Return": ret, "Hit": pred == actual})
        return pd.DataFrame(rows)

    def summarize(self, scorecard: pd.DataFrame) -> pd.DataFrame:
        if scorecard.empty:
            return pd.DataFrame()
        return scorecard.groupby("Horizon").agg(Samples=("Hit", "size"), Hit_Rate=("Hit", "mean"), Avg_Return=("Forward_Return", "mean")).reset_index()

    def report(self, scorecard: pd.DataFrame, summary: pd.DataFrame) -> list[str]:
        if scorecard.empty:
            return ["Scorecard rows: 0"]
        return [f"Scorecard rows: {len(scorecard)}", f"Scorecard horizons: {', '.join(map(str, sorted(scorecard['Horizon'].unique())))}"]


class LongOnlyExecutionEngine:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    def run(self, data: pd.DataFrame, forecast: pd.DataFrame) -> pd.DataFrame:
        shares = self.config.initial_shares
        cash = self.config.initial_cash
        in_market = shares > 0
        rows: list[dict[str, Any]] = []
        for idx, prices in data.iterrows():
            close_price = _safe_float(prices[self.config.close_column])
            action = forecast.loc[idx, "Forecast_Action"] if idx in forecast.index else "DATA_NOT_READY"
            if action == "SELL_TO_CASH" and in_market:
                cash += shares * close_price
                shares = 0.0
                in_market = False
            elif action == "BUY_OR_HOLD_LONG" and not in_market and close_price > 0:
                shares = cash / close_price
                cash = 0.0
                in_market = True
            rows.append({"Date": idx.date().isoformat(), "Close": close_price, "Forecast_Action": action, "Shares": shares, "Cash": cash, "Portfolio_Value": cash + shares * close_price})
        return pd.DataFrame(rows)


class SystemStatusManager:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    def options_cache_status(self) -> dict[str, Any]:
        path = self.config.options_snapshot_path
        if not path.exists():
            return {"rows": 0, "latest_date": "NONE", "source": "NONE"}
        frame = pd.read_csv(path)
        latest = str(frame.get("Snapshot_Date", pd.Series(dtype=str)).dropna().max() or "NONE")
        source = str(frame.get("Options_Source", pd.Series(["cache"])).dropna().iloc[-1]) if not frame.empty else "NONE"
        return {"rows": int(len(frame)), "latest_date": latest, "source": source}

    def news_cache_status(self) -> dict[str, Any]:
        path = Path(self.config.news_cache_path)
        if not path.exists():
            return {"rows": 0, "latest_date": "NONE", "provider": os.getenv("NEWS_PROVIDER", "").strip() or self.config.news_provider}
        frame = pd.read_csv(path)
        latest = str(frame.get("Date", pd.Series(dtype=str)).dropna().max() or "NONE")
        return {"rows": int(len(frame)), "latest_date": latest, "provider": os.getenv("NEWS_PROVIDER", "").strip() or self.config.news_provider}

    def hmm_cache_status(self) -> dict[str, Any]:
        path = self.config.hmm_cache_path
        if not path.exists():
            return {"rows": 0, "latest_date": "NONE", "status": "ENABLED_EMPTY" if self.config.hmm_cache_enabled else "DISABLED"}
        frame = pd.read_csv(path)
        latest = str(frame.get("Date", pd.Series(dtype=str)).dropna().max() or "NONE")
        return {"rows": int(len(frame)), "latest_date": latest, "status": "ENABLED" if self.config.hmm_cache_enabled else "DISABLED"}

    def build_report(self, data: pd.DataFrame, forecast: pd.DataFrame, ledger: pd.DataFrame) -> list[str]:
        ready = int(forecast["Composite_Score"].notna().sum()) if "Composite_Score" in forecast else 0
        latest_action = str(ledger["Forecast_Action"].iloc[-1]) if not ledger.empty else "NONE"
        provider = data.attrs.get("market_data_provider", "UNKNOWN")
        feed = data.attrs.get("market_data_feed", "UNKNOWN")
        return [f"Provider/feed: {provider}/{feed}", f"Forecast-ready rows: {ready}/{len(forecast)}", f"Latest action: {latest_action}"]


class ETFStrategyPipeline:
    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or StrategyConfig()
        self.data_client = MarketDataClient(self.config)
        self.algo_core = AlgoSignalCore(self.config)
        self.options_core = UNGOptionsChainSignalCore(self.config)
        self.news_core = NewsSentimentCore(self.config)
        self.forecast_manager = ForecastManager(self.config)
        self.scorecard_manager = ScorecardManager(self.config)
        self.execution_engine = LongOnlyExecutionEngine(self.config)
        self.status_manager = SystemStatusManager(self.config)

    def run(self, start: str, end: str | None = None) -> pd.DataFrame:
        data = self.data_client.fetch(start=start, end=end)
        signals = [self.algo_core.generate(data), self.options_core.generate(data), self.news_core.generate(data)]
        forecast = self.forecast_manager.build(data, signals)
        scorecard = self.scorecard_manager.build(data, forecast)
        summary = self.scorecard_manager.summarize(scorecard)
        ledger = self.execution_engine.run(data, forecast)
        ledger.attrs.update(
            {
                "daily_data": data,
                "forecast": forecast,
                "readiness_report": self.status_manager.build_report(data, forecast, ledger),
                "scorecard": scorecard,
                "scorecard_summary": summary,
                "scorecard_report": self.scorecard_manager.report(scorecard, summary),
            }
        )
        return ledger


UNGStrategyPipeline = ETFStrategyPipeline


def build_feed_preflight_report(config: StrategyConfig) -> list[str]:
    status = SystemStatusManager(config)
    key_id, secret_key = _alpaca_credentials()
    eia_key = _eia_api_key()
    options = status.options_cache_status()
    news = status.news_cache_status()
    hmm = status.hmm_cache_status()
    provider = os.getenv("MARKET_DATA_PROVIDER", "").strip().lower() or config.market_data_provider
    news_provider = os.getenv("NEWS_PROVIDER", "").strip().lower() or config.news_provider
    alpaca_feed = os.getenv("ALPACA_STOCK_FEED", "").strip().lower() or config.alpaca_stock_feed
    try:
        import hmmlearn  # noqa: F401
        hmm_backend = "hmmlearn"
        hmm_ready = True
    except ImportError:
        hmm_backend = "MISSING (hmmlearn required)"
        hmm_ready = False
    lines = [
        f"Profile: {config.profile_name} ({config.profile_label})",
        f"Ticker: {config.ticker}",
        f"Market provider setting: {provider}",
        f"Alpaca stock feed: {alpaca_feed}",
        f"News provider setting: {news_provider}",
        f"Alpaca credentials: {'SET' if key_id and secret_key else 'MISSING'}",
        f"EIA API key: {'SET' if eia_key else 'MISSING'}",
        f"HMM backend: {hmm_backend}",
        f"HMM cache: {hmm['status']} ({hmm['rows']} rows; latest={hmm['latest_date']})",
        f"Options cache: {options['rows']}/{config.options_warmup_snapshots} rows (latest={options['latest_date']}; source={options['source']})",
        f"News/event cache: {news['rows']} rows (latest={news['latest_date']}; provider={news['provider']})",
    ]
    missing: list[str] = []
    if not (key_id and secret_key):
        missing.append("ALPACA_API_KEY_ID and ALPACA_SECRET_KEY")
    if config.require_news_signal and not eia_key:
        missing.append("EIA_API_KEY")
    if not hmm_ready:
        missing.append("hmmlearn Python package")
    lines.append("Missing API/env values: " + (", ".join(missing) if missing else "none detected"))
    if alpaca_feed == "iex":
        lines.append("Feed warning: ALPACA_STOCK_FEED=iex is useful for development, but SIP is preferred for production intraday/volume-sensitive work.")
    if config.require_news_signal and news_provider == "forexfactory":
        lines.append("Feed warning: NEWS_PROVIDER=forexfactory will not refresh EIA rows during normal forecast runs. Use NEWS_PROVIDER=auto after EIA_API_KEY is set.")
    lines.append("Suggested next commands:")
    if config.require_news_signal and not eia_key:
        lines.append("- Add EIA_API_KEY to .env/Streamlit/GitHub secrets, then rerun this preflight.")
    if int(options["rows"]) < config.options_warmup_snapshots:
        lines.append("- Add Alpaca credentials and run --backfill-options before relying on options signals.")
    lines.append(f"- After caches are ready: python ung_long_only_strategy.py --profile {config.profile_name} --start 2018-01-01 --tail 60")
    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the hosted ETF Forecast Manager runtime.")
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--list-profiles", action="store_true")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--hmm-cache-dir", default=None)
    parser.add_argument("--no-hmm-cache", action="store_true")
    parser.add_argument("--backfill-news", action="store_true")
    parser.add_argument("--backfill-news-provider", choices=["auto", "forexfactory", "eia", "eia_storage"], default=None)
    parser.add_argument("--backfill-options", action="store_true")
    parser.add_argument("--options-backfill-limit", type=int, default=20)
    parser.add_argument("--backfill-only", action="store_true")
    parser.add_argument("--check-feeds", action="store_true")
    parser.add_argument("--tail", type=int, default=60)
    parser.add_argument("--csv", default=None)
    parser.add_argument("--scorecard-csv", default=None)
    parser.add_argument("--scorecard-summary-csv", default=None)
    parser.add_argument("--intraday", action="store_true")
    parser.add_argument("--intraday-only", action="store_true")
    parser.add_argument("--intraday-start", default=None)
    parser.add_argument("--intraday-end", default=None)
    parser.add_argument("--intraday-period", default=None)
    parser.add_argument("--intraday-interval", default=None)
    parser.add_argument("--intraday-tail", type=int, default=20)
    parser.add_argument("--intraday-csv", default=None)
    parser.add_argument("--intraday-scorecard", action="store_true")
    parser.add_argument("--intraday-scorecard-csv", default=None)
    parser.add_argument("--intraday-scorecard-summary-csv", default=None)
    return parser.parse_args()


def main() -> None:
    load_env_file()
    args = parse_args()
    if args.list_profiles:
        print("Built-in ETF profiles")
        for line in ETFProfileRegistry.describe_profiles():
            print(f"- {line}")
        return
    ticker = args.ticker or os.getenv("ETF_TICKER", "").strip() or None
    profile = args.profile or os.getenv("ETF_PROFILE", "").strip() or None
    config = ETFProfileRegistry.build_config(profile_name=profile, ticker=ticker)
    config = replace(
        config,
        alpaca_trading_base_url=os.getenv("ALPACA_TRADING_BASE_URL", "").strip() or config.alpaca_trading_base_url,
        eia_storage_series_id=os.getenv("EIA_STORAGE_SERIES_ID", "").strip() or config.eia_storage_series_id,
        hmm_cache_dir=args.hmm_cache_dir or os.getenv("HMM_CACHE_DIR", "").strip() or config.hmm_cache_dir,
        hmm_cache_enabled=False if args.no_hmm_cache else _env_bool("HMM_CACHE_ENABLED", config.hmm_cache_enabled),
    )
    pipeline = ETFStrategyPipeline(config)
    end = args.end or date.today().isoformat()
    if args.check_feeds:
        print("Feed/API preflight report")
        for line in build_feed_preflight_report(config):
            print(f"- {line}")
        return
    if args.backfill_news:
        if (args.backfill_news_provider or "auto") in {"auto", "eia", "eia_storage"}:
            rows = pipeline.news_core.fetch_eia_storage_and_cache(start=args.start, end=end)
            print(f"EIA rows cached: {len(rows)}")
        if args.backfill_only and not args.backfill_options:
            return
    if args.backfill_options:
        data = pipeline.data_client.fetch(start=args.start, end=end)
        rows = pipeline.options_core.backfill_alpaca_history(data=data, start=args.start, end=end, max_dates=args.options_backfill_limit)
        print(f"Option dates processed: {len(rows)}")
        if args.backfill_only:
            return
    if args.intraday_only:
        print("Intraday runtime is reserved for the full local engine.")
        return
    ledger = pipeline.run(start=args.start, end=end)
    if args.csv:
        ledger.to_csv(args.csv, index=False)
    scorecard = ledger.attrs.get("scorecard", pd.DataFrame())
    summary = ledger.attrs.get("scorecard_summary", pd.DataFrame())
    if args.scorecard_csv and not scorecard.empty:
        scorecard.to_csv(args.scorecard_csv, index=False)
    if args.scorecard_summary_csv and not summary.empty:
        summary.to_csv(args.scorecard_summary_csv, index=False)
    for title, report in (("Forecast Manager warm-up report", ledger.attrs.get("readiness_report", [])), ("Scorecard Manager report", ledger.attrs.get("scorecard_report", []))):
        if report:
            print(title)
            for line in report:
                print(f"- {line}")
            print()
    display = ledger if args.tail == 0 else ledger.tail(args.tail)
    with pd.option_context("display.max_rows", None, "display.width", 180):
        print(display.to_string(index=False))


if __name__ == "__main__":
    main()
