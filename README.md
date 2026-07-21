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
