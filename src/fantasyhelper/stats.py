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
