"""Region configs for burn-window analysis. Each module defines THRESHOLDS, STATIONS, DATA_CSV, SOURCE."""
from importlib import import_module


def load(name: str):
    return import_module(f"src.regions.{name}")
