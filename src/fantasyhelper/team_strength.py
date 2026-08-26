"""League-relative roster strength reports."""

from __future__ import annotations

import pandas as pd

from fantasyhelper.players import normalize_name
from fantasyhelper.projections import ALL_CATEGORIES, GOALIE_CATEGORIES


def build_team_strength(players: pd.DataFrame, rosters: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Aggregate rostered player z-scores and rank each fantasy team."""
    if rosters.empty:
        return pd.DataFrame()
    roster = rosters[["FullName", "fantasy_team", "manager"]].copy()
    roster["name_key"] = roster["FullName"].map(normalize_name)
    values = players.drop_duplicates("name_key").copy()
    merged = roster.merge(values, on="name_key", how="left", suffixes=("_yahoo", ""))
    score_columns = [f"z_{category}" for category in ALL_CATEGORIES]
    for column in score_columns:
        if column not in merged:
            merged[column] = 0.0
    aggregated = merged.groupby(["fantasy_team", "manager"], dropna=False)[score_columns].sum().reset_index()
    aggregated["skater_strength"] = aggregated[[f"z_{category}" for category in ALL_CATEGORIES if category not in GOALIE_CATEGORIES]].sum(axis=1)
    aggregated["goalie_strength"] = aggregated[[f"z_{category}" for category in GOALIE_CATEGORIES]].sum(axis=1)
    for category in ALL_CATEGORIES:
        score_column = f"z_{category}"
        aggregated[f"{category}_rank"] = aggregated[score_column].rank(ascending=False, method="min").astype("Int64")
    aggregated["skater_rank"] = aggregated["skater_strength"].rank(ascending=False, method="min").astype("Int64")
    aggregated["goalie_rank"] = aggregated["goalie_strength"].rank(ascending=False, method="min").astype("Int64")
    category_scores = aggregated[[f"z_{category}" for category in ALL_CATEGORIES]]
    aggregated["best_category"] = category_scores.idxmax(axis=1).str.removeprefix("z_")
    aggregated["weakest_category"] = category_scores.idxmin(axis=1).str.removeprefix("z_")
    return aggregated.sort_values(["skater_strength", "goalie_strength"], ascending=False).reset_index(drop=True)
