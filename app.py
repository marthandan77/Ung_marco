from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent
DEFAULT_SETTINGS = ROOT / "config/default_settings.yaml"
PRESETS = ROOT / "config/presets.yaml"

st.set_page_config(page_title="XAU/USD Advisor", layout="wide")


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def make_sample_data(rows: int = 250) -> pd.DataFrame:
    idx = pd.date_range(end=pd.Timestamp.utcnow(), periods=rows, freq="15min")
    rng = np.random.default_rng(42)
    close = 2350 + np.cumsum(rng.normal(0, 1.8, rows))
    high = close + rng.uniform(0.5, 3.5, rows)
    low = close - rng.uniform(0.5, 3.5, rows)
    open_ = close + rng.normal(0, 0.8, rows)
    volume = rng.integers(100, 1000, rows)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)


def clean_uploaded_csv(uploaded) -> pd.DataFrame:
    df = pd.read_csv(uploaded)
    df.columns = [str(c).strip().lower() for c in df.columns]
    time_col = "time" if "time" in df.columns else "datetime" if "datetime" in df.columns else None
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col])
        df = df.set_index(time_col)
    required = {"open", "high", "low", "close"}
    if not required.issubset(df.columns):
        raise ValueError("CSV must include open, high, low, close columns.")
    if "volume" not in df.columns:
        df["volume"] = 1
    return df.dropna(subset=["open", "high", "low", "close"])


def add_indicators(df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    out = df.copy()
    out["ema_fast"] = out["close"].ewm(span=int(settings.get("ema_fast", 50)), adjust=False).mean()
    out["ema_slow"] = out["close"].ewm(span=int(settings.get("ema_slow", 200)), adjust=False).mean()
    typical = (out["high"] + out["low"] + out["close"]) / 3
    volume = out["volume"].replace(0, 1).fillna(1)
    out["vwap"] = (typical * volume).cumsum() / volume.cumsum()
    prev_close = out["close"].shift(1)
    tr = pd.concat([out["high"] - out["low"], (out["high"] - prev_close).abs(), (out["low"] - prev_close).abs()], axis=1).max(axis=1)
    out["atr"] = tr.rolling(14, min_periods=3).mean()
    delta = out["close"].diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=3).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=3).mean().replace(0, np.nan)
    out["rsi"] = (100 - 100 / (1 + gain / loss)).fillna(50)
    out["adx"] = (tr / out["atr"].replace(0, np.nan) * 20).rolling(14, min_periods=3).mean().fillna(0).clip(0, 60)
    return out


def build_structure(df: pd.DataFrame, settings: dict) -> dict:
    latest = df.iloc[-1]
    window = df.tail(max(50, int(settings.get("lookback_days", 7)) * 96))
    high_7d = float(window["high"].max())
    low_7d = float(window["low"].min())
    price = float(latest["close"])
    atr = float(latest.get("atr", 0) or 0) or max((high_7d - low_7d) / 50, 0.01)
    vwap = float(latest.get("vwap", price))
    range_pos = 50.0 if high_7d == low_7d else (price - low_7d) / (high_7d - low_7d) * 100
    near_support = abs(price - low_7d) <= float(settings.get("support_resistance_tolerance_atr", 0.5)) * atr
    near_resistance = abs(high_7d - price) <= float(settings.get("support_resistance_tolerance_atr", 0.5)) * atr
    near_vwap = abs(price - vwap) <= float(settings.get("vwap_tolerance_atr", 0.35)) * atr
    middle = float(settings.get("middle_range_lower_pct", 35)) <= range_pos <= float(settings.get("middle_range_upper_pct", 65))
    trend = "range"
    if latest["ema_fast"] > latest["ema_slow"] and price > latest["ema_fast"]:
        trend = "up"
    elif latest["ema_fast"] < latest["ema_slow"] and price < latest["ema_fast"]:
        trend = "down"
    return {"price": price, "atr": atr, "high_7d": high_7d, "low_7d": low_7d, "support": low_7d, "resistance": high_7d, "swing_high": float(window.tail(20)["high"].max()), "swing_low": float(window.tail(20)["low"].min()), "vwap": vwap, "range_pos": range_pos, "near_support": near_support, "near_resistance": near_resistance, "near_vwap": near_vwap, "middle_range": middle, "trend": trend}


def score(row: dict, structure: dict, settings: dict, macro_bias: str) -> tuple[int, int]:
    buy = sell = 0
    if macro_bias in {"supportive", "mixed"}: buy += 20
    if macro_bias in {"restrictive", "mixed"}: sell += 20
    if not settings.get("news_block_manual", False):
        buy += 10; sell += 10
    if structure["trend"] == "up": buy += 20
    if structure["trend"] == "down": sell += 20
    if row.get("adx", 0) >= settings.get("adx_minimum", 20):
        if structure["trend"] == "up": buy += 5
        if structure["trend"] == "down": sell += 5
    if structure["near_support"]: buy += 15
    if structure["near_resistance"]: sell += 15
    if structure["near_vwap"]: buy += 5; sell += 5
    if not structure["near_resistance"]: buy += 5
    if not structure["near_support"]: sell += 5
    if row["close"] > row["open"]: buy += 10
    if row["close"] < row["open"]: sell += 10
    if row.get("rsi", 50) >= settings.get("rsi_level", 50): buy += 5
    if row.get("rsi", 50) <= settings.get("rsi_level", 50): sell += 5
    buy += 5; sell += 5
    return int(buy), int(sell)


def choose_candidate(buy_score: int, sell_score: int, settings: dict) -> str:
    if buy_score >= settings.get("buy_threshold", 78) and buy_score > sell_score: return "BUY"
    if sell_score >= settings.get("sell_threshold", 78) and sell_score > buy_score: return "SELL"
    return "WAIT" if max(buy_score, sell_score) >= settings.get("wait_threshold", 60) else "HOLD"


def plan(side: str, structure: dict, settings: dict) -> dict:
    price = structure["price"]; atr = structure["atr"]
    if side == "BUY":
        sl = min(structure["swing_low"], price - settings.get("atr_multiplier", 1.3) * atr)
        risk = max(price - sl, 0.01)
        return {"entry": price, "sl": sl, "tp1": price + settings.get("tp1_r", 1.5) * risk, "tp2": price + settings.get("tp2_r", 2.0) * risk, "risk": risk}
    if side == "SELL":
        sl = max(structure["swing_high"], price + settings.get("atr_multiplier", 1.3) * atr)
        risk = max(sl - price, 0.01)
        return {"entry": price, "sl": sl, "tp1": price - settings.get("tp1_r", 1.5) * risk, "tp2": price - settings.get("tp2_r", 2.0) * risk, "risk": risk}
    return {"entry": price, "sl": price, "tp1": price, "tp2": price, "risk": 0.0}


def apply_veto(candidate: str, p: dict, structure: dict, settings: dict, macro_bias: str) -> tuple[str, str, list[str]]:
    reasons = []
    if settings.get("news_block_manual", False): reasons.append("Manual news block active")
    if structure["middle_range"]: reasons.append("Price is in middle of range")
    if candidate == "BUY" and structure["near_resistance"]: reasons.append("BUY too close to resistance")
    if candidate == "SELL" and structure["near_support"]: reasons.append("SELL too close to support")
    risk = p.get("risk", 0); atr = structure["atr"]
    if risk <= 0: reasons.append("Invalid risk")
    if atr > 0 and risk < settings.get("min_sl_atr_fraction", 0.5) * atr: reasons.append("Stop distance too tight")
    if atr > 0 and risk > settings.get("max_sl_atr_fraction", 2.5) * atr: reasons.append("Stop distance too wide")
    if candidate == "BUY" and macro_bias == "restrictive": reasons.append("Macro conflicts with BUY")
    if candidate == "SELL" and macro_bias == "supportive": reasons.append("Macro conflicts with SELL")
    if candidate not in {"BUY", "SELL"}: return candidate, candidate, reasons
    if reasons: return "HOLD", "HOLD - " + reasons[0], reasons
    return candidate, f"{candidate} - Trend Pullback", reasons


def render_chart(df: pd.DataFrame, structure: dict, p: dict) -> go.Figure:
    fig = go.Figure(go.Candlestick(x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"], name="Price"))
    for col in ["ema_fast", "ema_slow", "vwap"]:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], mode="lines", name=col))
    for label, value in {"7D High": structure["high_7d"], "7D Low": structure["low_7d"], "Entry": p["entry"], "SL": p["sl"], "TP1": p["tp1"], "TP2": p["tp2"]}.items():
        fig.add_hline(y=value, annotation_text=label, line_dash="dot")
    fig.update_layout(height=620, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=20, b=10))
    return fig


settings = load_yaml(DEFAULT_SETTINGS)
presets = load_yaml(PRESETS)
st.sidebar.header("Manual parameters")
if presets:
    preset = st.sidebar.selectbox("Preset", list(presets.keys()), index=list(presets.keys()).index(settings.get("preset_name", "Balanced Strict")) if settings.get("preset_name") in presets else 0)
    if st.sidebar.button("Load preset"):
        settings.update(presets[preset])
settings["news_block_manual"] = st.sidebar.toggle("Manual news block", bool(settings.get("news_block_manual", False)))
settings["buy_threshold"] = st.sidebar.slider("BUY threshold", 50, 95, int(settings.get("buy_threshold", 78)))
settings["sell_threshold"] = st.sidebar.slider("SELL threshold", 50, 95, int(settings.get("sell_threshold", 78)))
settings["wait_threshold"] = st.sidebar.slider("WAIT threshold", 40, 90, int(settings.get("wait_threshold", 60)))
settings["atr_multiplier"] = st.sidebar.slider("ATR multiplier", 0.8, 2.5, float(settings.get("atr_multiplier", 1.3)), 0.1)
settings["min_reward_risk"] = st.sidebar.slider("Minimum reward/risk", 1.0, 3.0, float(settings.get("min_reward_risk", 1.5)), 0.1)
settings["middle_range_lower_pct"] = st.sidebar.slider("Middle range lower %", 10, 49, int(settings.get("middle_range_lower_pct", 35)))
settings["middle_range_upper_pct"] = st.sidebar.slider("Middle range upper %", 51, 90, int(settings.get("middle_range_upper_pct", 65)))
macro_bias = st.sidebar.selectbox("Macro/news bias", ["mixed", "supportive", "restrictive"], index=0)

uploaded = st.sidebar.file_uploader("Optional OHLC CSV", type=["csv"])
if uploaded:
    df = clean_uploaded_csv(uploaded)
    source = "uploaded CSV"
else:
    df = make_sample_data()
    source = "sample data - replace with CSV or provider integration"

df = add_indicators(df, settings)
structure = build_structure(df, settings)
latest = df.iloc[-1].to_dict()
buy_score, sell_score = score(latest, structure, settings, macro_bias)
candidate = choose_candidate(buy_score, sell_score, settings)
p = plan(candidate, structure, settings)
final_signal, signal_type, vetoes = apply_veto(candidate, p, structure, settings, macro_bias)
reason = f"Trend={structure['trend']}. Range location={structure['range_pos']:.1f}%. Macro={macro_bias}."
if vetoes:
    reason += " Rejected: " + "; ".join(vetoes)

st.title("XAU/USD Streamlit Advisor")
st.caption("Manual dashboard. No broker execution. No auto-learning. No setup is better than a weak setup.")
page = st.sidebar.radio("Page", ["Live Advisor", "Chart Scanner", "News/Macro", "Parameter Control", "Signal Log"])

if page == "Live Advisor":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final status", final_signal)
    c2.metric("Signal type", signal_type)
    c3.metric("BUY score", buy_score)
    c4.metric("SELL score", sell_score)
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Entry", f"{p['entry']:,.2f}")
    p2.metric("SL", f"{p['sl']:,.2f}")
    p3.metric("TP1", f"{p['tp1']:,.2f}")
    p4.metric("TP2", f"{p['tp2']:,.2f}")
    st.info(reason)
    if vetoes: st.error("Veto: " + "; ".join(vetoes))
    st.write({"data_source": source})
    st.plotly_chart(render_chart(df, structure, p), use_container_width=True)
elif page == "Chart Scanner":
    st.plotly_chart(render_chart(df, structure, p), use_container_width=True)
    st.json(structure)
elif page == "News/Macro":
    st.write("Use manual news block around CPI, NFP, FOMC, PCE and Fed speeches. API calendar can be added later.")
    st.json({"macro_bias": macro_bias, "manual_news_block": settings["news_block_manual"]})
elif page == "Parameter Control":
    st.json(settings)
    st.download_button("Export settings YAML", yaml.safe_dump(settings, sort_keys=False), file_name="active_settings.yaml")
elif page == "Signal Log":
    row = {"final_signal": final_signal, "signal_type": signal_type, "buy_score": buy_score, "sell_score": sell_score, "entry": p["entry"], "sl": p["sl"], "tp1": p["tp1"], "tp2": p["tp2"], "veto": "; ".join(vetoes), "reason": reason}
    st.dataframe(pd.DataFrame([row]), use_container_width=True)
    st.download_button("Download snapshot CSV", pd.DataFrame([row]).to_csv(index=False), file_name="xauusd_signal_snapshot.csv")
