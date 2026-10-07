"""Command-line entry point for FantasyHelper."""

from __future__ import annotations

import argparse

from fantasyhelper.config import load_config
from fantasyhelper.data_sources import load_projection_sheet
from fantasyhelper.pipeline import build_reports, write_reports
from fantasyhelper.sheets import publish_reports, update_rosters, update_rosters_from_local_html
from fantasyhelper.season_stats import update_season_stats
from fantasyhelper.stats import update_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Build fantasy hockey reports")
    parser.add_argument("command", nargs="?", choices=("update-data", "build", "publish", "update-roster", "update-roster-local", "update-stats"))
    parser.add_argument("--updateroster", action="store_true", help="Fetch Yahoo rosters and update the configured Google Sheet")
    parser.add_argument("--updaterosterlocal", action="store_true", help="Use a saved Yahoo roster HTML page to update the configured Google Sheet")
    parser.add_argument("--updatestats", action="store_true", help="Fetch NHL season stats and update Stats (Season) z-scores")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--data", default="nhl_data.h5")
    parser.add_argument("--output", default="data/reports")
    parser.add_argument("--with-projections", action="store_true", help="Load the configured Google projections tab")
    args = parser.parse_args()
    update_flags = sum((args.updateroster, args.updaterosterlocal, args.updatestats))
    if update_flags > 1:
        parser.error("choose only one sheet update flag")
    if args.updatestats:
        if args.command and args.command != "update-stats":
            parser.error("the stats update flag cannot be combined with another command")
        args.command = "update-stats"
    if args.updateroster or args.updaterosterlocal:
        requested_command = "update-roster-local" if args.updaterosterlocal else "update-roster"
        if args.command and args.command != requested_command:
            parser.error("roster update flags cannot be combined with another command")
        if args.updateroster and args.updaterosterlocal:
            parser.error("choose either --updateroster or --updaterosterlocal")
        args.command = requested_command
    if not args.command:
        parser.error("a command is required")
    config = load_config(args.config)
    if args.command == "update-data":
        schedule = config["schedule"]
        update_data(args.data, date=schedule["start_date"], schedule_end=schedule["end_date"],
                    season=config["season"]["target"], league_id=config["league"]["yahoo_league_id"])
        return
    if args.command in ("update-roster", "update-roster-local"):
        result = update_rosters_from_local_html(config) if args.command == "update-roster-local" else update_rosters(config)
        print(f"Updated {result.matched_players} rostered players; set all other sheet players to Undrafted.")
        if result.yahoo_players_not_on_sheet:
            print("Yahoo players not found on the sheet: " + ", ".join(result.yahoo_players_not_on_sheet))
        if result.ambiguous_sheet_players:
            print("Ambiguous Yahoo ownership (left Undrafted): " + ", ".join(result.ambiguous_sheet_players))
        return
    if args.command == "update-stats":
        result = update_season_stats(config)
        print(f"Updated {result.season_players_with_nhl_stats} of {result.sheet_players} sheet players in Stats (Season) "
              f"and {result.recent_players_with_nhl_stats} in Stats (Last 2 weeks). "
              f"NHL players not on the sheet: season={result.season_unmatched_nhl_players}, "
              f"last-two-weeks={result.recent_unmatched_nhl_players}.")
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
