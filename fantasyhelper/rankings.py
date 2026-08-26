"""Category and position rankings based on configurable z-scores."""

from __future__ import annotations

import pandas as pd

from fantasyhelper.players import SKATER_POSITIONS
from fantasyhelper.projections import GOALIE_CATEGORIES, SKATER_CATEGORIES


def _zscore(series: pd.Series, inverse: bool = False) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    std = values.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=series.index)
    score = (values - values.mean()) / std
    return -score if inverse else score


def _slot_counts(config: dict) -> dict[str, int]:
    team_count = config["league"]["team_count"]
    slots = config["roster"]["active_slots"]
    return {position: team_count * slots[position] for position in (*SKATER_POSITIONS, "G")}


def add_category_scores(players: pd.DataFrame) -> pd.DataFrame:
    result = players.copy()
    category_map = {"G": SKATER_CATEGORIES, "C": SKATER_CATEGORIES, "LW": SKATER_CATEGORIES,
                    "RW": SKATER_CATEGORIES, "D": SKATER_CATEGORIES, "GAA": GOALIE_CATEGORIES}
    is_goalie = result["eligible_positions"].map(lambda positions: "G" in positions)
    for category in SKATER_CATEGORIES:
        result[f"z_{category}"] = _zscore(result.loc[~is_goalie, category]).reindex(result.index)
    for category in GOALIE_CATEGORIES:
        result[f"z_{category}"] = _zscore(result.loc[is_goalie, category], inverse=category == "GAA").reindex(result.index)
    result["skater_value"] = result[[f"z_{category}" for category in SKATER_CATEGORIES]].sum(axis=1, min_count=1)
    result["goalie_value"] = result[[f"z_{category}" for category in GOALIE_CATEGORIES]].sum(axis=1, min_count=1)
    return result


def build_position_rankings(players: pd.DataFrame, config: dict) -> dict[str, pd.DataFrame]:
    """Return one rankable frame per fantasy position, retaining dual-eligibles."""
    counts = _slot_counts(config)
    rankings: dict[str, pd.DataFrame] = {}
    for position in (*SKATER_POSITIONS, "G"):
        subset = players[players["eligible_positions"].map(lambda positions: position in positions)].copy()
        if position == "G":
            minimum = config["ranking"]["goalie_min_games_played"]
            subset["limited_sample"] = pd.to_numeric(subset.get("GP"), errors="coerce").lt(minimum)
            subset = subset.sort_values(["limited_sample", "goalie_value"], ascending=[True, False])
            subset["overall_value"] = subset["goalie_value"]
        else:
            subset = subset.sort_values("skater_value", ascending=False)
            subset["overall_value"] = subset["skater_value"]
        # Schedule is deliberately a small tiebreaker, never the main valuation signal.
        schedule_bonus = (
            _zscore(subset.get("scheduled_games", pd.Series(0, index=subset.index))) * config["ranking"]["schedule_tiebreaker_weight"]
            + _zscore(subset.get("playoff_games", pd.Series(0, index=subset.index))) * config["ranking"]["playoff_tiebreaker_weight"]
            + _zscore(subset.get("rival_week_games", pd.Series(0, index=subset.index))) * config["ranking"]["rival_tiebreaker_weight"]
        )
        subset["schedule_bonus"] = schedule_bonus
        subset["overall_value"] = subset["overall_value"] + schedule_bonus
        subset = subset.sort_values("overall_value", ascending=False)
        subset["rank"] = range(1, len(subset) + 1)
        subset["draftable_cutoff"] = counts[position]
        subset["is_draftable"] = subset["rank"] <= counts[position]
        rankings[position] = subset
    return rankings


def build_category_rankings(players: pd.DataFrame) -> dict[str, pd.DataFrame]:
    rankings = {}
    for category in (*SKATER_CATEGORIES, *GOALIE_CATEGORIES):
        position = "G" if category in GOALIE_CATEGORIES else "Skater"
        subset = players[players["eligible_positions"].map(lambda values: "G" in values if position == "G" else "G" not in values)].copy()
        subset = subset.sort_values(f"z_{category}", ascending=False)
        subset["rank"] = range(1, len(subset) + 1)
        rankings[category] = subset
    return rankings
