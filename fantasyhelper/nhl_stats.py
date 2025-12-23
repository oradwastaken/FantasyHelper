import pandas as pd

from fantasyhelper.types import teams_enum


def process_teams(df: pd.DataFrame) -> pd.DataFrame:
    df = df[["name", "abbr", "franchise_id"]].sort_values("name").reset_index(drop=True)
    df.set_index("franchise_id", inplace=True)
    df["abbr"] = pd.Categorical(df["abbr"], categories=teams_enum)
    return df


def process_roster(df: pd.DataFrame) -> pd.DataFrame:
    df = df[["id", "firstName", "lastName", "positionCode", "team"]]
    df["team"] = pd.Categorical(df["team"], categories=teams_enum)
    df.set_index("id", inplace=True)
    return df


def process_goalies(df_stats: pd.DataFrame) -> pd.DataFrame:
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

    # Remove umlaut and other symbols:
    df_stats["FullName"] = (
        df_stats["FullName"]
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("ascii")
    )

    return df_stats


def process_skaters(df_stats: pd.DataFrame) -> pd.DataFrame:
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

    # Remove umlaut and other symbols:
    df_stats["FullName"] = (
        df_stats["FullName"]
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("ascii")
    )
    return df_stats


def process_week(df_week: pd.DataFrame) -> pd.DataFrame:
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
