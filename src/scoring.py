from __future__ import annotations

from typing import Dict, Tuple


def score_setups(row: Dict, structure: Dict, macro_bias: str, settings: Dict) -> Tuple[int, int, Dict[str, str]]:
    buy = 0
    sell = 0
    reasons = {}

    # Macro/news block: 30 points
    if macro_bias in {"supportive", "mixed", "unknown"}:
        buy += 10
    if macro_bias in {"restrictive", "mixed", "unknown"}:
        sell += 10
    if not settings.get("news_block_manual", False):
        buy += 10
        sell += 10
    buy += 10 if macro_bias == "supportive" else 0
    sell += 10 if macro_bias == "restrictive" else 0

    # Trend/regime: 25 points
    if structure.get("trend") == "up":
        buy += 10
    if structure.get("trend") == "down":
        sell += 10
    adx_ok = float(row.get("adx", 0) or 0) >= float(settings.get("adx_minimum", 20))
    if adx_ok:
        buy += 5 if structure.get("trend") == "up" else 0
        sell += 5 if structure.get("trend") == "down" else 0
    buy += 5
    sell += 5
    if structure.get("trend") == "up":
        buy += 5
    if structure.get("trend") == "down":
        sell += 5

    # Levels: 25 points
    if structure.get("near_support"):
        buy += 10
    if structure.get("near_resistance"):
        sell += 10
    if structure.get("near_vwap"):
        buy += 5
        sell += 5
    if not structure.get("near_resistance"):
        buy += 5
    if not structure.get("near_support"):
        sell += 5
    buy += 5 if structure.get("range_pos", 50) < 70 else 0
    sell += 5 if structure.get("range_pos", 50) > 30 else 0

    # Entry trigger: 20 points
    close = float(row.get("close", 0) or 0)
    open_ = float(row.get("open", close) or close)
    rsi = float(row.get("rsi", 50) or 50)
    rsi_level = float(settings.get("rsi_level", 50))
    if close > open_:
        buy += 10
    if close < open_:
        sell += 10
    if rsi >= rsi_level:
        buy += 5
    if rsi <= rsi_level:
        sell += 5
    buy += 5
    sell += 5

    reasons["buy"] = f"buy score {buy}: trend={structure.get('trend')}, macro={macro_bias}, zone={structure.get('range_pos', 50):.1f}%"
    reasons["sell"] = f"sell score {sell}: trend={structure.get('trend')}, macro={macro_bias}, zone={structure.get('range_pos', 50):.1f}%"
    return int(buy), int(sell), reasons


def choose_candidate(buy_score: int, sell_score: int, settings: Dict) -> str:
    if buy_score >= int(settings.get("buy_threshold", 78)) and buy_score > sell_score:
        return "BUY"
    if sell_score >= int(settings.get("sell_threshold", 78)) and sell_score > buy_score:
        return "SELL"
    best = max(buy_score, sell_score)
    return "WAIT" if best >= int(settings.get("wait_threshold", 60)) else "HOLD"
