"""Install the live ID-keyed formula for Player Values.

The source tabs may be sorted independently.  Each is joined to Player Values
by NHL_PLAYER_ID, not row number.  The Google Sheets formula reads all three
source tabs and weights directly, so edits recalculate without rerunning Python.

Usage:
    uv run python scripts/sync_weighted_player_values.py
    uv run python scripts/sync_weighted_player_values.py --apply
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fantasyhelper.config import load_config
from fantasyhelper.players import normalize_name
from fantasyhelper.sheets import get_gspread_client


PLAYER_VALUES = "Player Values - Cats"
SOURCES = ("Projections", "Stats (Season)", "Stats (Last 2 weeks)")
ROW_START = 3
ROW_END = 782
PLAYER_DETAILS_RANGE = f"E{ROW_START}:G{ROW_END}"
ID_COLUMN = "A"
PLAYER_VALUES_ID_COLUMN = "AQ"
DATA_RANGE = f"L{ROW_START}:AB{ROW_END}"
NHL_API = "https://api-web.nhle.com/v1"
NHL_SEARCH = "https://search.d3.nhle.com/api/v1/search/player"
HEADERS = {"User-Agent": "FantasyHelper/1.0 (personal fantasy hockey tool)", "Accept": "application/json"}
# Official NHL directory spellings differ from the fantasy-sheet display names.
# These IDs were verified against the NHL player-search endpoint.
NHL_ID_OVERRIDES = {
    ("Yegor Chinakhov", "PIT"): "8482475",  # Official directory: Egor Chinakhov
    ("Joe Veleno", "NYR"): "8480813",  # Official directory: Joseph Veleno
}


def fetch_json(url: str) -> object:
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def compatible_position(sheet_position: str, nhl_position: str | None) -> bool:
    wanted = {"L" if position == "LW" else "R" if position == "RW" else position for position in sheet_position.split(",")}
    return nhl_position in wanted


def player_name(player: dict) -> str:
    return f"{player['firstName']['default']} {player['lastName']['default']}"


def candidate_name(player: dict) -> str:
    return player.get("name") or player_name(player)


def current_roster_index(teams: set[str], season: str) -> dict[tuple[str, str], list[dict]]:
    """Return current official NHL roster entries by (team abbreviation, name)."""
    result: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for team in sorted(teams):
        roster = fetch_json(f"{NHL_API}/roster/{team}/{season}")
        assert isinstance(roster, dict)
        for group in ("forwards", "defensemen", "goalies"):
            for player in roster.get(group, []):
                result[(team, normalize_name(player_name(player)))].append(player)
        # The public endpoint throttles bursts; this keeps a complete refresh
        # below its rate limit.
        time.sleep(0.1)
    return result


def choose_candidate(candidates: list[dict], name: str, team: str, position: str) -> dict | None:
    exact = [candidate for candidate in candidates if normalize_name(candidate_name(candidate)) == normalize_name(name)]
    compatible = [candidate for candidate in exact if compatible_position(position, candidate.get("positionCode"))]
    if len(compatible) == 1:
        return compatible[0]
    same_team = [candidate for candidate in compatible if candidate.get("teamAbbrev") == team]
    if len(same_team) == 1:
        return same_team[0]
    # Yahoo eligibility can differ from the NHL API's primary position. An
    # exact name is still safe when it identifies exactly one NHL player.
    return exact[0] if len(exact) == 1 else None


def resolve_ids(rows: list[list[str]], season: str) -> list[str]:
    teams = {row[1] for row in rows}
    roster_index = current_roster_index(teams, season)
    resolved: list[str] = []
    unresolved: list[str] = []

    for name, team, position in rows:
        candidate = choose_candidate(roster_index.get((team, normalize_name(name)), []), name, team, position)
        if candidate is None and (name, team) in NHL_ID_OVERRIDES:
            resolved.append(NHL_ID_OVERRIDES[(name, team)])
            continue
        if candidate is None:
            query = urlencode({"culture": "en-us", "limit": "20", "q": name})
            search_results = fetch_json(f"{NHL_SEARCH}?{query}")
            assert isinstance(search_results, list)
            candidate = choose_candidate(search_results, name, team, position)
            time.sleep(0.05)
        if candidate is None:
            unresolved.append(f"{name} ({team}, {position})")
        else:
            resolved.append(str(candidate.get("id", candidate.get("playerId"))))

    if unresolved:
        preview = "\n".join(f"- {player}" for player in unresolved[:20])
        suffix = "" if len(unresolved) <= 20 else f"\n- ... and {len(unresolved) - 20} more"
        raise ValueError(f"Could not uniquely resolve {len(unresolved)} NHL IDs:\n{preview}{suffix}")
    if len(set(resolved)) != len(resolved):
        duplicates = sorted({player_id for player_id in resolved if resolved.count(player_id) > 1})
        raise ValueError(f"NHL ID resolution produced duplicate IDs: {', '.join(duplicates)}")
    return resolved


def column_values(worksheet, cell_range: str, row_count: int) -> list[str]:
    rows = worksheet.get(cell_range, value_render_option="UNFORMATTED_VALUE")
    values = [str(row[0]) if row and row[0] not in (None, "") else "" for row in rows]
    return (values + [""] * row_count)[:row_count]


def column_letter(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def weighted_formulas() -> list[str]:
    """Return one dynamic ID-keyed array formula per stat column."""
    formulas = []
    for offset in range(17):
        source_column = column_letter(2 + offset)  # B:R on each input tab
        formulas.append(f'''=ARRAYFORMULA(LET(
  ids, $AQ${ROW_START}:$AQ${ROW_END},
  projVals, IFNA(XLOOKUP(ids, Projections!$A${ROW_START}:$A${ROW_END}, Projections!${source_column}${ROW_START}:${source_column}${ROW_END}, ""), ""),
  seasonVals, IFNA(XLOOKUP(ids, 'Stats (Season)'!$A${ROW_START}:$A${ROW_END}, 'Stats (Season)'!${source_column}${ROW_START}:${source_column}${ROW_END}, ""), ""),
  recentVals, IFNA(XLOOKUP(ids, 'Stats (Last 2 weeks)'!$A${ROW_START}:$A${ROW_END}, 'Stats (Last 2 weeks)'!${source_column}${ROW_START}:${source_column}${ROW_END}, ""), ""),
  IF(
    (projVals="")*(seasonVals="")*(recentVals=""),
    "",
    N(projVals)*'Roster Comparison'!$G$1+
    N(seasonVals)*'Roster Comparison'!$G$2+
    N(recentVals)*'Roster Comparison'!$G$3
  )
))''')
    return formulas


def validate_or_initialize_ids(worksheet, ids: list[str], cell_range: str, *, initialize: bool) -> None:
    existing = column_values(worksheet, cell_range, len(ids))
    if not any(existing):
        if initialize:
            worksheet.update([[player_id] for player_id in ids], cell_range)
        return
    elif any(not value for value in existing):
        raise ValueError(f"{worksheet.title}!{cell_range} has some missing NHL IDs; refusing to realign sorted rows")
    elif len(set(existing)) != len(existing) or set(existing) != set(ids):
        raise ValueError(f"{worksheet.title}!{cell_range} must contain each current NHL ID exactly once")


def main(apply: bool) -> None:
    config = load_config()
    settings = config["google_sheets"]
    book = get_gspread_client(settings["credentials_path"], settings["token_path"]).open_by_key(settings["spreadsheet_id"])
    player_values = book.worksheet(PLAYER_VALUES)
    details = player_values.get(PLAYER_DETAILS_RANGE)
    if len(details) != ROW_END - ROW_START + 1 or any(len(row) != 3 or not all(row) for row in details):
        raise ValueError(f"Expected complete name, team, and position values in {PLAYER_VALUES}!{PLAYER_DETAILS_RANGE}")

    player_ids = column_values(player_values, f"{PLAYER_VALUES_ID_COLUMN}{ROW_START}:{PLAYER_VALUES_ID_COLUMN}{ROW_END}", len(details))
    if not any(player_ids):
        print("Resolving NHL player IDs from the official NHL roster and player-search APIs...")
        player_ids = resolve_ids(details, config["season"]["target"])
        print(f"Resolved {len(player_ids)} unique NHL player IDs.")
    elif any(not player_id for player_id in player_ids) or len(set(player_ids)) != len(player_ids):
        raise ValueError(f"{PLAYER_VALUES}!{PLAYER_VALUES_ID_COLUMN}{ROW_START}:{PLAYER_VALUES_ID_COLUMN}{ROW_END} has missing or duplicate NHL IDs")
    else:
        print(f"Using {len(player_ids)} existing NHL IDs from {PLAYER_VALUES}!{PLAYER_VALUES_ID_COLUMN}.")

    worksheets = [book.worksheet(title) for title in SOURCES]
    for worksheet in worksheets:
        validate_or_initialize_ids(worksheet, player_ids, f"{ID_COLUMN}{ROW_START}:{ID_COLUMN}{ROW_END}", initialize=apply)
    weight_cells = book.worksheet("Roster Comparison").get("G1:G3", value_render_option="UNFORMATTED_VALUE")
    weights = [float(row[0] or 0) if row else 0.0 for row in weight_cells]
    if len(weights) != 3:
        raise ValueError("Roster Comparison!G1:G3 must contain all three source weights.")

    print(f"Weights: projections={weights[0]:g}, season={weights[1]:g}, last 2 weeks={weights[2]:g}")
    if not apply:
        print("Dry run only. Re-run with --apply to install the live weighted formula.")
        return

    id_values = [[player_id] for player_id in player_ids]
    if player_values.col_count < 43:
        player_values.resize(cols=43)
    if not player_values.acell(f"{PLAYER_VALUES_ID_COLUMN}2").value:
        player_values.update([["NHL_PLAYER_ID"]], f"{PLAYER_VALUES_ID_COLUMN}2")
    if not any(column_values(player_values, f"{PLAYER_VALUES_ID_COLUMN}{ROW_START}:{PLAYER_VALUES_ID_COLUMN}{ROW_END}", len(player_ids))):
        player_values.update(id_values, f"{PLAYER_VALUES_ID_COLUMN}{ROW_START}:{PLAYER_VALUES_ID_COLUMN}{ROW_END}")
    for worksheet in worksheets:
        if not worksheet.acell(f"{ID_COLUMN}2").value:
            worksheet.update([["NHL_PLAYER_ID"]], f"{ID_COLUMN}2")

    player_values.batch_clear([DATA_RANGE])
    player_values.update([weighted_formulas()], "L3", value_input_option="USER_ENTERED")
    print("Live NHL-ID weighted formulas installed in Player Values!L3:AB3.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write NHL IDs and refresh Player Values.")
    main(parser.parse_args().apply)
