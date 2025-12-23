import json
from datetime import time
from pathlib import Path

import pandas as pd

from fantasyhelper.api_calls import (
    fetch_fantasy_rosters,
    fetch_goalie_stats,
    fetch_skater_stats,
    fetch_teams,
    fetch_week,
)
from fantasyhelper.dates import get_previous_monday
from fantasyhelper.fantasy_stats import process_fantasy_rosters
from fantasyhelper.nhl_stats import (
    process_goalies,
    process_skaters,
    process_teams,
    process_week,
)


def update_data(hdf_path="nhl_data.h5", date: str = None, verbose=True):
    """
    Downloads/fetches data and updates the HDF5 store.

    Parameters:
        verbose (bool): If True, print status messages.
    """

    if date is None:
        date = get_previous_monday()

    if verbose:
        print(f"Fetching NHL roster data (date = {date})...")
    df_teams_raw = fetch_teams()
    df_teams = process_teams(df_teams_raw)

    if verbose:
        print("Fetching NHL schedule data...")
    df_week_raw = fetch_week(date)
    df_week = process_week(df_week_raw)

    if verbose:
        print("Fetching NHL skater stats...")
    df_skaters_raw = fetch_skater_stats()
    df_skaters = process_skaters(df_skaters_raw)

    if verbose:
        print("Fetching NHL goalie stats...")
    df_goalies_raw = fetch_goalie_stats()
    df_goalies = process_goalies(df_goalies_raw)

    if verbose:
        print("Fetching fantasy rosters...")
    df_fantasy_rosters_raw = fetch_fantasy_rosters()
    df_fantasy_rosters = process_fantasy_rosters(df_fantasy_rosters_raw)

    if verbose:
        print("Saving to HDF5...")

    # Before saving, let's save all lists as strings:
    df_fantasy_rosters["position"] = df_fantasy_rosters["position"].apply(json.dumps)

    with pd.HDFStore(hdf_path, mode="w") as store:
        store.put("df_teams", df_teams, format="table")
        store.put("df_week", df_week, format="table")
        store.put("df_skaters", df_skaters, format="table")
        store.put("df_goalies", df_goalies, format="table")
        store.put("df_fantasy_rosters", df_fantasy_rosters, format="table")
        store.get_storer("df_teams").attrs.metadata = {
            "source": "fetch_teams",
            "timestamp": time(),
        }
        store.get_storer("df_week").attrs.metadata = {
            "source": "fetch_week",
            "timestamp": time(),
        }
        store.get_storer("df_skaters").attrs.metadata = {
            "source": "fetch_skater_stats",
            "timestamp": time(),
        }
        store.get_storer("df_goalies").attrs.metadata = {
            "source": "fetch_goalie_stats",
            "timestamp": time(),
        }
        store.get_storer("df_fantasy_rosters").attrs.metadata = {
            "source": "get_fantasy_rosters",
            "timestamp": time(),
        }

    if verbose:
        print("Update complete.")


def load_data(hdf_path="nhl_data.h5", verbose=True):
    """
    Loads DataFrames from HDF5 store into a dictionary.

    Returns:
        dict of DataFrames
    """
    if not Path(hdf_path).exists():
        raise FileNotFoundError(
            f"HDF5 file not found at {hdf_path}. Run update_data() first."
        )

    if verbose:
        print("Loading data from HDF5...")

    with pd.HDFStore(hdf_path, mode="r") as store:
        data = {key.strip("/"): store[key] for key in store.keys()}

    # Let's unspool the stringed-lists back into list[str]
    data["df_fantasy_rosters"]["position"] = data["df_fantasy_rosters"][
        "position"
    ].apply(json.loads)

    if verbose:
        print("Loaded:", ", ".join(data.keys()))

    return data
