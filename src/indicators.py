from __future__ import annotations

import numpy as np
import pandas as pd


def add_indicators(df: pd.DataFrame, ema_fast: int = 50, ema_slow: int = 200) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    out["ema_fast"] = out["close"].ewm(span=ema_fast, adjust=False).mean()
    out["ema_slow"] = out["close"].ewm(span=ema_slow, adjust=False).mean()
    typical = (out["high"] + out["low"] + out["close"]) / 3
    volume = out.get("volume", pd.Series(1.0, index=out.index)).replace(0, 1)
    out["vwap"] = (typical * volume).cumsum() / volume.cumsum()
    prev_close = out["close"].shift(1)
    tr = pd.concat([
        out["high"] - out["low"],
        (out["high"] - prev_close).abs(),
        (out["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["atr"] = tr.rolling(14, min_periods=3).mean()
    delta = out["close"].diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=3).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=3).mean().replace(0, np.nan)
    rs = gain / loss
    out["rsi"] = 100 - (100 / (1 + rs))
    out["rsi"] = out["rsi"].fillna(50)
    up_move = out["high"].diff()
    down_move = -out["low"].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr = out["atr"].replace(0, np.nan)
    plus_di = 100 * pd.Series(plus_dm, index=out.index).rolling(14, min_periods=3).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=out.index).rolling(14, min_periods=3).mean() / atr
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    out["adx"] = dx.rolling(14, min_periods=3).mean().fillna(0)
    return out
