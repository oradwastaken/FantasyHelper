import ast

import pandas as pd
from yahoofantasy import Context
from yahoofantasy import League

ctx = Context()


def get_league_ids(year: int = 2024):
    leagues = ctx.get_leagues("nhl", year)
    for league in leagues:
        print(league, league.id)


def get_fantasy_rosters(league_id: str = "453.l.21077"):
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

    return pd.DataFrame(records)
