"""High-level workflow that turns cached/raw data into reports."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from fantasyhelper.config import load_config
from fantasyhelper.players import attach_yahoo_eligibility, ownership_by_player
from fantasyhelper.projections import blend_projections
from fantasyhelper.rankings import add_category_scores, build_category_rankings, build_position_rankings
from fantasyhelper.schedule import attach_schedule_metrics, weekly_team_games
from fantasyhelper.stats import load_data
from fantasyhelper.team_strength import build_team_strength


def build_reports(config_path: str = "config.yaml", hdf_path: str = "nhl_data.h5", projections: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """Build all rank and team reports from the local data store."""
    config = load_config(config_path)
    data = load_data(hdf_path, verbose=False)
    skaters = data["df_skaters"].copy()
    goalies = data["df_goalies"].copy()
    players = pd.concat([skaters, goalies], ignore_index=True, sort=False)
    rosters = data.get("df_fantasy_rosters")
    players = attach_yahoo_eligibility(players, rosters)
    players = blend_projections(players, projections if projections is not None else pd.DataFrame(),
                                config["season"]["games_per_season"], config["ranking"]["projection_weight"],
                                config["ranking"]["historical_weight"])
    # Projection-only rows may not have been present in the NHL historical data.
    players = attach_yahoo_eligibility(players, rosters)
    players = attach_schedule_metrics(players, data.get("df_week"), config)
    players = add_category_scores(players)
    owners = ownership_by_player(rosters)
    players = players.merge(owners, on="name_key", how="left")
    reports: dict[str, pd.DataFrame] = {}
    for position, ranking in build_position_rankings(players, config).items():
        reports[f"Overall - {position}"] = ranking
    for category, ranking in build_category_rankings(players).items():
        reports[f"Category - {category}"] = ranking
    reports["Team Strength"] = build_team_strength(players, rosters, config)
    reports["Schedule"] = weekly_team_games(data.get("df_week", pd.DataFrame()))
    reports["Data Quality"] = players[[column for column in ("FullName", "team", "eligible_positions", "GP", "low_sample", "projection_available") if column in players]].copy()
    return reports


def write_reports(reports: dict[str, pd.DataFrame], output_directory: str | Path = "data/reports") -> None:
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    for title, frame in reports.items():
        frame.to_csv(directory / f"{title.replace('/', '-').replace(' ', '_')}.csv", index=False)
