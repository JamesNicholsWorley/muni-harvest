"""Settings loader. Resolves the repo root and reads config/settings.toml.

tomllib is stdlib on 3.11+, so this stays dependency-free.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

# repo root = three parents up from this file: src/muni_harvest/config.py -> repo/
REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = REPO_ROOT / "config" / "settings.toml"


def load_settings() -> dict:
    with SETTINGS_PATH.open("rb") as fh:
        return tomllib.load(fh)


def resolve_path(p: str) -> Path:
    """Resolve a settings path relative to the repo root (absolute passes through)."""
    path = Path(p)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def data_dir() -> Path:
    d = resolve_path(load_settings()["paths"]["data_dir"])
    d.mkdir(parents=True, exist_ok=True)
    return d
