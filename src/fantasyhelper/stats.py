from nhlpy import NHLClient
import pandas as pd

client = NHLClient()


def clean_name(ntype, name):
    """
    Clean the name of the player or team
    """
    return name[ntype]["default"]


def get_teams() -> pd.DataFrame:
    teams = client.teams.teams()
    df = pd.DataFrame(teams)
    df = df[["name", "abbr", "franchise_id"]].sort_values("name").reset_index(drop=True)
    df.set_index("franchise_id", inplace=True)
    return df


def get_roster(team_abbr, season="20242025") -> pd.DataFrame:
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
    df.set_index("id", inplace=True)
    return df


def get_player_stats(season="20242025"):
    player_stats_dfs = []
    i = 1
    while i > 0:
        stats = client.stats.skater_stats_summary(
            start_season=season,
            end_season=season,
            start=100 * (i - 1) + 1,
            limit=100 * i,
        )
        if stats == []:
            i = -1
        else:
            player_stats_dfs.append(pd.DataFrame(stats))
            i += 1

    df_all_stats = pd.concat(
        player_stats_dfs,
        ignore_index=True,
    )

    # If player has played for multiple teams, only keep the most recent one:
    df_all_stats["teamAbbrevs"] = df_all_stats["teamAbbrevs"].str.split(",").str[-1]

    df_all_stats = df_all_stats[
        [
            "playerId",
            "skaterFullName",
            "teamAbbrevs",
            "positionCode",
            "gamesPlayed",
            "goals",
            "assists",
            "ppPoints",
            "shPoints",
            "gameWinningGoals",
            "shots",
        ]
    ]

    df_all_stats.rename(
        columns={
            "skaterFullName": "FullName",
            "teamAbbrevs": "team",
            "positionCode": "position",
            "gamesPlayed": "GP",
            "goals": "G",
            "assists": "A",
            "ppPoints": "PPP",
            "shPoints": "SHP",
            "shots": "SOG",
            "gameWinningGoals": "GWP",
        },
        inplace=True,
    )

    df_all_stats.set_index("playerId", inplace=True)

    return df_all_stats


def get_week(date: str = "2025-01-20"):
    """example date: "2025-01-20"""
    week_df = pd.DataFrame(client.schedule.weekly_schedule(date))
    gameWeek = pd.json_normalize(week_df["gameWeek"])
    games = pd.json_normalize(gameWeek["games"])

    records = []
    for row in games.itertuples(index=False):
        for item in row:
            if item:  # skip "None"
                records.append(item)

    week_df = pd.DataFrame(records)

    week_df = week_df[["id", "startTimeUTC", "homeTeam.abbrev", "awayTeam.abbrev"]]
    week_df.rename(
        columns={
            "id": "gameId",
            "startTimeUTC": "date",
            "homeTeam.abbrev": "homeTeam",
            "awayTeam.abbrev": "awayTeam",
        },
        inplace=True,
    )
    week_df.set_index("gameId", inplace=True)

    return week_df
