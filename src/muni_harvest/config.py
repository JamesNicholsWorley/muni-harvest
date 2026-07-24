"""Settings loader. Resolves the repo root and reads config/settings.toml.

tomllib is stdlib on 3.11+, so this stays dependency-free.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

# repo root = three parents up from this file: src/muni_harvest/config.py -> repo/
REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = REPO_ROOT / "config" / "settings.toml"


def load_env(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from .env into os.environ (no python-dotenv dep).
    Existing env vars win, so real environment/CI secrets aren't overwritten."""
    p = path or (REPO_ROOT / ".env")
    if not p.exists():
        return
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


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


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")]


def excluded_hosts() -> set[str]:
    """News/media hosts to drop from all target lists (config/exclude_hosts.txt)."""
    return set(_read_lines(REPO_ROOT / "config" / "exclude_hosts.txt"))


def host_overrides() -> dict[str, str]:
    """bad_host -> good_host corrections (config/host_overrides.csv)."""
    out: dict[str, str] = {}
    for ln in _read_lines(REPO_ROOT / "config" / "host_overrides.csv"):
        if "," in ln and not ln.startswith("bad_host"):
            bad, good = ln.split(",", 1)
            out[bad.strip()] = good.strip()
    return out
