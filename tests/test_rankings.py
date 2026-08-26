import pandas as pd

from fantasyhelper.config import load_config
from fantasyhelper.players import attach_yahoo_eligibility
from fantasyhelper.projections import blend_projections, prorate_historical
from fantasyhelper.rankings import add_category_scores, build_position_rankings


def _skater(name, position, goals):
    return {"FullName": name, "position": position, "GP": 42, "G": goals, "A": 20,
            "+/-": 5, "PIM": 10, "PPP": 3, "SHP": 0, "SOG": 80, "FW": 50,
            "HIT": 10, "BLK": 5}


def test_historical_counting_stats_are_prorated_to_84_games():
    result = prorate_historical(pd.DataFrame([_skater("Example", "C", 21)]), 84)
    assert result.loc[0, "historical_G"] == 42
    assert result.loc[0, "historical_GAA"] is pd.NA or pd.isna(result.loc[0, "historical_GAA"])


def test_dual_eligible_player_appears_in_each_position_ranking():
    players = pd.DataFrame([_skater("Dual", "C", 30), _skater("Wing", "LW", 20), _skater("Centre", "C", 10)])
    rosters = pd.DataFrame([{"FullName": "Dual", "position": ["C", "LW", "Util"]}])
    players = attach_yahoo_eligibility(players, rosters)
    blended = blend_projections(players, pd.DataFrame(), 84, 0.7, 0.3)
    rankings = build_position_rankings(add_category_scores(blended), load_config())
    assert "Dual" in rankings["C"]["FullName"].tolist()
    assert "Dual" in rankings["LW"]["FullName"].tolist()


def test_low_sample_goalie_is_flagged():
    goalie = pd.DataFrame([{"FullName": "Goalie", "position": "G", "GP": 10, "W": 4, "GAA": 2.0, "SV%": 0.93, "SHO": 1}])
    goalie = attach_yahoo_eligibility(goalie, pd.DataFrame())
    goalie = add_category_scores(blend_projections(goalie, pd.DataFrame(), 84, 0.7, 0.3))
    ranking = build_position_rankings(goalie, load_config())["G"]
    assert bool(ranking.iloc[0]["limited_sample"])
