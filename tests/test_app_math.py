import importlib.util
from pathlib import Path


def test_app_exists():
    assert Path('app.py').exists()


def test_config_exists():
    assert Path('config/default_settings.yaml').exists()
    assert Path('config/presets.yaml').exists()
