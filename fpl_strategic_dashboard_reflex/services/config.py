"""Configuration loader for FPL Strategic Dashboard Reflex.
Reads configuration from environment variables and config.json.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict


def get_project_root() -> Path:
    """Returns the project root directory."""
    return Path(__file__).resolve().parents[2]


def load_config() -> Dict[str, Any]:
    """Loads configuration from config.json if present.
    Searches in:
    1. Current working directory
    2. Project root directory
    """
    candidate_paths = [
        Path.cwd() / "config.json",
        get_project_root() / "config.json",
    ]

    for p in candidate_paths:
        try:
            if p.is_file():
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception:
            continue

    return {}


def get_odds_api_key() -> str:
    """Retrieves the Odds API key with fallback order:
    1. Environment variable ODDS_API_KEY
    2. config.json key 'ODDS_API_KEY' or 'odds_api_key'
    """
    env_key = os.getenv("ODDS_API_KEY", "").strip()
    if env_key:
        return env_key

    cfg = load_config()
    key = cfg.get("ODDS_API_KEY") or cfg.get("odds_api_key")
    if key and isinstance(key, str):
        return key.strip()

    return ""
