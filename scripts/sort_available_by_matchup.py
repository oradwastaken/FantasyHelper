#!/usr/bin/env python3
"""Sort the H2H pickup dropdown by matchup-win improvement."""

from fantasyhelper.config import load_config
from fantasyhelper.sheets import get_gspread_client


FORMULA = '''=INDEX(
  SORT(
    FILTER(
      {'Player Values - Cats'!E3:E,'Player Values - Cats'!AS3:AS},
      'Player Values - Cats'!C3:C=FALSE,
      'Player Values - Cats'!E3:E<>""
    ),
    2, FALSE
  ),
  ,1
)'''
PICKUP_GAMES_FORMULA = '''=IF($B79="","",IFNA(INDEX('Player Values - Cats'!$AT$3:$AT,MATCH($B79,'Player Values - Cats'!$E$3:$E,0)),0))'''
DROP_GAMES_FORMULA = '''=IF($B80="","",IFNA(INDEX('Player Values - Cats'!$AT$3:$AT,MATCH($B80,'Player Values - Cats'!$E$3:$E,0)),0))'''


def main() -> None:
    config = load_config()
    settings = config["google_sheets"]
    spreadsheet = get_gspread_client(settings["credentials_path"], settings["token_path"]).open_by_key(
        settings["spreadsheet_id"]
    )
    spreadsheet.worksheet("Available").update([[FORMULA]], "A1", value_input_option="USER_ENTERED")
    spreadsheet.worksheet("H2H").update(
        [[PICKUP_GAMES_FORMULA], [DROP_GAMES_FORMULA]], "C79:C80", value_input_option="USER_ENTERED"
    )
    print("Sorted Available pickup choices by Δ Matchup Win % and updated H2H pickup/drop games remaining.")


if __name__ == "__main__":
    main()
