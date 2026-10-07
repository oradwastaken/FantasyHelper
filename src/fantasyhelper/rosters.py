"""Yahoo-to-Google-Sheets roster synchronization."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pandas as pd


_TEAM_TABLE = re.compile(
    r'<div><p[^>]*>\s*<a href="/hockey/[^\"]+/\d+">(?P<team>[^<]+)</a>'
    r'.*?<table[^>]*id="Tst-team-\d+"[^>]*>(?P<table>.*?)</table>',
    re.DOTALL,
)
_PLAYER_NAME = re.compile(
    r'<a[^>]*class="Nowrap name [^"]*"[^>]*title="([^"]+)"'
)


@dataclass(frozen=True)
class RosterUpdate:
    """The values and diagnostics produced for one roster-sheet update."""

    values: list[list[str]]
    matched_players: int
    yahoo_players_not_on_sheet: list[str]
    ambiguous_sheet_players: list[str]


def fetch_local_rosters(path_pattern: str) -> pd.DataFrame:
    """Parse a Yahoo ``Starting Rosters`` page saved locally as HTML.

    The page contains one ``Tst-team-*`` table for each fantasy team.  The
    fantasy-team name is kept as the manager field, allowing ``manager_aliases``
    to map it to the worksheet's owner values.
    """
    from html import unescape
    from glob import glob
    from pathlib import Path

    paths = [Path(path) for path in glob(path_pattern)]
    if not paths:
        raise FileNotFoundError(f"No saved Yahoo roster page matches {path_pattern!r}")
    source = max(paths, key=lambda path: path.stat().st_mtime)
    html = source.read_text(encoding="utf-8")
    records = []
    for match in _TEAM_TABLE.finditer(html):
        team = unescape(match.group("team")).strip()
        names = _PLAYER_NAME.findall(match.group("table"))
        for name in names:
            records.append({"FullName": unescape(name), "manager": team, "fantasy_team": team})
    if not records:
        raise ValueError(f"No Yahoo roster tables were found in {source}")
    return pd.DataFrame(records)


def _normalise_name(value: object) -> str:
    """Make small presentation differences in player names harmless."""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def build_roster_update(
    sheet_player_names: Sequence[object],
    yahoo_rosters: pd.DataFrame,
    manager_aliases: Mapping[str, str] | None = None,
) -> RosterUpdate:
    """Assign each sheet player to a manager, or ``Undrafted``.

    ``manager_aliases`` maps Yahoo manager names (or Yahoo fantasy-team names) to
    the exact data-validation values used by the worksheet.  Managers that already
    use the worksheet value need no entry.
    """
    required = {"FullName", "manager", "fantasy_team"}
    missing = required.difference(yahoo_rosters.columns)
    if missing:
        raise ValueError(f"Yahoo roster data is missing columns: {', '.join(sorted(missing))}")

    aliases = dict(manager_aliases or {})
    assignments: dict[str, set[str]] = {}
    yahoo_names: set[str] = set()
    for row in yahoo_rosters.itertuples(index=False):
        name = str(row.FullName).strip()
        if not name:
            continue
        manager = str(row.manager).strip()
        team = str(row.fantasy_team).strip()
        owner = aliases.get(manager, aliases.get(team, manager))
        key = _normalise_name(name)
        assignments.setdefault(key, set()).add(owner)
        yahoo_names.add(key)

    sheet_keys: dict[str, list[int]] = {}
    for index, name in enumerate(sheet_player_names):
        if name is not None and str(name).strip():
            sheet_keys.setdefault(_normalise_name(name), []).append(index)

    values: list[list[str]] = []
    ambiguous: list[str] = []
    matched = 0
    for name in sheet_player_names:
        if name is None or not str(name).strip():
            values.append([""])
            continue
        key = _normalise_name(name)
        owners = assignments.get(key, set())
        if len(owners) == 1:
            values.append([next(iter(owners))])
            matched += 1
        else:
            values.append(["Undrafted"])
            if len(owners) > 1 and name is not None:
                ambiguous.append(str(name))

    missing_from_sheet = sorted(
        str(row.FullName)
        for row in yahoo_rosters.itertuples(index=False)
        if _normalise_name(row.FullName) not in sheet_keys
    )
    return RosterUpdate(values, matched, missing_from_sheet, ambiguous)
