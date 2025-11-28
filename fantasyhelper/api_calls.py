import ast
from itertools import count

import pandas as pd
from nhlpy.api.query.builder import QueryBuilder, QueryContext
from nhlpy.api.query.filters.game_type import GameTypeQuery
from nhlpy.api.query.filters.season import SeasonQuery
from nhlpy.nhl_client import NHLClient
from yahoofantasy import Context, League

from fantasyhelper.dates import get_current_season

client = NHLClient()
ctx = Context()

CURRENT_SEASON = get_current_season()


def fetch_teams() -> pd.DataFrame:
    teams = client.teams.teams()
    return pd.DataFrame(teams)


def fetch_week(date: str = "2025-01-20") -> pd.DataFrame:
    df_week = client.schedule.weekly_schedule(date)
    return pd.DataFrame(df_week)


def fetch_skater_stats(season: str = CURRENT_SEASON) -> pd.DataFrame:
    filters = [
        GameTypeQuery(game_type="2"),  # 2 = regular season
        SeasonQuery(season_start=season, season_end=season),
    ]

    query_builder = QueryBuilder()
    query_context: QueryContext = query_builder.build(filters=filters)

    report_types = ["summary", "realtime", "bios", "faceoffwins"]
    df_list = []
    for report_type in report_types:
        data_list = []
        for page in count(start=1):
            response = client.stats.skater_stats_with_query_context(
                report_type=report_type,
                query_context=query_context,
                start=100 * (page - 1) + 1,
                limit=100 * page,
            )
            data = pd.json_normalize(pd.DataFrame(response)["data"])

            if data.empty:
                break

            data_list.append(data)

        df = pd.concat(data_list, ignore_index=True)
        df.set_index("playerId", inplace=True)
        df_list.append(df)

    df_stats = pd.concat(df_list, axis=1, ignore_index=False)
    df_stats = df_stats.loc[:, ~df_stats.columns.duplicated()].copy()
    return df_stats


def fetch_goalie_stats(season: str = CURRENT_SEASON) -> pd.DataFrame:
    data_list = []
    for page in count(start=1):
        response = client.stats.goalie_stats_summary(
            stats_type="summary",
            start_season=season,
            game_type_id=2,
            end_season=season,
            start=100 * (page - 1) + 1,
            limit=100 * page,
        )
        data = pd.DataFrame(response)
        if data.empty:
            break

        data_list.append(data)

    df_stats = pd.concat(data_list, ignore_index=False)
    df_stats.set_index("playerId", inplace=True)
    return df_stats


def fetch_fantasy_rosters(league_id: str = "453.l.21077"):
    league = League(ctx, league_id)

    records = []
    for fantasy_team in league.teams():
        for player in fantasy_team.players():
            pos_dict = ast.literal_eval(str(player.eligible_positions))
            records.append(
                {
                    "fantasy_team": fantasy_team.name,
                    "manager": fantasy_team.manager.nickname,
                    "fantasy_team_id": fantasy_team.id,
                    "FullName": player.name.full,
                    "lastName": player.name.last,
                    "team": player.editorial_team_abbr,
                    "player_id_yahoo": player.player_id,
                    "position": pos_dict["position"],
                }
            )

    rosters = pd.DataFrame(records)
    return rosters


def fetch_league_ids(year: int = CURRENT_SEASON[:4]):
    leagues = ctx.get_leagues("nhl", year)
    for league in leagues:
        print(league, league.id)


def fetch_roster(team_abbr, season=CURRENT_SEASON) -> pd.DataFrame:
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
    return df


def clean_name(ntype, name):
    """
    Clean the name of the player or team
    """
    return name[ntype]["default"]
