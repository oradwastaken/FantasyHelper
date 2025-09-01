import pandas as pd

from src.fantasyhelper.types import teams_enum


def process_fantasy_rosters(df_rosters: pd.DataFrame) -> pd.DataFrame:
    df_rosters["team"] = pd.Categorical(df_rosters["team"], categories=teams_enum)
    return df_rosters
