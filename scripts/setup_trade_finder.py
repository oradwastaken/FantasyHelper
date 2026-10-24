#!/usr/bin/env python3
"""Initialize the Trade Finder worksheet before its Apps Script is run."""

from fantasyhelper.config import load_config
from fantasyhelper.sheets import get_gspread_client


def main() -> None:
    config = load_config()
    settings = config["google_sheets"]
    spreadsheet = get_gspread_client(settings["credentials_path"], settings["token_path"]).open_by_key(
        settings["spreadsheet_id"]
    )
    worksheet = spreadsheet.worksheet("Trade Finder")
    worksheet.update(
        [["Trade Finder"], ["Run Fantasy Helper → Find Trades to generate up to 30 trade ideas."]],
        "A1:A2", value_input_option="USER_ENTERED"
    )
    worksheet.format("A1", {"textFormat": {"bold": True, "fontSize": 14}})
    print("Initialized Trade Finder.")


if __name__ == "__main__":
    main()
