from datetime import date, datetime

from fantasyhelper.schedule_sync import _column_name, _daily_team_games, _matchup_dates


def test_matchup_dates_reads_the_week_date_rows():
    values = [["", "", ""] for _ in range(63)]
    values[2] = [2, datetime(2026, 10, 5), datetime(2026, 10, 11)]

    assert _matchup_dates(values, 2) == (2, date(2026, 10, 5), date(2026, 10, 11))


def test_daily_team_games_tracks_every_team_for_each_day():
    games = [
        {"startTimeUTC": "2026-10-22T01:00:00Z", "venueTimezone": "America/Denver", "awayTeam": {"abbrev": "TOR"}, "homeTeam": {"abbrev": "MTL"}},
        {"gameDate": "2026-10-22", "awayTeam": {"abbrev": "TOR"}, "homeTeam": {"abbrev": "BOS"}},
        {"gameDate": "2026-10-25", "awayTeam": {"abbrev": "MTL"}, "homeTeam": {"abbrev": "TOR"}},
    ]

    dates, games_by_team = _daily_team_games(games, ["TOR", "BOS", "MTL"], date(2026, 10, 21), date(2026, 10, 25))

    assert dates == [date(2026, 10, 21), date(2026, 10, 22), date(2026, 10, 23), date(2026, 10, 24), date(2026, 10, 25)]
    assert games_by_team == [[1, 1, 0, 0, 1], [0, 1, 0, 0, 0], [1, 0, 0, 0, 1]]


def test_column_name_supports_columns_beyond_z():
    assert _column_name(30) == "AD"
    assert _column_name(228) == "HT"
