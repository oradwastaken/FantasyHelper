import pandas as pd

from fantasyhelper.schedule import weekly_team_games


def test_weekly_team_games_counts_home_and_away_games():
    games = pd.DataFrame([
        {"date": "2026-10-05T00:00:00Z", "homeTeam": "TOR", "awayTeam": "MTL"},
        {"date": "2026-10-07T00:00:00Z", "homeTeam": "TOR", "awayTeam": "BOS"},
    ])
    result = weekly_team_games(games)
    assert result[result["team"] == "TOR"].iloc[0]["games"] == 2
