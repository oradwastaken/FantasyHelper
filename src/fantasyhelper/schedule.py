"""Schedule quality calculations."""

from __future__ import annotations

import pandas as pd


def weekly_team_games(games: pd.DataFrame) -> pd.DataFrame:
    """Convert NHL game rows into per-team Monday-week game counts."""
    if games.empty:
        return pd.DataFrame(columns=["week_start", "team", "games"])
    frame = games.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    frame["week_start"] = (frame["date"].dt.normalize() - pd.to_timedelta(frame["date"].dt.weekday, unit="D")).dt.tz_localize(None)
    home = frame[["week_start", "homeTeam"]].rename(columns={"homeTeam": "team"})
    away = frame[["week_start", "awayTeam"]].rename(columns={"awayTeam": "team"})
    return pd.concat([home, away]).groupby(["week_start", "team"], as_index=False, observed=True).size().rename(columns={"size": "games"})


def attach_schedule_metrics(players: pd.DataFrame, games: pd.DataFrame | None, config: dict) -> pd.DataFrame:
    result = players.copy()
    if games is None or games.empty or "team" not in result:
        result["scheduled_games"] = 0
        result["playoff_games"] = 0
        result["rival_week_games"] = 0
        return result
    weekly = weekly_team_games(games)
    configured_playoffs = {pd.Timestamp(value) for value in config["schedule"].get("playoff_weeks", [])}
    configured_rival = {pd.Timestamp(value) for value in config["schedule"].get("rival_matchup_weeks", [])}
    totals = weekly.groupby("team", as_index=False, observed=True)["games"].sum().rename(columns={"games": "scheduled_games"})
    playoff = weekly[weekly["week_start"].isin(configured_playoffs)].groupby("team", as_index=False, observed=True)["games"].sum().rename(columns={"games": "playoff_games"})
    rival = weekly[weekly["week_start"].isin(configured_rival)].groupby("team", as_index=False, observed=True)["games"].sum().rename(columns={"games": "rival_week_games"})
    result = result.merge(totals, on="team", how="left").merge(playoff, on="team", how="left").merge(rival, on="team", how="left")
    return result.fillna({"scheduled_games": 0, "playoff_games": 0, "rival_week_games": 0})
