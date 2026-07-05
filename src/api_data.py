from __future__ import annotations

from typing import Mapping

import pandas as pd
import requests


def load_ohlc_from_url(url: str, headers: Mapping[str, str] | None = None) -> pd.DataFrame:
    if not url:
        return pd.DataFrame()
    response = requests.get(url, headers=dict(headers or {}), timeout=20)
    response.raise_for_status()
    data = response.json()
    rows = data.get("data", data if isinstance(data, list) else [])
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df.columns = [str(c).strip().lower() for c in df.columns]
    time_col = "time" if "time" in df.columns else "timestamp" if "timestamp" in df.columns else None
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], utc=True)
        df = df.set_index(time_col)
    return df
