# FantasyHelper


Based on Coreyjs's [nhl-api-py](https://github.com/coreyjs/nhl-api-py) package and mattdodge's [yahoofantasy](https://github.com/mattdodge/yahoofantasy) packages. All package dependencies are managed using uv.

---

## Installation

1. **Install uv**  
   Follow instructions at [uv installation](https://docs.astral.sh/uv/getting-started/installation/).

2. **Sync dependencies**  
   From the project root, run:
   ```bash
   uv sync
   ```
   This installs all dependencies and links the project (fantasyhelper) in editable mode.
3. **Start Jupyter**
    Launch with:
    ```bash
    uv run jupyter notebook
    ```
   
    Make sure the notebook kernel is set to the `uv` environment created for this project (usually located in .venv/). If you don’t see it, you can add it manually:
    ```bash
    uv run python -m ipykernel install --user --name=fantasyhelper
   ```

    Then, open jupyter notebook:
    ```
    uv run jupyter notebook
    ```

    The app's core functionality is in [main.ipynb](main.ipynb).

## Rankings workflow

Edit [config.yaml](config.yaml) with the current Yahoo league, season, schedule, and
Google projections-sheet details. Build CSV reports from the local HDF5 snapshot with:

```bash
uv sync --no-editable
uv run --no-editable fantasyhelper build
```

This project uses a non-editable install because the current macOS Python environment
does not load editable-install path files reliably. After changing package source files,
force a rebuild of the installed project package:

```bash
uv sync --no-editable --reinstall-package fantasyhelper
```

To include projections, create a Google OAuth desktop client JSON file at the configured
credentials path and run `uv run --no-editable fantasyhelper build --with-projections`. The first use
opens a browser sign-in flow. Publish all reports to a new (or configured existing) Google
Sheet with `uv run --no-editable fantasyhelper publish --with-projections`.

## Sync Yahoo rosters to Google Sheets

The roster updater fetches every player on the configured Yahoo league's rosters and
writes their owner to `Player Values - Cats!D3:D783`.  It sets sheet players absent
from Yahoo rosters to `Undrafted`, while preserving the sheet's validation, formatting,
and formulas.

```bash
uv sync --no-editable --reinstall-package fantasyhelper
uv run --no-editable fantasyhelper --updateroster
# equivalent: uv run --no-editable fantasyhelper update-roster
```

`config.yaml` contains the target spreadsheet ID and the source/target columns. If a
Yahoo manager nickname differs from the worksheet's validation value, add it under
`roster_sync.manager_aliases`; keys may be either Yahoo manager nicknames or fantasy
team names. For example:

```yaml
roster_sync:
  manager_aliases:
    Rob: "Rob/Orad"
```

### One-time Google authorization

This repository does not currently contain Google OAuth credentials. To authorize it:

1. In Google Cloud Console, create or select a project, enable the Google Sheets API
   and Google Drive API, then configure the OAuth consent screen for the Google account
   that can edit the target spreadsheet.
2. Create an OAuth 2.0 **Desktop app** client and download its JSON file as
   `.secrets/google-oauth-client.json`. The `.secrets` directory is gitignored.
3. Confirm that the Google account used at sign-in is an editor of the target sheet.
4. Run the updater command above. Your browser will open once; sign in and approve the
   requested Sheets/Drive permissions. A refresh token is saved to
   `.secrets/google-token.json` for later runs.

### Update from a downloaded Yahoo roster page

If Yahoo API access is unavailable, visit [Yahoo's Starting Rosters page](https://hockey.fantasysports.yahoo.com/hockey/5325/startingrosters), then select **File → Save As → Page Source** in your browser and save the HTML under `roster_site/`. Then run:

```bash
uv run --no-editable fantasyhelper --updaterosterlocal
```

The updater selects the most recently modified matching HTML file, reads each Yahoo
fantasy-team table, and maps the team name through `roster_sync.manager_aliases` in
`config.yaml` before updating the sheet. Update those aliases if a team is renamed.

## Update NHL season stats

Fetch all NHL regular-season skater and goalie statistics for `season.target`, compute
population z-scores for each fantasy category, and write them to both `Stats (Season)`
and `Stats (Last 2 weeks)`:

```bash
uv sync --no-editable --reinstall-package fantasyhelper
uv run --no-editable fantasyhelper --updatestats
# equivalent: uv run --no-editable fantasyhelper update-stats
```

The command uses the `NHL_PLAYER_ID` column to preserve the existing sheet ordering,
checks that both stats sheets and `Projections` have the same IDs and headers, and only
updates `B:R`. Skater categories are standardized from per-game rates; goalie wins and
shutouts are standardized from per-start rates, while GAA and SV% are already rates.
GAA is inverted so lower is better. The recent sheet uses the inclusive 14-calendar-day
window ending today. `OFF` and `POG` remain blank because they are projection-only
fields rather than NHL API stats.
