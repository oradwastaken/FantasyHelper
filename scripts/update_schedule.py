#!/usr/bin/env python3
"""Run the Google Sheet Schedule/H2H remaining-games refresh."""
from fantasyhelper.config import load_config
from fantasyhelper.schedule_sync import update_schedule

if __name__ == "__main__":
    result = update_schedule(load_config())
    print(f"Updated Schedule and H2H for week {result.matchup_week}: games remaining from {result.as_of_date:%Y-%m-%d} through {result.end_date:%Y-%m-%d} for {result.teams_updated} teams.")
