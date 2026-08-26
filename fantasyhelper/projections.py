"""Historical proration and projection blending."""

from __future__ import annotations

import pandas as pd

from fantasyhelper.players import normalize_name

SKATER_CATEGORIES = ["G", "A", "+/-", "PIM", "PPP", "SHP", "SOG", "FOW", "HIT", "BLK"]
GOALIE_CATEGORIES = ["W", "GAA", "SV%", "SO"]
ALL_CATEGORIES = SKATER_CATEGORIES + GOALIE_CATEGORIES
ALIASES = {"FW": "FOW", "SHO": "SO", "SVPCT": "SV%", "SAVE%": "SV%", "PLUSMINUS": "+/-"}


def canonicalize_stats(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.rename(columns={column: ALIASES.get(column.upper().replace(" ", ""), column) for column in result.columns}, inplace=True)
    for category in ALL_CATEGORIES:
        if category not in result:
            result[category] = pd.NA
    return result


def prorate_historical(frame: pd.DataFrame, games_per_season: int) -> pd.DataFrame:
    result = canonicalize_stats(frame)
    if "GP" not in result:
        raise ValueError("Historical data must contain GP")
    gp = pd.to_numeric(result["GP"], errors="coerce")
    for category in ALL_CATEGORIES:
        if category in result and category not in ("GAA", "SV%"):
            result[f"historical_{category}"] = pd.to_numeric(result[category], errors="coerce").div(gp).mul(games_per_season)
        elif category in result:
            result[f"historical_{category}"] = pd.to_numeric(result[category], errors="coerce")
    result["low_sample"] = gp.lt(1) | gp.isna()
    return result


def blend_projections(historical: pd.DataFrame, projections: pd.DataFrame, games_per_season: int,
                      projection_weight: float, historical_weight: float) -> pd.DataFrame:
    """Blend projections where available; gracefully use historical-only rows."""
    historical = prorate_historical(historical, games_per_season)
    historical["name_key"] = historical["FullName"].map(normalize_name)
    if projections is None or projections.empty:
        result = historical.copy()
        for category in ALL_CATEGORIES:
            result[category] = result.get(f"historical_{category}")
        result["projection_available"] = False
        return result
    projected = canonicalize_stats(projections)
    name_column = next((column for column in ("FullName", "Player", "Name", "Player Name") if column in projected), None)
    if name_column is None:
        raise ValueError("Projection sheet needs a FullName, Player, Name, or Player Name column")
    projected["name_key"] = projected[name_column].map(normalize_name)
    projected = projected.drop_duplicates("name_key")
    result = historical.merge(projected, on="name_key", how="outer", suffixes=("", "_projection"))
    projection_name = f"{name_column}_projection" if name_column in historical.columns else name_column
    if "FullName" not in result:
        result["FullName"] = result[projection_name]
    elif projection_name in result:
        result["FullName"] = result["FullName"].fillna(result[projection_name])
    for category in ALL_CATEGORIES:
        historical_column = f"historical_{category}"
        projected_column = category + "_projection" if category in historical.columns else category
        if projected_column not in result:
            projected_column = category if category in result else None
        historical_values = result.get(historical_column)
        projected_values = pd.to_numeric(result[projected_column], errors="coerce") if projected_column else None
        if historical_values is None:
            result[category] = projected_values
        elif projected_values is None:
            result[category] = historical_values
        else:
            both = historical_values.notna() & projected_values.notna()
            result[category] = historical_values.where(~both, historical_values * historical_weight + projected_values * projection_weight)
            result[category] = result[category].fillna(projected_values)
    result["projection_available"] = result["name_key"].isin(projected["name_key"])
    return result
