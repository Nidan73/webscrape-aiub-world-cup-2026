# AIUB World Cup 2026 Scraper — Design Spec

**Date:** 2026-07-21
**Status:** Approved — ready for implementation planning
**Scope:** Three components in one repo:
1. A re-runnable **scraper** producing clean JSON of the full tournament dataset (§2–§7).
2. A deterministic **possible-opponents projection** ("path to the final") over the scraped data (§8).
3. A **Flask web dashboard** that visualizes everything, with a background data-refresh button (§9).

A full probabilistic Monte Carlo simulation is out of scope (§10).

## 1. Goal

Build a re-runnable Python scraper for **https://ofsportsaiub.org/** (the AIUB World Cup 2026
tournament portal) that produces clean, structured JSON of the full tournament dataset. Each run
captures the current state of the tournament (which starts 2026-07-28 and runs into early August),
so the data can seed and later refresh analysis.

On top of that data, provide a **projection** tool: for a chosen team, compute the set of teams they
could face at each knockout round on the way to the final, based purely on the bracket structure and
group assignments (§8).

## 2. Site analysis (confirmed)

All data is **server-rendered HTML** — no JavaScript execution required, so no headless browser.

The site exposes its own data endpoint that `app.js` calls:

- `tab-api.php?tab=<name>` → returns `{"html": "<rendered fragment>", "tab": "<name>"}`.
  Confirmed working for: `overview`, `fixtures`, `groups` (standings), `teams`, `scorers`,
  `bracket`, `fair-play`.
- `/teams/{id}-{slug}` → team profile page (real team name, captain, 16-player roster + stats).
- `/matches/{id}-{slug}` → individual match page (not required; fixtures list has all match data).

The tournament is currently pre-start: 0 matches played, all scores/standings/scorers empty.
Parsers **must handle both** the empty state and the populated (live) state.

### Key selectors (verified against live HTML)

**Teams directory** (`tab=teams`): each team is
`<a class="team-directory-card" href="/teams/{id}-{slug}" data-search="...">` containing
`<strong>{country}</strong>`, `<small>{faculty}</small>`, and `<span class="team-directory-group">Group X</span>`.
Used only to enumerate the 48 teams and their profile URLs.

**Team profile** (`/teams/{id}-{slug}`):
- `<h1>{country}</h1>` — country (e.g. "Netherlands")
- `<span class="profile-team-name">Team · {REAL NAME}</span>` — **the real team name** (strip
  the `"Team · "` prefix → e.g. "CS Backbencher"). This is the field the user specifically wants.
- `.profile-meta` → group + faculty
- `.profile-captain-feature[href="/players/{id}-{slug}"]` → captain
- 16 × `<a class="profile-player" href="/players/{id}-{slug}">` each with:
  jersey `<b>{n}</b>`, name `<strong>`, role `<small>`, optional `roster-captain-mark`,
  and `.player-totals` → `{goals}` goals / `{assists}` assists / `{cards}` cards.

**Fixtures** (`tab=fixtures`): `<article class="fixture-row google-fixture" data-fixture-card>`:
- link `/matches/{id}-{slug}` → match id + slug
- `.fixture-card-head` → `Group X` + `Jul 28, 8:00 AM` (date + time)
- `.fixture-side.home .fixture-team` / `.fixture-side.away .fixture-team` → team names (+ flag code from `src`)
- `.fixture-score[data-live-fixture-score]` → `VS` (unplayed) or `H:A` when played
- foot region → match number ("Match 1") and status text
- `data-fixture-search-text="{home} {away}"`

**Standings** (`tab=groups`): 16 × `<table class="data-table">` with header
`Nation | P | Pts | GD | GF | FP`. Each `<tr>` links the team via `/teams/{id}-{slug}`;
`<tr class="qualify">` marks a qualifying position → `qualified: true`.

**Bracket** (`tab=bracket`): `.ucl-board` with stages `R32, R16, QF, SF, Final`
(`<button data-bracket-jump>` labels), each a `<section class="knockout-stage stage-r32" data-bracket-stage>`.
Most slots are placeholders pre-tournament.

**Scorers** (`tab=scorers`): top-scorer list; currently the empty-state panel
("No goals have been recorded yet").

## 3. Data model (JSON output)

One file per entity in `data/latest/`.

**teams.json** — `[ Team ]`
```
Team = { id, slug, profile_url, flag_url, country, team_name, faculty, group,
         captain: { player_id, name, player_url } | null }
```
`country` + `team_name` sit side by side (the user's requirement). `team_name` and `captain`
come from the profile page and are `null` when profiles are skipped (`--no-rosters`).

**rosters.json** — `[ Roster ]`
```
Roster = { team_id, country, team_name, players: [ Player ] }
Player = { player_id, slug, player_url, jersey_number, name, role, is_captain,
           photo_url, goals, assists, cards }
```

**fixtures.json** — `[ Fixture ]`
```
Fixture = { match_id, slug, match_url, match_no, group, date, time, datetime_iso,
            home: { country, flag_code }, away: { country, flag_code },
            home_score, away_score, status, raw_score }
```
`home_score`/`away_score` are `null` until played (`raw_score == "VS"`). `status` ∈
{`scheduled`, `live`, `final`} derived from the score/status text.

**standings.json** — `[ GroupStanding ]`
```
GroupStanding = { group, table: [ Row ] }
Row = { position, team_id, country, team_url, played, points, goal_diff,
        goals_for, fair_play, qualified }
```

**scorers.json** — `[ Scorer ]` (empty `[]` in the current pre-tournament state)
```
Scorer = { rank, player_id, name, team, goals }
```

**bracket.json** — `[ BracketStage ]`
```
BracketStage = { stage, matches: [ KnockoutMatch ] }
KnockoutMatch = { match_no, next_match_no, match_url, stage,
                  home_label, away_label,          # e.g. "1st of Group A", "2nd of Group I", "Winner of M49"
                  home_team, away_team,            # resolved team name once known, else null
                  home_score, away_score, status }
```
`match_no` + `next_match_no` encode the bracket tree; `home_label`/`away_label` encode the seeding
(group position or "Winner of M#"). These drive the §8 projection.

**manifest.json** (per run) — `{ scraped_at, source, entities: { <name>: { count, source_url, ok, error? } }, snapshot_dir }`

## 4. Architecture

Python 3, `requests` + `beautifulsoup4` + `lxml` + `flask`, in a virtualenv. `pytest` for tests (dev).

```
webscrape-aiub-world-cup-2026/   (repo root)
├── requirements.txt          # requests, beautifulsoup4, lxml, flask
├── README.md  .gitignore
├── scraper/
│   ├── config.py             # BASE_URL, endpoints, output paths, default delay
│   ├── client.py             # requests.Session: UA header, retry+backoff, polite delay,
│   │                         #   fetch_tab(name)->fragment html, fetch_page(url)->html
│   ├── models.py             # dataclasses for every entity in §3
│   ├── parsers/
│   │   ├── teams.py          # teams directory fragment -> [team stub]
│   │   ├── profile.py        # team profile page -> (Team enrichment, Roster)
│   │   ├── fixtures.py       # fixtures fragment -> [Fixture]
│   │   ├── standings.py      # groups fragment -> [GroupStanding]
│   │   ├── scorers.py        # scorers fragment -> [Scorer]
│   │   └── bracket.py        # bracket fragment -> [BracketStage]
│   ├── writer.py             # dataclasses -> JSON (latest/ + snapshot/ + manifest)
│   └── run.py                # CLI orchestrator
├── projection/               # §8 possible-opponents feature (reads data/latest/*.json)
│   ├── load.py               # load teams.json + standings.json + bracket.json
│   ├── resolver.py           # slot label ("1st of Group A" / "Winner of M49") -> set[team]
│   ├── path.py               # per-team round-by-round possible opponents to the final
│   ├── run.py                # write projections.json for all teams
│   └── cli.py                # CLI entry point
├── dashboard/                # §9 Flask web dashboard (reads data/latest/*.json)
│   ├── app.py                # Flask app + routes
│   ├── data_access.py        # load + cache data/latest/*.json; freshness via manifest
│   ├── jobs.py               # background refresh job (subprocess) + status
│   ├── templates/            # base + overview/teams/team_detail/fixtures/standings/bracket/scorers
│   └── static/               # css/js (visual design sourced from ui-ux-pro-max)
├── data/
│   ├── latest/               # teams/fixtures/standings/rosters/scorers/bracket.json,
│   │                         #   projections.json (from projection.run), manifest.json
│   └── snapshots/<ISO-timestamp>/   # full copy of each run (tournament history)
└── tests/
    ├── fixtures_html/        # saved real HTML fragments/pages
    ├── fixtures_json/        # small sample data/latest set for projection + dashboard tests
    ├── test_parsers.py       # offline parser unit tests (§7)
    ├── test_projection.py    # resolver + path unit tests (§8)
    └── test_dashboard.py     # Flask route tests, subprocess stubbed (§9)
```

### Data flow (one run)
1. `run.py` parses CLI flags, builds a `Client`.
2. Fetch + parse the tab entities: teams directory, fixtures, standings, scorers, bracket.
3. For each of the 48 teams (unless `--no-rosters`), fetch the profile page → enrich `Team`
   (real `team_name`, captain) and build its `Roster`. Polite delay between requests.
4. `writer` writes each entity to `data/latest/`, copies the set into a timestamped
   `data/snapshots/<ts>/`, and writes `manifest.json`.

A **full refresh** = `scraper.run` then `projection.run` (which writes `projections.json` from the
freshly scraped data). This is the sequence the dashboard's background refresh button (§9) triggers.

### CLI
```
python -m scraper.run                          # scrape everything
python -m scraper.run --only fixtures standings
python -m scraper.run --no-rosters             # skip the 48 profile fetches (fast refresh)
python -m scraper.run --delay 1.0              # seconds between requests (default ~0.5)
python -m scraper.run --out ./data             # output root
```

## 5. Error handling & robustness

- **Per-entity isolation** — each entity is fetched/parsed/written independently. A failure in
  one (e.g. rosters) still writes the others and is recorded as `ok: false` + `error` in the manifest.
- **Parser guards** — a missing/renamed field yields `null` + a logged warning, never a crash.
  Parsers are written to tolerate both the empty (all-zero) and populated states.
- **HTTP** — `requests.Session` with a descriptive User-Agent, timeout, and retry-with-backoff
  (≈3 attempts) on transient errors.
- **Atomic-ish writes** — `latest/` is only overwritten by a successful entity write; the snapshot
  preserves whatever a run produced.

## 6. Politeness & ethics

- One full run is ≈54 small requests (6 tab fragments + 48 profile pages).
- Default ≈0.5s delay between requests, descriptive User-Agent, honor `robots.txt`.
- Read-only public tournament data; no login, no write endpoints, no personal-data harvesting
  beyond what the public roster pages already display.

## 7. Testing

Parsers are pure `html -> dataclass` functions. Representative real HTML (a fixtures fragment,
a groups fragment, one team profile, the bracket fragment, and the empty scorers panel) is saved
to `tests/fixtures_html/` and each parser is unit-tested offline against expected records —
covering both the empty pre-tournament state and a hand-edited "played" sample so live-result
parsing is verified before real matches happen. No network access in tests.

## 8. Possible-opponents projection ("path to the final")

A deterministic tool, in the `projection/` package, that reads `data/latest/` and answers: **for a
given team, which teams could they face at each knockout round on the way to the final?**

### Inputs
- `bracket.json` — the tree (`match_no` → `next_match_no`) and slot labels (`home_label`/`away_label`).
- `teams.json` — team → group (and country/team_name for display).
- `standings.json` — current group order, used to narrow slots once results exist.

### Slot resolution (`resolver.py`)
Resolve any slot **label** to the set of teams that could fill it, given current knowledge:
- `"1st of Group A"` / `"2nd of Group A"` → if standings for Group A are decided, the concrete team;
  otherwise every team in Group A (any could take that position).
- `"Winner of M49"` → recursively, the union of teams that can reach either side of match M49.
- A concrete resolved `home_team`/`away_team` (once the site fills it in) → that single team.

### Path computation (`path.py`)
For a chosen team T in group G:
1. Entry slots: the R32 match(es) whose label is `"1st of Group G"` or `"2nd of Group G"`. Pre-group-stage
   both are possible, so T may have two candidate paths (winner-of-group vs runner-up); report both,
   labelled. Once T's group position is decided, keep only the real one.
2. From each entry match, the **opponent slot** resolves (via `resolver.py`) to a set of possible teams
   → that round's possible opponents (T itself removed).
3. Follow `next_match_no` to the next round; the opponent there is `"Winner of M#"` of the sibling
   subtree → resolve to a set. Repeat up to the Final.
4. Emit, per round (R32, R16, QF, SF, Final), the set of possible opponents (as country + team_name).

The same code path works pre-tournament (large sets) and mid-tournament (sets collapse toward single
teams) because everything flows through slot resolution against current standings/results.

### CLI & output
```
python -m projection.cli --team "Netherlands"        # match by country, team_name, or slug
python -m projection.cli --team "CS Backbencher"
python -m projection.cli --all --json data/latest/projections.json
```
- Default: a readable round-by-round report to stdout (each round → the possible opponents).
- `--all --json <path>`: write `projections.json`, an object **keyed by team `id`** (matching the
  dashboard's `/teams/<id>` route), each value:
  `{ country, team_name, scenarios: { "group_winner"|"runner_up": [ {round, possible_opponents:[ {id, country, team_name} ] } ] } }`.
  Written to `data/latest/projections.json` by default.

### Testing
Pure functions over loaded JSON (no network). Unit-test `resolver.py` and `path.py` against a small
fixed bracket + group fixture, asserting the possible-opponent sets at each round for a sample team,
in both the pre-tournament (all groups open) and partially-resolved states.

## 9. Web dashboard (Flask)

A read-oriented Flask + Jinja2 app in `dashboard/` that visualizes `data/latest/*.json`. Visual
design is sourced from the **ui-ux-pro-max** skill at build time (user-accepted; sports-dashboard
direction: clean, modern, flag/badge-forward, responsive, light+dark).

### Data access (`data_access.py`)
Loads the entity JSON files, caches them in memory, and invalidates the cache when `manifest.json`'s
`scraped_at` changes. The dashboard never scrapes inline — it only reads files.

### Routes / views
- `/` **Overview** — tournament status (from manifest + fixtures), next matches, quick stats, refresh control.
- `/teams` — grid of all 48 teams showing **country + real team_name** + faculty + group; searchable.
- `/teams/<id>` **Team detail** — the roster (16 players + captain) **and the star view: the
  possible-opponents "path to the final"** (read from `projections.json`).
- `/fixtures` — all matches grouped by day, scores/status, searchable.
- `/standings` — the 16 group tables.
- `/bracket` — the knockout tree (R32→Final).
- `/scorers` — top scorers (empty-state until the first goal).

### Path-to-final view
For the selected team, render round-by-round cards (R32 → R16 → QF → SF → Final); each card lists the
**possible opponents** at that round (flag + country + real name). A team has up to two entry scenarios
(group winner vs runner-up) — show both, toggle-able. Data comes straight from `projections.json`;
no bracket logic in the browser. (Exact layout to be refined with ui-ux-pro-max during implementation.)

### Background refresh (`jobs.py`)
- `POST /refresh` starts a **background job** (subprocess running the full refresh: `scraper.run` +
  `projection.run`) and returns immediately; only one job runs at a time.
- `GET /refresh/status` reports job state (`idle`/`running`/`done`/`error`), start time, and per-entity
  counts on completion. The Overview page polls this (or uses SSE) to show progress, then reloads data.
- The HTTP request never blocks on the ~54-request scrape.

### Testing
Flask test client hits each route against a fixture `data/latest/` and asserts key content renders
(teams show both names, a team's path lists the expected opponent sets, empty-states don't crash).
The refresh job is tested with the subprocess stubbed.

## 10. Out of scope (YAGNI)

- A **probabilistic Monte Carlo** simulation / win-probability model (the §8 projection is deterministic).
- A database / diffing layer (timestamped JSON snapshots cover history).
- Scheduled/automated scraping (cron etc.); refresh is manual — CLI or the §9 button.
- Public hosting / auth / multi-user; the dashboard is a local single-user tool.
- Scraping `/matches/{id}` pages or `/players/{id}` pages (fixtures + rosters already carry the data).
- Overview-tab and fair-play tab scraping (derivable/aggregate; not needed here).
