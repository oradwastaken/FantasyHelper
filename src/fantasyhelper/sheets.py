"""OAuth-backed Google Sheets publishing."""

from __future__ import annotations

from pathlib import Path

import gspread
import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from fantasyhelper.rosters import RosterUpdate, build_roster_update, fetch_local_rosters

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]


def get_gspread_client(credentials_path: str, token_path: str) -> gspread.Client:
    """Authenticate through the local browser on first use and refresh thereafter."""
    credentials_file = Path(credentials_path)
    token_file = Path(token_path)
    credentials = Credentials.from_authorized_user_file(token_file, SCOPES) if token_file.exists() else None
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials or not credentials.valid:
        if not credentials_file.exists():
            raise FileNotFoundError(f"Google OAuth client file not found: {credentials_file}")
        credentials = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES).run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    return gspread.authorize(credentials)


def _write_frame(spreadsheet: gspread.Spreadsheet, title: str, frame: pd.DataFrame) -> None:
    try:
        worksheet = spreadsheet.worksheet(title)
        worksheet.clear()
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=title, rows=max(100, len(frame) + 1), cols=max(10, len(frame.columns)))
    safe = frame.copy().fillna("")
    for column in safe.select_dtypes(include=["datetime", "datetimetz"]).columns:
        safe[column] = safe[column].astype(str)
    values = [safe.columns.tolist(), *safe.astype(object).values.tolist()]
    worksheet.update(values, "A1")
    worksheet.freeze(rows=1)
    worksheet.set_basic_filter()


def publish_reports(reports: dict[str, pd.DataFrame], config: dict) -> str:
    """Create or update the configured spreadsheet and return its URL."""
    settings = config["google_sheets"]
    client = get_gspread_client(settings["credentials_path"], settings["token_path"])
    spreadsheet = client.open_by_key(settings["spreadsheet_id"]) if settings.get("spreadsheet_id") else client.create(settings["spreadsheet_title"])
    for title, frame in reports.items():
        _write_frame(spreadsheet, title[:100], frame)
    return spreadsheet.url


def _apply_rosters(config: dict, yahoo_rosters: pd.DataFrame) -> RosterUpdate:
    """Apply a normalized Yahoo roster frame to the configured worksheet."""
    settings = config["google_sheets"]
    roster = config["roster_sync"]
    spreadsheet_id = settings.get("spreadsheet_id")
    if not spreadsheet_id:
        raise ValueError("google_sheets.spreadsheet_id is required for update-roster")

    client = get_gspread_client(settings["credentials_path"], settings["token_path"])
    worksheet = client.open_by_key(spreadsheet_id).worksheet(roster["worksheet"])
    first_row = int(roster["first_data_row"])
    last_row = int(roster["last_data_row"])
    player_column = roster["player_name_column"]
    owner_column = roster["owner_column"]
    row_count = last_row - first_row + 1
    sheet_names = [row[0] if row else "" for row in worksheet.get(f"{player_column}{first_row}:{player_column}{last_row}")]
    # gspread omits trailing empty rows from ``get``; retain the full target range
    # so stale owner values are also reset to Undrafted.
    sheet_names.extend([""] * (row_count - len(sheet_names)))
    result = build_roster_update(sheet_names, yahoo_rosters, roster.get("manager_aliases"))
    worksheet.update(result.values, f"{owner_column}{first_row}:{owner_column}{last_row}")
    return result


def update_rosters(config: dict) -> RosterUpdate:
    """Fetch Yahoo API rosters and write ownership into one sheet column."""
    # Import lazily: report publishing should not require Yahoo credentials.
    from fantasyhelper.api_calls import fetch_fantasy_rosters

    return _apply_rosters(config, fetch_fantasy_rosters(config["league"]["yahoo_league_id"]))


def update_rosters_from_local_html(config: dict) -> RosterUpdate:
    """Update ownership from the most recently saved Yahoo roster-page HTML."""
    source = config["roster_sync"]["local_html_glob"]
    return _apply_rosters(config, fetch_local_rosters(source))
