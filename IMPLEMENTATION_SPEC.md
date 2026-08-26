# Fantasy Hockey Helper: Implementation Specification

## Goal

Build a configurable Python workflow that produces:

1. Overall cats rankings by eligible position: C, LW, RW, D, G.
2. Individual rankings for each of the 15 fantasy categories.
3. A team-strength report showing every fantasy team's relative category strengths and weaknesses.
4. A new Google Sheet containing all reports.

Draft value remains the primary signal. Schedule quality, playoff schedule, and rival matchup value act only as configurable tiebreakers.

## Configuration

Add `config.yaml`, committed with editable defaults:

```yaml
league:
  yahoo_league_id: "465.l.6920"
  team_count: 8
  my_team_name: "Slaffing From The Throne"
  rival_team_name: "McJesus Take The Wheel"

season:
  target: "20262027"
  historical: "20252026"
  games_per_season: 84
  regular_season_game_type: 2

roster:
  active_slots:
    C: 4
    LW: 4
    RW: 4
    D: 6
    UTIL: 2
    G: 4
  total_roster_size: 30

ranking:
  methodology: "z_score"
  projection_weight: 0.70
  historical_weight: 0.30
  goalie_min_games_played: 15
  schedule_tiebreaker_weight: 0.05
  playoff_tiebreaker_weight: 0.10
  rival_tiebreaker_weight: 0.05

schedule:
  playoff_weeks: []
  rival_matchup_weeks: []

sources:
  projections_sheet_url: "https://docs.google.com/spreadsheets/d/..."
  projections_tab: "Player Values - Cats"

google_sheets:
  spreadsheet_title: "Fantasy Hockey Rankings"
  credentials_path: ".secrets/google-oauth-client.json"
```

Playoff and rival weeks remain empty until confirmed, preventing unverified schedule assumptions from affecting rankings.

## Data ingestion

Refactor the existing `update_data()` workflow to accept the configured season and use cached, date-stamped source files. This avoids unnecessary NHL/Yahoo API calls and reduces rate-limit risk.

Collect:

- NHL historical skater and goalie data for 2025-26.
- NHL schedule data for the target season, covering all relevant regular-season and playoff weeks.
- Yahoo league rosters, team names, managers, and every player's eligible-position list.
- Projections from the configured Google Sheet.
- NHL team rosters/player identity data where needed to reconcile projection, NHL, and Yahoo player records.

Use NHL player ID as the primary NHL identifier. Build a reusable player-matching layer with normalized names and team/position checks as fallbacks, plus a review report for unmatched or ambiguous players.

Correct the current skater data collection so all needed categories are fetched, including blocked shots. Standardize all outputs to:

- Skaters: `G`, `A`, `+/-`, `PIM`, `PPP`, `SHP`, `SOG`, `FOW`, `HIT`, `BLK`
- Goalies: `W`, `GAA`, `SV%`, `SO`, plus `GP`

## Projections and historical blend

For counting categories, historical values are prorated:

`prorated_stat = historical_stat / GP * 84`

Players below the configured minimum historical GP should remain available but be flagged as low-sample; they should not cause division errors or silently receive extreme values.

Combine sources per category:

`blended_value = projection_weight x projection + historical_weight x prorated_historical`

If a player is missing from one source, use the available source and flag the missing value in the output. If neither source is available, exclude the player from ranks but include them in the data-quality report.

For ratio goalie categories, retain GAA and SV% as projected/blended rates rather than prorating them as totals. Require at least the configured goalie GP threshold for normal ranking eligibility; below-threshold goalies appear in a separate "limited sample" section.

## Position eligibility and replacement levels

Yahoo eligibility is the source of truth for fantasy positions. A dual-eligible player appears in every ranking matching their Yahoo eligibility.

For example, a C/LW player is evaluated independently as both a center and a left wing. Their category scores are identical, but their overall value differs because the replacement-level pool differs at C and LW.

Define draftable skater pools from 8 teams and active slots:

- C: 32
- LW: 32
- RW: 32
- D: 48
- UTIL: 16 skaters
- G: 32

Use a configurable allocation method for UTIL slots, initially assigning them to the best remaining skaters across eligible positions after the dedicated position pools are filled. The report should explicitly state the replacement-level cutoff used for each position.

## Ranking methodology

Use z-scores against the relevant draftable player pool.

For each category:

- Calculate mean and standard deviation among eligible draftable players.
- Convert player values to z-scores.
- Invert GAA, so lower GAA produces a higher score.
- Keep `SV%` and all other positive categories in their normal direction.

Overall position value is the equal-weight sum of the 15 category z-scores, while separating skater and goalie rankings so incompatible categories are never blended. Since all league categories count equally, every category receives equal weight; z-scores naturally normalize categories with different scales and availability.

Generate:

- Overall C, LW, RW, D, and G rankings.
- One ranking for each of the 15 categories.
- Raw values, historical values, projections, blended values, z-score, rank, eligibility, NHL team, and ownership status for every ranked player.

## Schedule scoring

Compute each NHL team's games by fantasy week, then map them to players.

For each player, report:

- Total target-season games.
- Playoff-week games.
- Rival-matchup-week games.
- Weekly games and off-night games, if schedule data supports reliable identification.

Schedule metrics are displayed separately and only added as small configurable tiebreakers to the primary player-value score. A weak player should never outrank a materially stronger player solely due to schedule.

## Team-strength report

Using Yahoo rosters and the same player values, create a table with one row per fantasy team and columns for:

- Overall skater strength
- Overall goalie strength
- Each of the 15 category strengths
- League rank for every strength column
- Best and weakest categories
- Rostered-player count by eligible position
- Schedule metrics for playoff and rival weeks, once configured

Team category strength should be the sum of rostered player category z-scores, normalized where necessary for positional roster differences. The report should show both the numerical score and ordinal ranking, for example, "A: 2nd of 8."

## Google Sheets output

Add OAuth browser sign-in using a local Google OAuth client configuration excluded from Git. On first run, open the browser consent flow and store the refresh token locally outside version control.

Create a new spreadsheet named from the configured title and populate these tabs:

- `README` - timestamp, seasons, source weights, configuration summary, and methodology.
- `Overall - C`
- `Overall - LW`
- `Overall - RW`
- `Overall - D`
- `Overall - G`
- `Category - G` through `Category - SO`
- `Team Strength`
- `Schedule`
- `Data Quality`

Freeze header rows, apply filters, format percentage/rate columns appropriately, and include links or notes for source provenance. Subsequent runs update the same configured spreadsheet ID.

## Code structure

Add focused modules rather than expanding `stats.py` indefinitely:

- `config.py` - load and validate YAML configuration.
- `data_sources.py` - NHL, Yahoo, and projections retrieval with caching.
- `players.py` - identity reconciliation and eligibility handling.
- `projections.py` - historical proration and blended projections.
- `rankings.py` - replacement pools, z-scores, category/position reports.
- `schedule.py` - weekly, playoff, and rival schedule metrics.
- `team_strength.py` - roster aggregation and league-relative team ranks.
- `sheets.py` - OAuth and Google Sheets publishing.
- `cli.py` - commands such as `update-data`, `build-rankings`, and `publish`.

Keep `update_data()` as a compatible facade if useful, but move its hard-coded league and season values into configuration.

## Verification

1. Unit-test stat normalization, 84-game prorating, inverse GAA scoring, missing-source handling, and dual-eligibility ranking.
2. Run the pipeline using 2025 off-season inputs and 2025-26 historical outcomes.
3. Compare generated category and overall ranks with end-of-year Yahoo fantasy rankings.
4. Inspect a sample of dual-eligible players manually to confirm appearance and position-specific rank differences.
5. Confirm team-strength totals reproduce roster composition and that `Slaffing From The Throne` and the configured rival resolve correctly.
6. Run ingestion twice and confirm cached data avoids duplicate network calls.
7. Publish to a test Google Sheet, verify OAuth refresh works, then publish the production sheet.

Implementation should be committed in logical stages: configuration/data foundation, ranking engine, schedule/team reports, Sheets export, and tests.
