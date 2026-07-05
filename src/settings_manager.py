from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DEFAULT_SETTINGS = CONFIG_DIR / "default_settings.yaml"
ACTIVE_SETTINGS = CONFIG_DIR / "active_settings.yaml"
PRESETS = CONFIG_DIR / "presets.yaml"


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return dict(data)


def load_settings() -> Dict[str, Any]:
    settings = _read_yaml(DEFAULT_SETTINGS)
    settings.update(_read_yaml(ACTIVE_SETTINGS))
    return settings


def load_presets() -> Dict[str, Dict[str, Any]]:
    return _read_yaml(PRESETS)


def save_active_settings(settings: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with ACTIVE_SETTINGS.open("w", encoding="utf-8") as f:
        yaml.safe_dump(settings, f, sort_keys=False)


def merge_settings(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    merged.update(override)
    return merged
