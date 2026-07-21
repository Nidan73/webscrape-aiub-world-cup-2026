# AIUB World Cup 2026 Scraper — Design Spec

**Date:** 2026-07-21
**Status:** Approved (pending final spec review)
**Scope:** Scraper only. The simulation that consumes this data is out of scope.

## 1. Goal

Build a re-runnable Python scraper for **https://ofsportsaiub.org/** (the AIUB World Cup 2026
tournament portal) that produces clean, structured JSON of the full tournament dataset. Each run
captures the current state of the tournament (which starts 2026-07-28 and runs into early August),
so the data can seed and later refresh a match simulation.

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
BracketStage = { stage, matches: [ { slot, home, away, home_score, away_score, status } ] }
```

**manifest.json** (per run) — `{ scraped_at, source, entities: { <name>: { count, source_url, ok, error? } }, snapshot_dir }`

## 4. Architecture

Python 3, `requests` + `beautifulsoup4` + `lxml`, in a virtualenv.

```
ossport-scraper/
├── requirements.txt          # requests, beautifulsoup4, lxml
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
├── data/
│   ├── latest/               # teams/fixtures/standings/rosters/scorers/bracket.json + manifest.json
│   └── snapshots/<ISO-timestamp>/   # full copy of each run (tournament history)
└── tests/
    ├── fixtures_html/        # saved real HTML fragments/pages
    └── test_parsers.py       # offline parser unit tests (no network)
```

### Data flow (one run)
1. `run.py` parses CLI flags, builds a `Client`.
2. Fetch + parse the tab entities: teams directory, fixtures, standings, scorers, bracket.
3. For each of the 48 teams (unless `--no-rosters`), fetch the profile page → enrich `Team`
   (real `team_name`, captain) and build its `Roster`. Polite delay between requests.
4. `writer` writes each entity to `data/latest/`, copies the set into a timestamped
   `data/snapshots/<ts>/`, and writes `manifest.json`.

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

## 8. Out of scope (YAGNI)

- The simulation engine itself.
- A database / diffing layer (timestamped JSON snapshots cover history).
- Scheduling/automation (user runs the command when they want a refresh).
- Scraping `/matches/{id}` pages or `/players/{id}` pages (fixtures + rosters already carry the data).
- Overview and fair-play tabs (derivable/aggregate; not needed for simulation).
