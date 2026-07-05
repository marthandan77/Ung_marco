from __future__ import annotations

from typing import Dict, List, Tuple


def apply_veto(candidate: str, plan: Dict, structure: Dict, settings: Dict, macro_bias: str = "mixed") -> Tuple[str, str, List[str]]:
    reasons: List[str] = []
    if structure.get("status") != "ok":
        reasons.append("Data unavailable")
    if settings.get("news_block_manual", False):
        reasons.append("Manual news block active")
    if structure.get("middle_range"):
        reasons.append("Price is in middle of current range")
    if candidate == "BUY" and structure.get("near_resistance"):
        reasons.append("BUY rejected near resistance")
    if candidate == "SELL" and structure.get("near_support"):
        reasons.append("SELL rejected near support")
    risk = float(plan.get("risk", 0) or 0)
    atr = float(structure.get("atr", 0) or 0)
    if risk <= 0:
        reasons.append("Invalid risk calculation")
    if atr > 0:
        if risk < float(settings.get("min_sl_atr_fraction", 0.5)) * atr:
            reasons.append("Stop distance too tight")
        if risk > float(settings.get("max_sl_atr_fraction", 2.5)) * atr:
            reasons.append("Stop distance too wide")
    if candidate == "BUY" and macro_bias == "restrictive":
        reasons.append("Macro context conflicts with BUY")
    if candidate == "SELL" and macro_bias == "supportive":
        reasons.append("Macro context conflicts with SELL")
    if candidate in {"WAIT", "HOLD"}:
        return candidate, candidate, reasons
    if reasons:
        return "HOLD", "HOLD - " + reasons[0], reasons
    signal_type = "BUY - Trend Pullback" if candidate == "BUY" else "SELL - Trend Pullback"
    return candidate, signal_type, reasons
