from __future__ import annotations

from typing import Dict


def build_plan(side: str, structure: Dict, settings: Dict) -> Dict[str, float | str]:
    price = float(structure.get("price", 0))
    atr = float(structure.get("atr", 0.01) or 0.01)
    atr_mult = float(settings.get("atr_multiplier", 1.3))
    tp1_r = float(settings.get("tp1_r", 1.5))
    tp2_r = float(settings.get("tp2_r", 2.0))
    if side == "BUY":
        sl = min(float(structure.get("swing_low", price - atr)), price - atr_mult * atr)
        risk = max(price - sl, 0.01)
        return {"entry": price, "sl": sl, "tp1": price + tp1_r * risk, "tp2": price + tp2_r * risk, "risk": risk, "side": side}
    if side == "SELL":
        sl = max(float(structure.get("swing_high", price + atr)), price + atr_mult * atr)
        risk = max(sl - price, 0.01)
        return {"entry": price, "sl": sl, "tp1": price - tp1_r * risk, "tp2": price - tp2_r * risk, "risk": risk, "side": side}
    return {"entry": price, "sl": price, "tp1": price, "tp2": price, "risk": 0.0, "side": side}


def reward_risk(side: str, plan: Dict, structure: Dict) -> float:
    risk = float(plan.get("risk", 0) or 0)
    if risk <= 0:
        return 0.0
    if side == "BUY":
        room = float(structure.get("resistance", plan["tp1"])) - float(plan["entry"])
    elif side == "SELL":
        room = float(plan["entry"]) - float(structure.get("support", plan["tp1"]))
    else:
        return 0.0
    return max(room / risk, 0.0)
