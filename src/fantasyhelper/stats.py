import json
from datetime import time
from pathlib import Path

import pandas as pd

from src.fantasyhelper.fantasy_stats import get_fantasy_rosters
from src.fantasyhelper.nhl_stats import (
    fetch_goalie_stats,
    fetch_skater_stats,
    fetch_teams,
    fetch_week,
    get_previous_monday,
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
        print("Fetching NHL roster data...")
    df_teams = fetch_teams()

    if verbose:
        print("Fetching NHL schedule data...")
    df_week = fetch_week(date)

    if verbose:
        print("Fetching NHL skater stats...")
    df_skaters = fetch_skater_stats()

    if verbose:
        print("Fetching NHL goalie stats...")
    df_goalies = fetch_goalie_stats()

    if verbose:
        print("Fetching fantasy rosters...")
    df_fantasy_rosters = get_fantasy_rosters()

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
