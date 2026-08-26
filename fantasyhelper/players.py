"""Player identity normalization and Yahoo eligibility handling."""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

SKATER_POSITIONS = ("C", "LW", "RW", "D")


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z]", "", text.casefold())


def clean_eligibility(value: object, fallback: object = "") -> list[str]:
    positions = value if isinstance(value, list) else []
    eligible = [position for position in positions if position in (*SKATER_POSITIONS, "G")]
    if not eligible and isinstance(fallback, str) and fallback in (*SKATER_POSITIONS, "G"):
        eligible = [str(fallback)]
    return eligible


def attach_yahoo_eligibility(players: pd.DataFrame, rosters: pd.DataFrame | None) -> pd.DataFrame:
    """Attach Yahoo eligibility by normalized name; keep NHL position as fallback."""
    result = players.copy()
    result["name_key"] = result["FullName"].map(normalize_name)
    # This function may be applied again after projection rows are merged in.
    result = result.drop(columns=["eligible_positions"], errors="ignore")
    if rosters is None or rosters.empty:
        result["eligible_positions"] = result.apply(lambda row: clean_eligibility([], row.get("position")), axis=1)
        return result
    yahoo = rosters.copy()
    yahoo["name_key"] = yahoo["FullName"].map(normalize_name)
    yahoo["eligible_positions"] = yahoo.apply(lambda row: clean_eligibility(row.get("position", [])), axis=1)
    eligibility = yahoo.groupby("name_key")["eligible_positions"].agg(
        lambda values: sorted(set(position for group in values for position in group))
    )
    result = result.join(eligibility, on="name_key")
    result["eligible_positions"] = result.apply(
        lambda row: row["eligible_positions"] if isinstance(row["eligible_positions"], list) else clean_eligibility([], row.get("position")), axis=1
    )
    return result


def ownership_by_player(rosters: pd.DataFrame) -> pd.DataFrame:
    """Return Yahoo ownership keyed by normalized player name."""
    if rosters.empty:
        return pd.DataFrame(columns=["name_key", "fantasy_team", "manager"])
    result = rosters[["FullName", "fantasy_team", "manager"]].copy()
    result["name_key"] = result["FullName"].map(normalize_name)
    return result.drop_duplicates("name_key")
