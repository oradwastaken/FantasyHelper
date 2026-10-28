#!/usr/bin/env python3
"""Add the live season-versus-projection z-score delta to Player Values - Cats."""

from fantasyhelper.config import load_config
from fantasyhelper.sheets import get_gspread_client


FORMULA = '''=MAP($AQ$3:$AQ,LAMBDA(id,
  IF(id="","",
    LET(
      rawProjection,XLOOKUP(id,Projections!$A$3:$A,Projections!$E$3:$R),
      rawSeason,XLOOKUP(id,'Stats (Season)'!$A$3:$A,'Stats (Season)'!$E$3:$R),
      projection,ARRAYFORMULA(IF(rawProjection="",0,VALUE(rawProjection))),
      season,ARRAYFORMULA(IF(rawSeason="",0,VALUE(rawSeason))),
      weights,Projections!$E$1:$R$1,
      valid,ARRAYFORMULA((rawProjection<>"")*(rawSeason<>"")),
      IFERROR(
        SUM(FILTER(ARRAYFORMULA(IF(valid,(season-projection)*weights,0)),valid))/
        SUM(FILTER(weights,valid)),
        ""
      )
    )
  )
))'''


def main() -> None:
    config = load_config()
    settings = config["google_sheets"]
    spreadsheet = get_gspread_client(settings["credentials_path"], settings["token_path"]).open_by_key(
        settings["spreadsheet_id"]
    )
    worksheet = spreadsheet.worksheet("Player Values - Cats")
    worksheet.update([["Season vs Projection Δ"], [FORMULA]], "AU2:AU3", value_input_option="USER_ENTERED")
    worksheet.format("AU3:AU", {"numberFormat": {"type": "NUMBER", "pattern": "+0.000;-0.000;0.000"}})
    print("Added live Season vs Projection Δ formula to Player Values - Cats!AU.")


if __name__ == "__main__":
    main()
