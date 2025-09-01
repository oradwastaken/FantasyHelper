from datetime import date, timedelta

import pandas as pd
from nhlpy.api.query.builder import QueryBuilder, QueryContext
from nhlpy.api.query.filters.game_type import GameTypeQuery
from nhlpy.api.query.filters.season import SeasonQuery
from nhlpy.nhl_client import NHLClient

from src.fantasyhelper.types import teams_enum

client = NHLClient()


def clean_name(ntype, name):
    """
    Clean the name of the player or team
    """
    return name[ntype]["default"]


def get_previous_monday():
    today = date.today()
    days_since_monday = today.weekday() % 7
    days_to_subtract = 7 if days_since_monday == 0 else days_since_monday
    previous_monday = today - timedelta(days=days_to_subtract)
    return previous_monday.strftime("%Y-%m-%d")


def fetch_teams() -> pd.DataFrame:
    teams = client.teams.teams()
    df = pd.DataFrame(teams)
    df = df[["name", "abbr", "franchise_id"]].sort_values("name").reset_index(drop=True)
    df.set_index("franchise_id", inplace=True)
    df["abbr"] = pd.Categorical(df["abbr"], categories=teams_enum)
    return df


def fetch_roster(team_abbr, season="20242025") -> pd.DataFrame:
    players = client.teams.team_roster(team_abbr=team_abbr, season=season)
    for p in players["forwards"] + players["defensemen"] + players["goalies"]:
        p["team"] = team_abbr
        p["firstName"] = clean_name("firstName", p)
        p["lastName"] = clean_name("lastName", p)
    forwards, defense, goalies = (
        players["forwards"],
        players["defensemen"],
        players["goalies"],
    )

    df = pd.concat(
        [pd.DataFrame(forwards), pd.DataFrame(defense), pd.DataFrame(goalies)],
        ignore_index=True,
    )

    df = df[["id", "firstName", "lastName", "positionCode", "team"]]
    df["team"] = pd.Categorical(df["team"], categories=teams_enum)
    df.set_index("id", inplace=True)
    return df


def fetch_goalie_stats(season="20242025"):
    i = 1
    data_list = []
    while i > 0:
        response = client.stats.goalie_stats_summary(
            stats_type="summary",
            start_season=season,
            game_type_id=2,
            end_season=season,
            start=100 * (i - 1) + 1,
            limit=100 * i,
        )
        data = pd.DataFrame(response)
        if data.empty:
            i = -1
        else:
            data_list.append(data)
            i += 1

    df_stats = pd.concat(data_list, ignore_index=False)
    df_stats.set_index("playerId", inplace=True)

    df_stats["currentTeamAbbrev"] = df_stats["teamAbbrevs"].apply(
        lambda x: x.split(",")[-1].strip()
    )

    df_stats["position"] = "G"

    df_stats = df_stats[
        [
            "lastName",
            "goalieFullName",
            "currentTeamAbbrev",
            "position",
            "gamesPlayed",
            "wins",
            "goalsAgainstAverage",
            "savePct",
            "shutouts",
        ]
    ]

    df_stats.rename(
        columns={
            "goalieFullName": "FullName",
            "lastName": "LastName",
            "currentTeamAbbrev": "team",
            "gamesPlayed": "GP",
            "wins": "W",
            "goalsAgainstAverage": "GAA",
            "savePct": "SV%",
            "shutouts": "SHO",
        },
        inplace=True,
    )

    df_stats = df_stats.dropna()
    df_stats["team"] = pd.Categorical(df_stats["team"], categories=teams_enum)

    return df_stats


def fetch_skater_stats(season="20242025"):
    filters = [
        GameTypeQuery(game_type="2"),
        SeasonQuery(season_start=season, season_end=season),
    ]

    query_builder = QueryBuilder()
    query_context: QueryContext = query_builder.build(filters=filters)

    report_types = ["summary", "realtime", "bios", "faceoffwins"]
    df_list = []
    for report_type in report_types:
        i = 1
        data_list = []
        while i > 0:
            response = client.stats.skater_stats_with_query_context(
                report_type=report_type,
                query_context=query_context,
                start=100 * (i - 1) + 1,
                limit=100 * i,
            )
            data = pd.json_normalize(pd.DataFrame(response)["data"])
            if data.empty:
                i = -1
            else:
                data_list.append(data)
                i += 1

        df = pd.concat(data_list, ignore_index=True)
        df.set_index("playerId", inplace=True)
        df_list.append(df)

    df_stats = pd.concat(df_list, axis=1, ignore_index=False)
    df_stats = df_stats.loc[:, ~df_stats.columns.duplicated()].copy()

    df_stats = df_stats[
        [
            "lastName",
            "skaterFullName",
            "currentTeamAbbrev",
            "currentTeamName",
            "positionCode",
            "gamesPlayed",
            "goals",
            "assists",
            "ppPoints",
            "shPoints",
            "gameWinningGoals",
            "shots",
            "plusMinus",
            "penaltyMinutes",
            "totalFaceoffWins",
            "hits",
        ]
    ]

    df_stats.rename(
        columns={
            "skaterFullName": "FullName",
            "lastName": "LastName",
            "currentTeamAbbrev": "team",
            "currentTeamName": "FullTeam",
            "positionCode": "position",
            "gamesPlayed": "GP",
            "goals": "G",
            "assists": "A",
            "ppPoints": "PPP",
            "shPoints": "SHP",
            "shots": "SOG",
            "plusMinus": "+/-",
            "penaltyMinutes": "PIM",
            "gameWinningGoals": "GWG",
            "totalFaceoffWins": "FW",
            "hits": "HIT",
            "blockedShots": "BLK",
        },
        inplace=True,
    )

    df_stats = df_stats.dropna()
    df_stats["team"] = pd.Categorical(df_stats["team"], categories=teams_enum)
    return df_stats


def fetch_week(date: str = "2025-01-20"):
    """example date: "2025-01-20"""
    df_week = pd.DataFrame(client.schedule.weekly_schedule(date))
    gameWeek = pd.json_normalize(df_week["gameWeek"])
    games = pd.json_normalize(gameWeek["games"])

    records = []
    for row in games.itertuples(index=False):
        for item in row:
            if item:  # skip "None"
                records.append(item)

    df_week = pd.DataFrame(records)

    df_week = df_week[["id", "startTimeUTC", "homeTeam.abbrev", "awayTeam.abbrev"]]
    df_week.rename(
        columns={
            "id": "gameId",
            "startTimeUTC": "date",
            "homeTeam.abbrev": "homeTeam",
            "awayTeam.abbrev": "awayTeam",
        },
        inplace=True,
    )
    df_week.set_index("gameId", inplace=True)
    df_week["homeTeam"] = pd.Categorical(df_week["homeTeam"], categories=teams_enum)
    df_week["awayTeam"] = pd.Categorical(df_week["awayTeam"], categories=teams_enum)
    return df_week
