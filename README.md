# webscrape-aiub-world-cup-2026

Scraper + analysis tooling for the [AIUB World Cup 2026](https://ofsportsaiub.org/) football
tournament (48 teams, 16 groups). Built in three phases: **scraper** (this phase) → possible-opponents
**projection** → Flask **dashboard**. See `docs/superpowers/specs/` for the design.

## Scraper

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python -m scraper.run              # scrape everything -> data/latest/*.json
./venv/bin/python -m scraper.run --no-rosters # fast refresh (skip 48 profile fetches)
./venv/bin/python -m scraper.run --only fixtures standings
./venv/bin/pytest -q                          # run tests
```

Output (in `data/latest/`, plus a timestamped copy in `data/snapshots/`):

| File | Contents |
|------|----------|
| `teams.json` | 48 teams: country **and** real team name, faculty, group, captain |
| `rosters.json` | per-team squads (players + stats) |
| `fixtures.json` | 79 matches (group + knockout): teams, date/time, score, status |
| `standings.json` | 16 group tables (P, Pts, GD, GF, Fair Play) |
| `scorers.json` | top scorers (empty until the first goal) |
| `bracket.json` | knockout tree (R32→Final) with seeding labels |
| `manifest.json` | per-run status + counts |

## Projection — who can a team face on the way to the final?

```bash
./venv/bin/python -m projection.cli --team "Netherlands"   # or a real team name, e.g. "CS Backbencher"
./venv/bin/python -m projection.cli --all                  # writes data/latest/projections.json
```

For each team it lists, per knockout round (R32→Final), the set of teams it *could* meet — as group
winner and as runner-up. Deterministic; the sets shrink automatically as real group results come in.

## Dashboard

```bash
./venv/bin/pip install -r requirements.txt   # installs flask
./venv/bin/python -m dashboard.app           # http://127.0.0.1:5000
```

A local Flask dashboard: overview, teams (country + real name), fixtures, standings, knockout
bracket, top scorers, and each team's possible-opponents path to the final. Light + dark. The
**Refresh data** button re-runs the scraper + projection in the background without blocking the page.

## Simulator

Open any team at **`/teams/<id>`** (from the Teams list) to use the opponent simulator. Three
modes — only one panel visible at a time:

| Mode | What it does |
|------|----------------|
| **A — Possible opponents** | Deterministic path-to-final sets (group winner / runner-up scenarios). |
| **B — What-if** | Pick group 1st/2nd and knockout winners; path updates live. Auto-snapshots on change; **Save as…** for named scenarios. |
| **C — Monte Carlo** | Run N trials with a bias dial (0 = uniform, 1 = full strength). Default **N = 1,000**, max **10,000**. |

Simulator state is stored under **`data/simulations/`** (ratings, active picks, history). Scraper
refresh writes only `data/latest/` — it never touches the sim directory.

JSON API (all under `/api/sim/`): ratings, current picks/settings, what-if preview, Monte Carlo run,
and history list/save/restore/rename/delete. Errors return `{ "ok": false, "error": "..." }`.
