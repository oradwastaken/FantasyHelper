"""Configuration loading for FantasyHelper."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "league": {"yahoo_league_id": "465.l.6920", "team_count": 8,
               "my_team_name": "Slaffing From The Throne",
               "rival_team_name": "McJesus Take The Wheel"},
    "season": {"target": "20262027", "historical": "20252026",
               "games_per_season": 84, "regular_season_game_type": 2},
    "roster": {"active_slots": {"C": 4, "LW": 4, "RW": 4, "D": 6, "UTIL": 2, "G": 4},
               "total_roster_size": 30},
    "ranking": {"methodology": "z_score", "projection_weight": 0.70,
                "historical_weight": 0.30, "goalie_min_games_played": 15,
                "schedule_tiebreaker_weight": 0.05, "playoff_tiebreaker_weight": 0.10,
                "rival_tiebreaker_weight": 0.05},
    "schedule": {"start_date": "2026-10-05", "end_date": "2027-04-18",
                 "playoff_weeks": [], "rival_matchup_weeks": []},
    "sources": {"projections_sheet_url": "", "projections_tab": "Player Values - Cats",
                "cache_directory": "data/cache"},
    "google_sheets": {"spreadsheet_title": "Fantasy Hockey Rankings",
                      "spreadsheet_id": "", "credentials_path": ".secrets/google-oauth-client.json",
                      "token_path": ".secrets/google-token.json"},
}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    """Load YAML configuration, applying safe defaults for omitted values."""
    config = deepcopy(DEFAULT_CONFIG)
    config_path = Path(path)
    if config_path.exists():
        with config_path.open(encoding="utf-8") as handle:
            supplied = yaml.safe_load(handle) or {}
        if not isinstance(supplied, dict):
            raise ValueError("config.yaml must contain a YAML mapping")
        _merge(config, supplied)
    weights = config["ranking"]
    if weights["projection_weight"] < 0 or weights["historical_weight"] < 0:
        raise ValueError("Projection and historical weights must be non-negative")
    if config["league"]["team_count"] < 1:
        raise ValueError("league.team_count must be positive")
    return config
