"""Command-line entry point for FantasyHelper."""

from __future__ import annotations

import argparse

from fantasyhelper.config import load_config
from fantasyhelper.data_sources import load_projection_sheet
from fantasyhelper.pipeline import build_reports, write_reports
from fantasyhelper.sheets import publish_reports
from fantasyhelper.stats import update_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Build fantasy hockey reports")
    parser.add_argument("command", choices=("update-data", "build", "publish"))
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--data", default="nhl_data.h5")
    parser.add_argument("--output", default="data/reports")
    parser.add_argument("--with-projections", action="store_true", help="Load the configured Google projections tab")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.command == "update-data":
        schedule = config["schedule"]
        update_data(args.data, date=schedule["start_date"], schedule_end=schedule["end_date"],
                    season=config["season"]["target"], league_id=config["league"]["yahoo_league_id"])
        return
    projections = None
    if args.with_projections:
        source = config["sources"]
        google = config["google_sheets"]
        projections = load_projection_sheet(source["projections_sheet_url"], source["projections_tab"], google["credentials_path"], google["token_path"])
    reports = build_reports(args.config, args.data, projections)
    if args.command == "build":
        write_reports(reports, args.output)
        print(f"Wrote {len(reports)} reports to {args.output}")
    else:
        print(f"Published reports to {publish_reports(reports, config)}")


if __name__ == "__main__":
    main()
