"""Build and publish current-season NHL category z-scores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from numbers import Integral

import pandas as pd

from fantasyhelper.api_calls import (
    fetch_goalie_stats,
    fetch_goalie_stats_for_dates,
    fetch_skater_stats,
    fetch_skater_stats_for_dates,
)
from fantasyhelper.projections import GOALIE_CATEGORIES, SKATER_CATEGORIES, canonicalize_stats
from fantasyhelper.rankings import _zscore
from fantasyhelper.sheets import get_gspread_client


SOURCE_HEADERS = ["NHL_PLAYER_ID", "GP", "OFF", "POG", *SKATER_CATEGORIES, *GOALIE_CATEGORIES]


@dataclass(frozen=True)
class SeasonStatsUpdate:
    """The result of one ``Stats (Season)`` refresh."""

    sheet_players: int
    season_players_with_nhl_stats: int
    recent_players_with_nhl_stats: int
    season_unmatched_nhl_players: int
    recent_unmatched_nhl_players: int


def canonical_player_id(value: object) -> str:
    """Return a stable string representation for a Google/NHL player ID."""
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, Integral):
        return str(value)
    text = str(value).strip()
    # Sheets can render an integer ID as ``8477492.0`` when it is read as an
    # unformatted number.
    return text[:-2] if text.endswith(".0") and text[:-2].isdigit() else text


def _with_ids(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.index = result.index.map(canonical_player_id)
    result = result.loc[result.index != ""]
    return result.loc[~result.index.duplicated(keep="first")]


def _skater_frame(raw_stats: pd.DataFrame) -> pd.DataFrame:
    """Select the NHL fields used by the fantasy sheet without names/teams."""
    raw = _with_ids(raw_stats)
    fields = {
        "gamesPlayed": "GP", "goals": "G", "assists": "A", "plusMinus": "+/-",
        "penaltyMinutes": "PIM", "ppPoints": "PPP", "shPoints": "SHP",
        "shots": "SOG", "totalFaceoffWins": "FOW", "hits": "HIT", "blockedShots": "BLK",
    }
    return raw.reindex(columns=fields).rename(columns=fields)


def _goalie_frame(raw_stats: pd.DataFrame) -> pd.DataFrame:
    raw = _with_ids(raw_stats)
    fields = {
        "gamesPlayed": "GP", "gamesStarted": "GS", "wins": "W", "goalsAgainstAverage": "GAA",
        "savePct": "SV%", "shutouts": "SO",
    }
    return raw.reindex(columns=fields).rename(columns=fields)


def build_season_zscores(skater_stats: pd.DataFrame, goalie_stats: pd.DataFrame) -> pd.DataFrame:
    """Return NHL-ID keyed season values in exactly the source-tab columns.

    Skater counting categories are converted to per-game rates before being
    standardized among all skaters. Goalie wins and shutouts are converted to
    per-start rates; GAA and save percentage are already rates. A lower GAA is
    better, so its score is reversed. This uses the same population-standard-
    deviation convention as the project's ranking calculations.
    """
    skaters = canonicalize_stats(_skater_frame(skater_stats))
    goalies = canonicalize_stats(_goalie_frame(goalie_stats))

    skater_gp = pd.to_numeric(skaters["GP"], errors="coerce").replace(0, pd.NA)
    goalie_gs = pd.to_numeric(goalies["GS"], errors="coerce").replace(0, pd.NA)
    for category in SKATER_CATEGORIES:
        skaters[category] = pd.to_numeric(skaters[category], errors="coerce").div(skater_gp)
    for category in ("W", "SO"):
        goalies[category] = pd.to_numeric(goalies[category], errors="coerce").div(goalie_gs)

    result = pd.concat([skaters[["GP", *SKATER_CATEGORIES]], goalies[["GP", *GOALIE_CATEGORIES]]], axis=0)
    result = result.loc[~result.index.duplicated(keep="first")]
    for category in SKATER_CATEGORIES:
        result[category] = _zscore(result.loc[skaters.index, category]).reindex(result.index)
    for category in GOALIE_CATEGORIES:
        result[category] = _zscore(result.loc[goalies.index, category], inverse=category == "GAA").reindex(result.index)
    # OFF and POG are projection-only measures; the NHL public statistics API
    # does not supply equivalents, so source-tab cells intentionally stay blank.
    result["OFF"] = pd.NA
    result["POG"] = pd.NA
    return result.reindex(columns=SOURCE_HEADERS[1:])


def _worksheet_ids(worksheet, first_row: int, last_row: int, column: str) -> list[str]:
    row_count = last_row - first_row + 1
    values = worksheet.get(f"{column}{first_row}:{column}{last_row}", value_render_option="UNFORMATTED_VALUE")
    ids = [canonical_player_id(row[0]) if row else "" for row in values]
    return (ids + [""] * row_count)[:row_count]


def _assert_source_layout(worksheet, projection_worksheet, settings: dict) -> list[str]:
    first_row = int(settings["first_data_row"])
    last_row = int(settings["last_data_row"])
    id_column = settings["player_id_column"]
    header_row = int(settings["header_row"])
    target_headers = worksheet.row_values(header_row)[:len(SOURCE_HEADERS)]
    projection_headers = projection_worksheet.row_values(header_row)[:len(SOURCE_HEADERS)]
    if target_headers != SOURCE_HEADERS or projection_headers != SOURCE_HEADERS:
        raise ValueError(f"{worksheet.title} and {projection_worksheet.title} must have the expected NHL source-tab headers")
    target_ids = _worksheet_ids(worksheet, first_row, last_row, id_column)
    projection_ids = _worksheet_ids(projection_worksheet, first_row, last_row, id_column)
    if not all(target_ids) or len(set(target_ids)) != len(target_ids):
        raise ValueError(f"{worksheet.title} has missing or duplicate NHL_PLAYER_ID values")
    if set(target_ids) != set(projection_ids) or len(target_ids) != len(projection_ids):
        raise ValueError(f"{worksheet.title} NHL_PLAYER_ID values must match {projection_worksheet.title} exactly")
    return target_ids


def _write_stats(worksheet, ids: list[str], values: pd.DataFrame, settings: dict) -> tuple[int, int]:
    """Write one calculated stats frame, retaining every source-tab row."""
    rows: list[list[object]] = []
    matched = 0
    for player_id in ids:
        if player_id in values.index:
            matched += 1
            row = values.loc[player_id].tolist()
            rows.append(["" if pd.isna(value) else float(value) for value in row])
        else:
            rows.append([""] * (len(SOURCE_HEADERS) - 1))
    first_row = int(settings["first_data_row"])
    last_row = int(settings["last_data_row"])
    worksheet.update(rows, f"B{first_row}:R{last_row}", value_input_option="RAW")
    return matched, len(values.index.difference(ids))


def update_season_stats(config: dict, today: date | None = None) -> SeasonStatsUpdate:
    """Update season-to-date and trailing-14-day NHL category z-score tabs."""
    settings = config["season_stats_sync"]
    google = config["google_sheets"]
    if not google.get("spreadsheet_id"):
        raise ValueError("google_sheets.spreadsheet_id is required for update-stats")

    client = get_gspread_client(google["credentials_path"], google["token_path"])
    spreadsheet = client.open_by_key(google["spreadsheet_id"])
    worksheet = spreadsheet.worksheet(settings["worksheet"])
    recent_worksheet = spreadsheet.worksheet(settings["last_two_weeks_worksheet"])
    projection_worksheet = spreadsheet.worksheet(settings["projections_worksheet"])
    ids = _assert_source_layout(worksheet, projection_worksheet, settings)
    recent_ids = _assert_source_layout(recent_worksheet, projection_worksheet, settings)

    print(f"Fetching NHL {config['season']['target']} skater stats...")
    skaters = fetch_skater_stats(config["season"]["target"])
    print(f"Fetching NHL {config['season']['target']} goalie stats...")
    goalies = fetch_goalie_stats(config["season"]["target"])
    season_values = build_season_zscores(skaters, goalies)
    season_matched, season_unmatched = _write_stats(worksheet, ids, season_values, settings)

    end_date = today or date.today()
    start_date = end_date - timedelta(days=13)
    print(f"Fetching NHL stats from {start_date.isoformat()} through {end_date.isoformat()}...")
    recent_skaters = fetch_skater_stats_for_dates(config["season"]["target"], start_date.isoformat(), end_date.isoformat())
    recent_goalies = fetch_goalie_stats_for_dates(config["season"]["target"], start_date.isoformat(), end_date.isoformat())
    recent_values = build_season_zscores(recent_skaters, recent_goalies)
    recent_matched, recent_unmatched = _write_stats(recent_worksheet, recent_ids, recent_values, settings)
    return SeasonStatsUpdate(len(ids), season_matched, recent_matched, season_unmatched, recent_unmatched)
