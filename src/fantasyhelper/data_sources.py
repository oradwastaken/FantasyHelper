"""Cached external data sources and projection-sheet ingestion."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from fantasyhelper.sheets import get_gspread_client


def cached_frame(name: str, cache_directory: str | Path, fetch: Callable[[], pd.DataFrame], refresh: bool = False) -> pd.DataFrame:
    """Return a date-stamped DataFrame cache, fetching only when needed."""
    directory = Path(cache_directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = directory / f"{name}-{stamp}.pkl"
    if path.exists() and not refresh:
        return pd.read_pickle(path)
    frame = fetch()
    frame.to_pickle(path)
    return frame


def load_projection_sheet(url: str, worksheet_name: str, credentials_path: str, token_path: str) -> pd.DataFrame:
    """Load the configured Google projections worksheet as a DataFrame."""
    if not url:
        return pd.DataFrame()
    client = get_gspread_client(credentials_path, token_path)
    worksheet = client.open_by_url(url).worksheet(worksheet_name)
    return pd.DataFrame(worksheet.get_all_records())
