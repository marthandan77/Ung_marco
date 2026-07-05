from __future__ import annotations

import pandas as pd


def load_uploaded_csv(file) -> pd.DataFrame:
    df = pd.read_csv(file)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
    return df
