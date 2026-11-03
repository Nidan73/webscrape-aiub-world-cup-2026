# AIUB World Cup 2026: scraper, projection and simulator

Python tooling for the AIUB World Cup 2026 football tournament on [ofsportsaiub.org](https://ofsportsaiub.org/) (48 teams in 16 groups, 79 matches, knockout from the Round of 32 to the Final). It scrapes the tournament site into JSON, works out which teams each side could meet on the way to the final, and serves everything in a local Flask dashboard with a what-if and Monte Carlo simulator.

## What it does

- **Scraper** (`scraper/`): reads the site's `tab-api.php` HTML fragments and team profile pages with Requests, Beautiful Soup and lxml. 0.5 s between requests, 20 s timeout, 3 retries. Handles both the empty pre-tournament state and played matches.
- **Projection** (`projection/`): for each team and knockout round, the set of possible opponents as group winner and as runner-up. Deterministic; the sets shrink as real group results come in.
- **Dashboard** (`dashboard/`): overview, teams, fixtures, standings, knockout bracket, top scorers and a page per team, with light and dark themes. The **Refresh data** button re-runs the scraper and projection in one background job without blocking the page.
- **Simulator** (`simulation/`, on each team page at `/teams/<id>`), three modes:
  - **A: Possible opponents.** The deterministic path-to-final sets.
  - **B: What-if.** Pick group 1st and 2nd places and knockout winners; the path updates live. Changes are saved to history automatically, and scenarios can be saved by name.
  - **C: Monte Carlo.** Runs N simulated tournaments, 1,000 by default (maximum 10,000). A bias dial runs from 0 (every team equally likely) to 1 (full strength). Strength is 1 + points + 0.1 x goal difference + 0.01 x goals for once the standings have data; before that, all teams are equal.

## Quick start

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python -m scraper.run                       # scrape everything to data/latest/*.json
./venv/bin/python -m scraper.run --no-rosters          # fast refresh, skips the 48 profile fetches
./venv/bin/python -m scraper.run --only fixtures standings
./venv/bin/python -m projection.cli --team "Netherlands"   # or a real team name
./venv/bin/python -m projection.cli --all              # writes data/latest/projections.json
./venv/bin/python -m dashboard.app                     # http://127.0.0.1:5000
./venv/bin/pytest -q                                   # run the tests
```

`data/` is not committed, so run the scraper before opening the dashboard. The simulator store uses `fcntl` file locks, so it runs on Linux and macOS.

## Output

Written to `data/latest/`, with a timestamped copy in `data/snapshots/`:

| File | Contents |
| --- | --- |
| `teams.json` | 48 teams: country and real team name, faculty, group, captain |
| `rosters.json` | Squads with player stats |
| `fixtures.json` | 79 matches (group and knockout): teams, date and time, score, status |
| `standings.json` | 16 group tables (P, Pts, GD, GF, fair play) |
| `scorers.json` | Top scorers (empty until the first goal) |
| `bracket.json` | Knockout tree (Round of 32 to Final) with seeding labels |
| `manifest.json` | Per-run status and counts |
| `projections.json` | Possible opponents per team and round (written by the projection step) |

Simulator state (ratings, current picks, history) is stored in `data/simulations/`. A scraper refresh writes only `data/latest/` and never touches it.

## Simulator API

All routes are under `/api/sim/`:

| Method | Route | Purpose |
| --- | --- | --- |
| GET, PUT | `/ratings` | Strength overrides |
| GET, PUT | `/current` | Current picks and settings |
| POST | `/whatif/preview` | Path preview for a set of picks |
| POST | `/montecarlo/run` | Run a Monte Carlo simulation |
| GET, POST | `/history` | List or save scenarios |
| POST | `/history/<id>/restore` | Restore a saved scenario |
| PATCH, DELETE | `/history/<id>` | Rename or delete a saved scenario |

Errors return `{"ok": false, "error": "..."}`.

## Tests

The pytest suite in `tests/` covers the HTTP client, every parser, the JSON writer, the projection, the simulation modules, the simulator API and the dashboard views.

## Layout

- `scraper/`: HTTP client, parsers, models, JSON writer, CLI.
- `projection/`: loader, bracket label resolver, path-to-final builder, CLI.
- `simulation/`: strength model, what-if picks, Monte Carlo, JSON store.
- `dashboard/`: Flask app, background refresh job, simulator API, templates, static JS and CSS.
- `docs/superpowers/`: design specs and phase plans.
- `design-system/`: dashboard design reference.
- `tests/`: pytest suite.
