from __future__ import annotations

from typing import Dict

import pandas as pd


def build_structure(df: pd.DataFrame, settings: Dict) -> Dict[str, float | str | bool]:
    if df.empty:
        return {"status": "no_data"}
    lookback = int(settings.get("lookback_days", 7))
    window = df.tail(max(50, lookback * 96)).copy()
    latest = window.iloc[-1]
    high_7d = float(window["high"].max())
    low_7d = float(window["low"].min())
    price = float(latest["close"])
    atr = float(latest.get("atr", 0) or 0)
    atr = atr if atr > 0 else max((high_7d - low_7d) / 50, 0.01)
    resistance = high_7d
    support = low_7d
    recent = window.tail(20)
    swing_high = float(recent["high"].max())
    swing_low = float(recent["low"].min())
    vwap = float(latest.get("vwap", price))
    range_pos = 50.0 if high_7d == low_7d else ((price - low_7d) / (high_7d - low_7d)) * 100
    near_support = abs(price - support) <= settings.get("support_resistance_tolerance_atr", 0.5) * atr
    near_resistance = abs(resistance - price) <= settings.get("support_resistance_tolerance_atr", 0.5) * atr
    near_vwap = abs(price - vwap) <= settings.get("vwap_tolerance_atr", 0.35) * atr
    middle = settings.get("middle_range_lower_pct", 35) <= range_pos <= settings.get("middle_range_upper_pct", 65)
    trend = "range"
    if latest.get("ema_fast", price) > latest.get("ema_slow", price) and price > latest.get("ema_fast", price):
        trend = "up"
    elif latest.get("ema_fast", price) < latest.get("ema_slow", price) and price < latest.get("ema_fast", price):
        trend = "down"
    return {
        "status": "ok",
        "price": price,
        "atr": atr,
        "high_7d": high_7d,
        "low_7d": low_7d,
        "support": support,
        "resistance": resistance,
        "swing_high": swing_high,
        "swing_low": swing_low,
        "vwap": vwap,
        "range_pos": float(range_pos),
        "near_support": bool(near_support),
        "near_resistance": bool(near_resistance),
        "near_vwap": bool(near_vwap),
        "middle_range": bool(middle),
        "trend": trend,
    }
