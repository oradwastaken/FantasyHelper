import pandas as pd
import pytest

from fantasyhelper.api_calls import _coalesce_duplicate_columns
from fantasyhelper.season_stats import build_season_zscores, canonical_player_id


def test_build_season_zscores_uses_separate_player_pools_and_inverts_gaa():
    skaters = pd.DataFrame(
        {
            "playerId": [1, 2, 3], "gamesPlayed": [2, 2, 2], "goals": [1, 2, 3],
            "assists": [3, 2, 1], "plusMinus": [0, 0, 0], "penaltyMinutes": [0, 0, 0],
            "ppPoints": [0, 0, 0], "shPoints": [0, 0, 0], "shots": [0, 0, 0],
            "totalFaceoffWins": [0, 0, 0], "hits": [0, 0, 0], "blockedShots": [0, 0, 0],
        }
    ).set_index("playerId")
    goalies = pd.DataFrame(
        {
            "playerId": [4, 5], "gamesPlayed": [2, 2], "wins": [1, 2],
            "goalsAgainstAverage": [3.0, 2.0], "savePct": [.900, .910], "shutouts": [0, 1],
        }
    ).set_index("playerId")

    result = build_season_zscores(skaters, goalies)

    assert result.loc["1", "G"] == pytest.approx(-1.224744871)
    assert result.loc["3", "G"] == pytest.approx(1.224744871)
    assert result.loc["5", "GAA"] == pytest.approx(1.0)
    assert pd.isna(result.loc["4", "G"])
    assert pd.isna(result.loc["1", "W"])
    assert pd.isna(result.loc["1", "OFF"])


def test_build_season_zscores_standardizes_skater_per_game_and_goalie_per_start_rates():
    skaters = pd.DataFrame(
        {"playerId": [1, 2], "gamesPlayed": [1, 2], "goals": [1, 1]}
    ).set_index("playerId")
    goalies = pd.DataFrame(
        {"playerId": [3, 4], "gamesPlayed": [2, 2], "gamesStarted": [1, 2], "wins": [1, 1],
         "goalsAgainstAverage": [2.0, 2.0], "savePct": [.900, .900], "shutouts": [1, 1]}
    ).set_index("playerId")

    result = build_season_zscores(skaters, goalies)

    # One goal in one game is above one goal in two games; one win/shutout in
    # one start is above one in two starts.
    assert result.loc["1", "G"] > result.loc["2", "G"]
    assert result.loc["3", "W"] > result.loc["4", "W"]
    assert result.loc["3", "SO"] > result.loc["4", "SO"]


def test_canonical_player_id_handles_google_numeric_ids():
    assert canonical_player_id(8477492.0) == "8477492"
    assert canonical_player_id("8477492") == "8477492"
    assert canonical_player_id(None) == ""


def test_duplicate_nhl_report_fields_use_the_first_nonblank_value():
    reports = pd.concat(
        [
            pd.DataFrame({"goals": [None, 2], "gamesPlayed": [None, 1]}, index=[1, 2]),
            pd.DataFrame({"goals": [8, 3], "gamesPlayed": [10, 1]}, index=[1, 2]),
        ],
        axis=1,
    )

    result = _coalesce_duplicate_columns(reports)

    assert result.loc[1, "goals"] == 8
    assert result.loc[1, "gamesPlayed"] == 10
    assert result.loc[2, "goals"] == 2
