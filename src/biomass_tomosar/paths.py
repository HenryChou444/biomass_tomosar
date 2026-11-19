"""Resolve machine-local dataset locations from config/local.toml."""

from pathlib import Path
import tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "config" / "local.toml"


def get_data_path(key: str, default: str) -> Path:
    settings = {}
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("rb") as f:
            settings = tomllib.load(f)
    raw_value = settings.get("paths", {}).get(key, default)
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def biomass_stack_dir() -> Path:
    return get_data_path("biomass_stack", "data/BIOMASS_STACK")


def mondah_dir() -> Path:
    return get_data_path("mondah", "data/mondah")
