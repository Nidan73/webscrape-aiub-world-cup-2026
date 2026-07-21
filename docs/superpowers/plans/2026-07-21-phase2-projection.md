# AIUB World Cup Scraper — Phase 2 (Projection) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Given the scraped `data/latest/*.json`, compute for every team the set of opponents it could face at each knockout round on the way to the final, and write `projections.json`.

**Architecture:** A `Context` loaded from teams/standings/bracket JSON. A label resolver turns any bracket slot label (`"1st of Group A"`, `"Winner of M49"`, or a concrete team) into a set of possible team ids, recursing through the bracket tree with memoization. A path builder walks a team's route up the tree via `next_match_no`, emitting the sibling's possible teams as that round's opponents. Deterministic — no randomness, no ratings. It narrows automatically as real group results fill in.

**Tech Stack:** Python 3 standard library only (`json`, `re`, `argparse`, `dataclasses`). `pytest` for tests. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-07-21-aiub-world-cup-scraper-design.md` §8. **Depends on:** Phase 1 scraper output.

## Global Constraints

- Python 3.10+ (`X | None`, `set[str]`, `dict[int, dict]`).
- No network anywhere. Reads only `data/latest/*.json` (produced by `scraper.run`).
- **Deterministic:** possible-opponent sets, not probabilities.
- A team id is a `str` (matches `Team.id` from Phase 1). Opponent output items are `{id, country, team_name}`.
- `projections.json` is keyed by team `id`; each value `{country, team_name, scenarios: {"group_winner"|"runner_up": [ {round, possible_opponents:[...]} ]}}`.
- Real bracket facts (verified): R32 = M49–64 with `home_label="1st of Group X"`, `away_label="2nd of Group Y"`; R16=M65–72, QF=M73–76, SF=M77–78, Final=M79 with `"Winner of M#"` labels; `next_match_no` chains to M79 (Final has `next_match_no=None`).
- **Commit messages must NOT contain any `Co-Authored-By` or AI-tool trailer** (user directive). Plain `-m` only.
- Work on a feature branch, not `main`.

---

### Task 1: Context loader

**Files:**
- Create: `projection/__init__.py` (empty)
- Create: `projection/load.py`
- Test: `tests/test_projection_load.py`

**Interfaces:**
- Produces `Context` (dataclass) with fields: `teams: dict[str,dict]` (id → `{id,country,team_name,group}`), `group_members: dict[str,list[str]]`, `group_resolved: dict[str,list[str]|None]`, `matches: dict[int,dict]`, `team_id_by_name: dict[str,str]`, `_reach_memo: dict`. Method `team_brief(tid) -> {id,country,team_name}`.
- Produces `build_context(teams_list, standings_list, bracket_list) -> Context` and `load_context(data_dir) -> Context`.
- A group is **resolved** (positions known) iff its standings table is non-empty and every row has `played >= group_size-1` with `group_size>1`; then `group_resolved[group]` is the team-id list in standings order, else `None`.

- [ ] **Step 1: Write the failing test**

`tests/test_projection_load.py`:
```python
import json
from projection.load import build_context, load_context

TEAMS = [
    {"id": "a1", "country": "Alpha", "team_name": "AA", "group": "A"},
    {"id": "a2", "country": "Ares",  "team_name": "AR", "group": "A"},
    {"id": "b1", "country": "Bravo", "team_name": "BB", "group": "B"},
    {"id": "b2", "country": "Bern",  "team_name": "BE", "group": "B"},
]
BRACKET = [
    {"stage": "R32", "matches": [
        {"match_no": 1, "next_match_no": 3, "stage": "R32",
         "home_label": "1st of Group A", "away_label": "2nd of Group B",
         "home_team": None, "away_team": None},
        {"match_no": 2, "next_match_no": 3, "stage": "R32",
         "home_label": "1st of Group B", "away_label": "2nd of Group A",
         "home_team": None, "away_team": None},
    ]},
    {"stage": "Final", "matches": [
        {"match_no": 3, "next_match_no": None, "stage": "Final",
         "home_label": "Winner of M1", "away_label": "Winner of M2",
         "home_team": None, "away_team": None},
    ]},
]
UNRESOLVED = [
    {"group": "A", "table": [{"team_id": "a1", "played": 0}, {"team_id": "a2", "played": 0}]},
    {"group": "B", "table": [{"team_id": "b1", "played": 0}, {"team_id": "b2", "played": 0}]},
]
RESOLVED = [
    {"group": "A", "table": [{"team_id": "a1", "played": 1}, {"team_id": "a2", "played": 1}]},
    {"group": "B", "table": [{"team_id": "b1", "played": 1}, {"team_id": "b2", "played": 1}]},
]


def test_build_context_groups_and_names():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    assert ctx.group_members["A"] == ["a1", "a2"]
    assert ctx.group_resolved["A"] is None            # nobody has played -> unresolved
    assert set(ctx.matches) == {1, 2, 3}
    assert ctx.team_id_by_name["alpha"] == "a1" and ctx.team_id_by_name["aa"] == "a1"
    assert ctx.team_brief("b2") == {"id": "b2", "country": "Bern", "team_name": "BE"}


def test_resolved_group_orders_by_position():
    ctx = build_context(TEAMS, RESOLVED, BRACKET)
    assert ctx.group_resolved["A"] == ["a1", "a2"]     # size 2, need 1 game -> resolved
    assert ctx.group_resolved["B"] == ["b1", "b2"]


def test_load_context_reads_files(tmp_path):
    (tmp_path / "teams.json").write_text(json.dumps(TEAMS))
    (tmp_path / "standings.json").write_text(json.dumps(UNRESOLVED))
    (tmp_path / "bracket.json").write_text(json.dumps(BRACKET))
    ctx = load_context(str(tmp_path))
    assert set(ctx.matches) == {1, 2, 3} and ctx.group_members["B"] == ["b1", "b2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_projection_load.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'projection'`).

- [ ] **Step 3: Write `projection/__init__.py` (empty) and `projection/load.py`**

```python
"""Load data/latest JSON into a Context for the projection engine."""
import json
import os
from dataclasses import dataclass, field


@dataclass
class Context:
    teams: dict            # id -> {id, country, team_name, group}
    group_members: dict    # group -> [id]
    group_resolved: dict   # group -> [id ordered by position] or None
    matches: dict          # match_no(int) -> match dict
    team_id_by_name: dict  # lowercased country/team_name -> id
    _reach_memo: dict = field(default_factory=dict)

    def team_brief(self, tid):
        t = self.teams[tid]
        return {"id": t["id"], "country": t["country"], "team_name": t["team_name"]}


def build_context(teams_list, standings_list, bracket_list) -> Context:
    teams, group_members, team_id_by_name = {}, {}, {}
    for t in teams_list:
        tid = t["id"]
        teams[tid] = {"id": tid, "country": t.get("country"),
                      "team_name": t.get("team_name"), "group": t.get("group")}
        group_members.setdefault(t.get("group"), []).append(tid)
        if t.get("country"):
            team_id_by_name[t["country"].lower()] = tid
        if t.get("team_name"):
            team_id_by_name[t["team_name"].lower()] = tid

    group_resolved = {}
    for gs in standings_list:
        group = gs.get("group")
        table = gs.get("table", [])
        size = len(group_members.get(group, [])) or len(table)
        need = size - 1
        decided = bool(table) and need > 0 and all((row.get("played") or 0) >= need for row in table)
        group_resolved[group] = [row.get("team_id") for row in table] if decided else None

    matches = {}
    for stage in bracket_list:
        for m in stage.get("matches", []):
            if m.get("match_no") is not None:
                matches[m["match_no"]] = m

    return Context(teams=teams, group_members=group_members, group_resolved=group_resolved,
                   matches=matches, team_id_by_name=team_id_by_name)


def load_context(data_dir) -> Context:
    def _load(name):
        with open(os.path.join(data_dir, name), encoding="utf-8") as fh:
            return json.load(fh)
    return build_context(_load("teams.json"), _load("standings.json"), _load("bracket.json"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_projection_load.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add projection/__init__.py projection/load.py tests/test_projection_load.py
git commit -m "feat(projection): context loader from scraped JSON"
```

---

### Task 2: Label resolver

**Files:**
- Create: `projection/resolver.py`
- Test: `tests/test_projection_resolver.py`

**Interfaces:**
- Consumes: `projection.load.Context`.
- Produces: `resolve(label: str | None, ctx) -> set[str]`, `reach_set(match_no: int, ctx) -> set[str]`, `_side_set(match: dict, side: str, ctx) -> set[str]` (`side` is `"home"`/`"away"`; uses concrete `<side>_team` if present else `<side>_label`). `reach_set` memoizes on `ctx._reach_memo`.

- [ ] **Step 1: Write the failing test**

`tests/test_projection_resolver.py`:
```python
from projection.load import build_context
from projection.resolver import resolve, reach_set
from tests.test_projection_load import TEAMS, BRACKET, UNRESOLVED, RESOLVED


def test_group_seed_unresolved_is_whole_group():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    assert resolve("1st of Group A", ctx) == {"a1", "a2"}
    assert resolve("2nd of Group B", ctx) == {"b1", "b2"}


def test_group_seed_resolved_is_single_team():
    ctx = build_context(TEAMS, RESOLVED, BRACKET)
    assert resolve("1st of Group A", ctx) == {"a1"}
    assert resolve("2nd of Group B", ctx) == {"b2"}


def test_winner_label_recurses_through_tree():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    # Winner of M1 = teams that can reach M1 = (1st A) U (2nd B)
    assert reach_set(1, ctx) == {"a1", "a2", "b1", "b2"}
    assert resolve("Winner of M1", ctx) == {"a1", "a2", "b1", "b2"}


def test_concrete_name_and_empty():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    assert resolve("Alpha", ctx) == {"a1"}       # by country
    assert resolve("BE", ctx) == {"b2"}           # by team_name
    assert resolve("", ctx) == set() and resolve(None, ctx) == set()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_projection_resolver.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'projection.resolver'`).

- [ ] **Step 3: Write `projection/resolver.py`**

```python
"""Resolve bracket slot labels to sets of possible team ids."""
import re

_GROUP_SEED = re.compile(r"^\s*(\d+)(?:st|nd|rd|th)\s+of\s+group\s+([a-p])\s*$", re.I)
_WINNER = re.compile(r"^\s*winner of m(\d+)\s*$", re.I)


def _side_set(match, side, ctx):
    concrete = match.get(f"{side}_team")
    if concrete:
        tid = ctx.team_id_by_name.get(concrete.strip().lower())
        return {tid} if tid else set()
    return resolve(match.get(f"{side}_label"), ctx)


def resolve(label, ctx):
    if not label:
        return set()
    m = _GROUP_SEED.match(label)
    if m:
        pos = int(m.group(1))
        group = m.group(2).upper()
        resolved = ctx.group_resolved.get(group)
        if resolved and 0 <= pos - 1 < len(resolved) and resolved[pos - 1]:
            return {resolved[pos - 1]}
        return set(ctx.group_members.get(group, []))
    w = _WINNER.match(label)
    if w:
        return reach_set(int(w.group(1)), ctx)
    tid = ctx.team_id_by_name.get(label.strip().lower())
    return {tid} if tid else set()


def reach_set(match_no, ctx):
    if match_no in ctx._reach_memo:
        return ctx._reach_memo[match_no]
    ctx._reach_memo[match_no] = set()          # cycle guard (tree has none, but safe)
    m = ctx.matches.get(match_no)
    if not m:
        return set()
    result = _side_set(m, "home", ctx) | _side_set(m, "away", ctx)
    ctx._reach_memo[match_no] = result
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_projection_resolver.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add projection/resolver.py tests/test_projection_resolver.py
git commit -m "feat(projection): label resolver with memoized reachability"
```

---

### Task 3: Path builder

**Files:**
- Create: `projection/path.py`
- Test: `tests/test_projection_path.py`

**Interfaces:**
- Consumes: `projection.resolver._side_set`, `resolve`, `reach_set`; `Context`.
- Produces:
  - `entry_matches(team: dict, ctx) -> list[tuple[dict, str, str]]` — `(match, my_side, scenario)` where scenario ∈ `{"group_winner","runner_up"}`.
  - `path_for_entry(entry: dict, my_side: str, team_id: str, ctx) -> list[dict]` — `[{round, possible_opponents:set[str]}]`.
  - `project_team(team_id: str, ctx) -> dict` — `{country, team_name, scenarios:{scenario:[{round, possible_opponents:[brief,...]}]}}` (opponents sorted by country, `team_id` excluded).

- [ ] **Step 1: Write the failing test**

`tests/test_projection_path.py`:
```python
from projection.load import build_context
from projection.path import entry_matches, project_team
from tests.test_projection_load import TEAMS, BRACKET, UNRESOLVED, RESOLVED


def _opp_ids(rounds, rnd):
    row = next(r for r in rounds if r["round"] == rnd)
    return {o["id"] for o in row["possible_opponents"]}


def test_entry_matches_two_scenarios():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    a1 = ctx.teams["a1"]
    entries = entry_matches(a1, ctx)
    scenarios = {scen: (m["match_no"], side) for m, side, scen in entries}
    assert scenarios == {"group_winner": (1, "home"), "runner_up": (2, "away")}


def test_project_team_unresolved_sets():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    proj = project_team("a1", ctx)
    gw = proj["scenarios"]["group_winner"]
    assert _opp_ids(gw, "R32") == {"b1", "b2"}            # opponent = 2nd of Group B
    assert _opp_ids(gw, "Final") == {"a2", "b1", "b2"}    # winner of M2 minus self
    ru = proj["scenarios"]["runner_up"]
    assert _opp_ids(ru, "R32") == {"b1", "b2"}            # opponent = 1st of Group B
    assert _opp_ids(ru, "Final") == {"a2", "b1", "b2"}


def test_project_team_resolved_narrows():
    ctx = build_context(TEAMS, RESOLVED, BRACKET)
    proj = project_team("a1", ctx)
    gw = proj["scenarios"]["group_winner"]
    assert _opp_ids(gw, "R32") == {"b2"}                  # 2nd of B is now exactly b2
    assert _opp_ids(gw, "Final") == {"a2", "b1"}          # winner of M2 = 1st B (b1) or 2nd A (a2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_projection_path.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'projection.path'`).

- [ ] **Step 3: Write `projection/path.py`**

```python
"""Build a team's round-by-round possible opponents up to the final."""
from projection.resolver import _side_set


def entry_matches(team, ctx):
    """R32 matches a team can enter, with the side it occupies and the scenario."""
    g = team["group"]
    out = []
    for m in ctx.matches.values():
        if m.get("stage") != "R32":
            continue
        if m.get("home_label") == f"1st of Group {g}":
            out.append((m, "home", "group_winner"))
        if m.get("away_label") == f"2nd of Group {g}":
            out.append((m, "away", "runner_up"))
    return out


def path_for_entry(entry, my_side, team_id, ctx):
    rounds = []
    opp_side = "away" if my_side == "home" else "home"
    rounds.append({"round": entry["stage"],
                   "possible_opponents": _side_set(entry, opp_side, ctx) - {team_id}})
    cur = entry
    while cur.get("next_match_no"):
        parent = ctx.matches.get(cur["next_match_no"])
        if not parent:
            break
        winner_label = f"Winner of M{cur['match_no']}"
        opp_side = "away" if parent.get("home_label") == winner_label else "home"
        rounds.append({"round": parent["stage"],
                       "possible_opponents": _side_set(parent, opp_side, ctx) - {team_id}})
        cur = parent
    return rounds


def project_team(team_id, ctx):
    team = ctx.teams[team_id]
    scenarios = {}
    for entry, side, scenario in entry_matches(team, ctx):
        rounds = path_for_entry(entry, side, team_id, ctx)
        scenarios[scenario] = [
            {"round": r["round"],
             "possible_opponents": [
                 ctx.team_brief(t)
                 for t in sorted(r["possible_opponents"], key=lambda i: (ctx.teams[i]["country"] or ""))
             ]}
            for r in rounds
        ]
    return {"country": team["country"], "team_name": team["team_name"], "scenarios": scenarios}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_projection_path.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add projection/path.py tests/test_projection_path.py
git commit -m "feat(projection): per-team path-to-final opponent sets"
```

---

### Task 4: Projections writer

**Files:**
- Create: `projection/run.py`
- Test: `tests/test_projection_run.py`

**Interfaces:**
- Consumes: `load_context`, `project_team`, `Context`.
- Produces: `build_projections(ctx) -> dict` (keyed by team id), `write_projections(ctx, out_path) -> dict`, and `main(argv=None)` (`python -m projection.run`).

- [ ] **Step 1: Write the failing test**

`tests/test_projection_run.py`:
```python
import json
from projection.load import build_context
from projection.run import build_projections, write_projections
from tests.test_projection_load import TEAMS, BRACKET, UNRESOLVED


def test_build_projections_covers_all_teams():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    data = build_projections(ctx)
    assert set(data) == {"a1", "a2", "b1", "b2"}
    assert data["a1"]["country"] == "Alpha"
    assert set(data["a1"]["scenarios"]) == {"group_winner", "runner_up"}


def test_write_projections_roundtrips(tmp_path):
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    out = tmp_path / "projections.json"
    write_projections(ctx, str(out))
    loaded = json.loads(out.read_text())
    rounds = loaded["a1"]["scenarios"]["group_winner"]
    assert [r["round"] for r in rounds] == ["R32", "Final"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_projection_run.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'projection.run'`).

- [ ] **Step 3: Write `projection/run.py`**

```python
"""Build projections.json for every team from the scraped data."""
import argparse
import json
import logging
import os

from projection.load import load_context
from projection.path import project_team

log = logging.getLogger(__name__)


def build_projections(ctx) -> dict:
    return {tid: project_team(tid, ctx) for tid in ctx.teams}


def write_projections(ctx, out_path) -> dict:
    data = build_projections(ctx)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build possible-opponents projections.")
    ap.add_argument("--data", default="./data/latest", help="input dir with the scraped *.json")
    ap.add_argument("--out", default="./data/latest/projections.json")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ctx = load_context(args.data)
    data = write_projections(ctx, args.out)
    print(f"projections for {len(data)} teams -> {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_projection_run.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add projection/run.py tests/test_projection_run.py
git commit -m "feat(projection): projections.json writer"
```

---

### Task 5: CLI + live run + README

**Files:**
- Create: `projection/cli.py`
- Test: `tests/test_projection_cli.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `load_context`, `project_team`, `write_projections`, `Context`.
- Produces: `find_team_id(ctx, query) -> str | None`, `render_team(ctx, team_id) -> str`, `main(argv=None)` (`python -m projection.cli --team NAME | --all`).

- [ ] **Step 1: Write the failing test**

`tests/test_projection_cli.py`:
```python
import json
from projection.load import build_context
from projection.cli import find_team_id, render_team
from tests.test_projection_load import TEAMS, BRACKET, UNRESOLVED


def test_find_team_id_by_country_and_name():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    assert find_team_id(ctx, "Alpha") == "a1"
    assert find_team_id(ctx, "be") == "b2"          # by real team_name, case-insensitive
    assert find_team_id(ctx, "nope") is None


def test_render_team_mentions_rounds_and_opponents():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    text = render_team(ctx, "a1")
    assert "Alpha" in text and "GROUP WINNER" in text and "RUNNER-UP" in text
    assert "R32" in text and "Final" in text
    assert "Bravo" in text            # a possible opponent country appears
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_projection_cli.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'projection.cli'`).

- [ ] **Step 3: Write `projection/cli.py`**

```python
"""CLI: print a team's path to the final, or write projections.json for all."""
import argparse

from projection.load import load_context
from projection.path import project_team
from projection.run import write_projections

_SCENARIO_LABEL = {"group_winner": "AS GROUP WINNER", "runner_up": "AS RUNNER-UP"}


def find_team_id(ctx, query):
    q = query.strip().lower()
    for tid, t in ctx.teams.items():
        if (t.get("country") or "").lower() == q or (t.get("team_name") or "").lower() == q:
            return tid
    for tid, t in ctx.teams.items():
        if q and (q in (t.get("country") or "").lower() or q in (t.get("team_name") or "").lower()):
            return tid
    return None


def _fmt_opponents(opps):
    if not opps:
        return "(none)"
    return ", ".join(
        o["country"] + (f" [{o['team_name']}]" if o.get("team_name") else "")
        for o in opps
    )


def render_team(ctx, team_id) -> str:
    t = ctx.teams[team_id]
    proj = project_team(team_id, ctx)
    title = t["country"] + (f" ({t['team_name']})" if t.get("team_name") else "")
    lines = [f"{title} — Group {t['group']} — path to the final", ""]
    for scen, rounds in proj["scenarios"].items():
        lines.append(_SCENARIO_LABEL.get(scen, scen))
        for r in rounds:
            lines.append(f"  {r['round']:6s} vs any of: {_fmt_opponents(r['possible_opponents'])}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Possible-opponents projection.")
    ap.add_argument("--data", default="./data/latest")
    ap.add_argument("--team", help="team by country or real name")
    ap.add_argument("--all", action="store_true", help="write projections.json for all teams")
    ap.add_argument("--json", default="./data/latest/projections.json")
    args = ap.parse_args(argv)

    ctx = load_context(args.data)
    if args.all:
        data = write_projections(ctx, args.json)
        print(f"projections for {len(data)} teams -> {args.json}")
        return
    if not args.team:
        ap.error("provide --team NAME or --all")
    tid = find_team_id(ctx, args.team)
    if not tid:
        ap.error(f"team not found: {args.team!r}")
    print(render_team(ctx, tid))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_projection_cli.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Full suite + live run against real data**

Run: `./venv/bin/pytest -q`
Expected: all Phase 1 + Phase 2 tests pass.

Ensure scraped data exists, then run the real projection:
```bash
./venv/bin/python -m scraper.run --no-rosters   # refresh teams/standings/bracket if needed
./venv/bin/python -m projection.cli --team "Netherlands"
./venv/bin/python -m projection.cli --all
```
Expected: the `--team` call prints two scenarios (group winner / runner-up), each listing R32→Final with possible opponents; `--all` reports `projections for 48 teams -> ./data/latest/projections.json`. Spot-check:
```bash
./venv/bin/python -c "import json; d=json.load(open('data/latest/projections.json')); k=next(iter(d)); print(len(d),'teams'); print(d[k]['country'], list(d[k]['scenarios']), [r['round'] for r in d[k]['scenarios']['group_winner']])"
```
Expected: `48 teams` and rounds `['R32','R16','QF','SF','Final']`.

- [ ] **Step 6: Update README and commit**

Add under the Scraper section of `README.md`:
```markdown
## Projection — who can a team face on the way to the final?

```bash
./venv/bin/python -m projection.cli --team "Netherlands"   # or a real team name, e.g. "CS Backbencher"
./venv/bin/python -m projection.cli --all                  # writes data/latest/projections.json
```

For each team it lists, per knockout round (R32→Final), the set of teams it *could* meet — as group
winner and as runner-up. Deterministic; the sets shrink automatically as real group results come in.
```

Then:
```bash
git add projection/cli.py tests/test_projection_cli.py README.md
git commit -m "feat(projection): CLI path-to-final report and live run"
```

---

## Self-Review

**1. Spec coverage (§8):**
- Inputs bracket/teams/standings → Task 1 (`load_context`). ✓
- Slot resolution (group seed resolved/unresolved, "Winner of M#", concrete team) → Task 2. ✓
- Path computation (two entry scenarios, opponent per round via sibling, up to Final) → Task 3. ✓
- `projections.json` keyed by team id with the specified shape → Tasks 3–4. ✓
- CLI `--team` (by country/team_name) and `--all --json` → Task 5. ✓
- Works pre-tournament (whole groups) and partially resolved (narrowed) → tested in Tasks 2 & 3. ✓
- Deterministic, stdlib only, no network → all tests offline. ✓

**2. Placeholder scan:** No TBD/TODO; every step has real code or an exact command with expected output.

**3. Type consistency:** `Context` fields and `team_brief` are used identically across `resolver`, `path`, `run`, `cli`. `_side_set(match, side, ctx)`, `resolve(label, ctx)`, `reach_set(match_no, ctx)`, `project_team(team_id, ctx)`, `build_projections(ctx)`, `write_projections(ctx, out_path)`, `find_team_id(ctx, query)`, `render_team(ctx, team_id)` signatures match every call site. Scenario keys `"group_winner"`/`"runner_up"` and round labels (`R32`,`R16`,`QF`,`SF`,`Final`) are consistent between path output, tests, and CLI.
