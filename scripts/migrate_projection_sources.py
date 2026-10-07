"""One-time migration of Player Values projection inputs into source tabs.

Run a dry run first:
    uv run python scripts/migrate_projection_sources.py

Then apply the migration:
    uv run python scripts/migrate_projection_sources.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# This repository uses a src/ layout but its default uv environment does not
# install the project package. Keep this one-off script runnable as documented.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fantasyhelper.config import load_config
from fantasyhelper.sheets import get_gspread_client


SOURCE_SHEET = "Player Values - Cats"
PROJECTIONS_SHEET = "Projections"
SEASON_SHEET = "Stats (Season)"
RECENT_SHEET = "Stats (Last 2 weeks)"
SOURCE_RANGE = "L1:AB783"
DATA_RANGE = "L3:AB783"
HEADER_RANGE = "L1:AB2"

WEIGHTED_FORMULA = """=ARRAYFORMULA(IF(
  (Projections!L3:AB783=\"\")*('Stats (Season)'!L3:AB783=\"\")*('Stats (Last 2 weeks)'!L3:AB783=\"\"),
  \"\",
  Projections!L3:AB783*'Roster Comparison'!$G$1+
  'Stats (Season)'!L3:AB783*'Roster Comparison'!$G$2+
  'Stats (Last 2 weeks)'!L3:AB783*'Roster Comparison'!$G$3
))"""


def is_blank(values: list[list[str]]) -> bool:
    return not any(cell != "" for row in values for cell in row)


def ensure_sheet(spreadsheet, title: str):
    try:
        worksheet = spreadsheet.worksheet(title)
    except Exception as error:
        # gspread exposes WorksheetNotFound, but avoiding an import keeps this
        # script compatible with the project's supported gspread versions.
        if error.__class__.__name__ != "WorksheetNotFound":
            raise
        worksheet = spreadsheet.add_worksheet(title=title, rows=783, cols=28)
    if worksheet.row_count < 783 or worksheet.col_count < 28:
        worksheet.resize(rows=max(783, worksheet.row_count), cols=max(28, worksheet.col_count))
    return worksheet


def copy_range(spreadsheet, source, destination, source_range: str) -> None:
    start, end = source_range.split(":")
    source_start = source.range(start)[0]
    source_end = source.range(end)[0]
    destination_start = destination.range(start)[0]
    spreadsheet.batch_update(
        {
            "requests": [
                {
                    "copyPaste": {
                        "source": {
                            "sheetId": source.id,
                            "startRowIndex": source_start.row - 1,
                            "endRowIndex": source_end.row,
                            "startColumnIndex": source_start.col - 1,
                            "endColumnIndex": source_end.col,
                        },
                        "destination": {
                            "sheetId": destination.id,
                            "startRowIndex": destination_start.row - 1,
                            "endRowIndex": destination_start.row - 1 + (source_end.row - source_start.row + 1),
                            "startColumnIndex": destination_start.col - 1,
                            "endColumnIndex": destination_start.col - 1 + (source_end.col - source_start.col + 1),
                        },
                        "pasteType": "PASTE_NORMAL",
                    }
                }
            ]
        }
    )


def main(apply: bool) -> None:
    config = load_config()
    settings = config["google_sheets"]
    spreadsheet = get_gspread_client(settings["credentials_path"], settings["token_path"]).open_by_key(
        settings["spreadsheet_id"]
    )
    source = spreadsheet.worksheet(SOURCE_SHEET)
    projections = ensure_sheet(spreadsheet, PROJECTIONS_SHEET)
    season = ensure_sheet(spreadsheet, SEASON_SHEET)
    recent = ensure_sheet(spreadsheet, RECENT_SHEET)

    source_anchor = str(source.acell("L3", value_render_option="FORMULA").value or "")
    if source_anchor.startswith("=ARRAYFORMULA("):
        raise SystemExit("Migration has already been applied; Player Values - Cats!L3 is the weighted formula.")
    if not is_blank(projections.get(DATA_RANGE)):
        raise SystemExit("Projections already has data in L3:AB783; refusing to overwrite it.")
    if not is_blank(season.get(DATA_RANGE)) or not is_blank(recent.get(DATA_RANGE)):
        raise SystemExit("A stats input tab already has data in L3:AB783; refusing to overwrite it.")

    print(f"Spreadsheet: {spreadsheet.url}")
    print(f"Copy {SOURCE_SHEET}!{SOURCE_RANGE} to {PROJECTIONS_SHEET}!{SOURCE_RANGE}")
    print(f"Copy headers to {SEASON_SHEET} and {RECENT_SHEET}; leave their data rows blank")
    print(f"Replace {SOURCE_SHEET}!{DATA_RANGE} with one weighted array formula")
    if not apply:
        print("Dry run only. Re-run with --apply to make these changes.")
        return

    copy_range(spreadsheet, source, projections, SOURCE_RANGE)
    copy_range(spreadsheet, source, season, HEADER_RANGE)
    copy_range(spreadsheet, source, recent, HEADER_RANGE)
    source.batch_clear([DATA_RANGE])
    source.update([[WEIGHTED_FORMULA]], "L3", value_input_option="USER_ENTERED")
    print("Migration complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Perform the migration after validation.")
    main(parser.parse_args().apply)
