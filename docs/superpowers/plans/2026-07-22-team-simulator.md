# Team Simulator + Dashboard Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a team-wise opponent simulator (Possible / What-if / Monte Carlo) with server-side JSON history, and polish the Flask dashboard to match the design system.

**Architecture:** New pure-Python `simulation/` package (strength, what-if, Monte Carlo, JSON store) sits beside existing `projection/`. Flask gains thin `/api/sim/*` routes and a redesigned `/teams/<id>` hub with mutually exclusive mode panels. Scraper refresh continues to write only `data/latest/`; simulator state lives in `data/simulations/`.

**Tech Stack:** Python 3.10+, existing `projection` + Flask + Jinja2, vanilla JS, pytest. No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-07-22-team-simulator-design.md`

## Global Constraints

- `simulation/` must **not** import Flask.
- Reuse `projection.load.Context`, `projection.path.project_team`, and resolver semantics — do not reimplement bracket label math in the dashboard.
- `data/simulations/` must never be deleted or rewritten by `RefreshJob` / scraper.
- Monte Carlo: default `n=1000`, reject `n > 10000` with HTTP 400; accept `seed` for tests.
- Bias ∈ `[0.0, 1.0]`; strength blend: `p = (1-bias)*p_uniform + bias*p_strength` then renormalize.
- What-if v1 picks only: per-group `1st`/`2nd` team ids + per-match KO `winner` team id. No match scores.
- History: auto snapshots capped at **50** FIFO; named saves until deleted; atomic write + file lock.
- UI: one mode panel visible at a time; history drawer closed by default; pre-tournament strength banner copy exact: `Using equal strength — no group results yet`
- API errors: `{ "ok": false, "error": "<message>" }` with 4xx.
- Design tokens via CSS variables only (no raw hex in templates); honor `prefers-reduced-motion`.
- Commit messages must **NOT** contain `Co-Authored-By` or AI-tool trailers.
- Prefer working on a feature branch (e.g. `feat/team-simulator`), not force-pushing `main`.

### File map

| Path | Responsibility |
|------|----------------|
| `simulation/__init__.py` | Package marker |
| `simulation/strength.py` | Hybrid strengths + weighted choice |
| `simulation/store.py` | ratings/current/history JSON I/O |
| `simulation/whatif.py` | Apply picks → project focus team |
| `simulation/montecarlo.py` | N trials → reach % + opponent freqs |
| `dashboard/app.py` | Register sim APIs; enrich team_detail |
| `dashboard/sim_api.py` | Flask blueprints/handlers for sim (keep `app.py` thin) |
| `dashboard/templates/team_detail.html` | Mode switcher + panels + history drawer |
| `dashboard/static/js/sim.js` | What-if / MC / history client |
| `dashboard/static/css/style.css` | Polish + sim UI styles |
| `dashboard/templates/*.html` | Empty-state + layout polish |
| `tests/test_simulation_*.py` | Engine + store tests |
| `tests/test_sim_api.py` | Flask API tests |
| `README.md` | Document simulator usage |

### Shared test fixtures

Reuse shapes from `tests/test_projection_load.py` (`TEAMS`, `BRACKET`, `UNRESOLVED`, `RESOLVED`). Import them in new tests instead of duplicating when possible.

---

### Task 1: Strength model

**Files:**
- Create: `simulation/__init__.py`
- Create: `simulation/strength.py`
- Test: `tests/test_simulation_strength.py`

**Interfaces:**
- Produces:
  - `standings_have_signal(standings_list: list) -> bool`
  - `team_strengths(standings_list: list, overrides: dict[str, float] | None = None) -> dict[str, float]`
  - `blend_probs(weights: list[float], bias: float) -> list[float]` — len matches weights; sums to 1.0
  - `weighted_choice(rng, candidates: list[str], strengths: dict[str, float], bias: float) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_simulation_strength.py
from simulation.strength import standings_have_signal, team_strengths, blend_probs, weighted_choice
import random

EMPTY = [
    {"group": "A", "table": [
        {"team_id": "a1", "played": 0, "points": 0, "goal_diff": 0, "goals_for": 0},
        {"team_id": "a2", "played": 0, "points": 0, "goal_diff": 0, "goals_for": 0},
    ]},
]
PLAYED = [
    {"group": "A", "table": [
        {"team_id": "a1", "played": 2, "points": 6, "goal_diff": 4, "goals_for": 5},
        {"team_id": "a2", "played": 2, "points": 0, "goal_diff": -4, "goals_for": 1},
    ]},
]


def test_no_signal_when_all_zero():
    assert standings_have_signal(EMPTY) is False
    s = team_strengths(EMPTY)
    assert s["a1"] == s["a2"] == 1.0


def test_signal_from_points():
    assert standings_have_signal(PLAYED) is True
    s = team_strengths(PLAYED)
    assert s["a1"] > s["a2"]


def test_overrides_replace_base():
    s = team_strengths(EMPTY, overrides={"a2": 9.0})
    assert s["a2"] == 9.0 and s["a1"] == 1.0


def test_blend_bias_zero_is_uniform():
    p = blend_probs([9.0, 1.0], bias=0.0)
    assert abs(p[0] - 0.5) < 1e-9 and abs(p[1] - 0.5) < 1e-9


def test_blend_bias_one_follows_strength():
    p = blend_probs([9.0, 1.0], bias=1.0)
    assert abs(p[0] - 0.9) < 1e-9 and abs(p[1] - 0.1) < 1e-9


def test_weighted_choice_deterministic_with_seed():
    strengths = {"a1": 1.0, "a2": 9.0}
    rng = random.Random(0)
    picks = [weighted_choice(rng, ["a1", "a2"], strengths, bias=1.0) for _ in range(200)]
    assert picks.count("a2") > picks.count("a1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_simulation_strength.py -v`  
Expected: FAIL (`ModuleNotFoundError: No module named 'simulation'`).

- [ ] **Step 3: Implement**

```python
# simulation/__init__.py
# empty

# simulation/strength.py
"""Hybrid team strength and bias-blended sampling."""
from __future__ import annotations


def standings_have_signal(standings_list: list) -> bool:
    for gs in standings_list or []:
        for row in gs.get("table") or []:
            if (row.get("played") or 0) > 0 or (row.get("points") or 0) > 0:
                return True
            if (row.get("goal_diff") or 0) != 0 or (row.get("goals_for") or 0) > 0:
                return True
    return False


def team_strengths(standings_list: list, overrides: dict | None = None) -> dict[str, float]:
    overrides = overrides or {}
    out: dict[str, float] = {}
    signal = standings_have_signal(standings_list)
    for gs in standings_list or []:
        for row in gs.get("table") or []:
            tid = row.get("team_id")
            if not tid:
                continue
            if signal:
                pts = float(row.get("points") or 0)
                gd = float(row.get("goal_diff") or 0)
                gf = float(row.get("goals_for") or 0)
                # Strictly positive weight: pts primary, small GD/GF tie-break.
                out[tid] = max(0.01, 1.0 + pts + 0.1 * gd + 0.01 * gf)
            else:
                out[tid] = 1.0
    for tid, val in overrides.items():
        out[str(tid)] = float(val)
    return out


def blend_probs(weights: list[float], bias: float) -> list[float]:
    n = len(weights)
    if n == 0:
        return []
    bias = max(0.0, min(1.0, float(bias)))
    pos = [max(0.0, float(w)) for w in weights]
    if sum(pos) <= 0:
        pos = [1.0] * n
    s = sum(pos)
    p_s = [w / s for w in pos]
    p_u = [1.0 / n] * n
    mixed = [(1 - bias) * u + bias * st for u, st in zip(p_u, p_s)]
    tot = sum(mixed) or 1.0
    return [m / tot for m in mixed]


def weighted_choice(rng, candidates: list[str], strengths: dict[str, float], bias: float) -> str:
    if not candidates:
        raise ValueError("candidates must be non-empty")
    weights = [float(strengths.get(c, 1.0)) for c in candidates]
    probs = blend_probs(weights, bias)
    r = rng.random()
    acc = 0.0
    for c, p in zip(candidates, probs):
        acc += p
        if r <= acc:
            return c
    return candidates[-1]
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `./venv/bin/pytest tests/test_simulation_strength.py -v`

- [ ] **Step 5: Commit**

```bash
git add simulation/__init__.py simulation/strength.py tests/test_simulation_strength.py
git commit -m "feat(simulation): hybrid strength model and bias-blended sampling"
```

---

### Task 2: Simulation JSON store

**Files:**
- Create: `simulation/store.py`
- Test: `tests/test_simulation_store.py`

**Interfaces:**
- Produces `SimStore(root_dir: str)` with:
  - `ensure() -> None`
  - `get_ratings() -> dict` / `put_ratings(data: dict) -> dict`
  - `get_current() -> dict` / `put_current(data: dict) -> dict`
  - Default current: `{"whatif": {"groups": {}, "ko": {}}, "mc": {"n": 1000, "bias": 0.0, "use_current_picks": true}}`
  - `list_history() -> list[dict]`
  - `save_history(*, type: str, title: str, payload: dict, team_id: str | None = None) -> dict` — `type` in `{"auto","named"}`; writes file + index; enforces auto cap 50
  - `get_history(id: str) -> dict | None`
  - `restore(id: str) -> dict` — loads into current (+ ratings if present); returns restored payload
  - `rename(id: str, title: str) -> dict`
  - `delete(id: str) -> bool`

Payload shape for history files:
`{id, type, title, created_at, team_id?, ratings, whatif, mc, mc_summary?}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_simulation_store.py
from simulation.store import SimStore


def test_defaults_when_missing(tmp_path):
    s = SimStore(str(tmp_path / "sim"))
    assert s.get_ratings() == {}
    cur = s.get_current()
    assert cur["mc"]["n"] == 1000 and cur["whatif"]["groups"] == {}


def test_ratings_roundtrip(tmp_path):
    s = SimStore(str(tmp_path / "sim"))
    s.put_ratings({"a1": 2.5})
    assert s.get_ratings()["a1"] == 2.5


def test_named_and_auto_history(tmp_path):
    s = SimStore(str(tmp_path / "sim"))
    s.put_ratings({"a1": 1})
    s.put_current({"whatif": {"groups": {"A": {"first": "a1", "second": "a2"}}, "ko": {}},
                   "mc": {"n": 500, "bias": 0.2, "use_current_picks": True}})
    named = s.save_history(type="named", title="Upset path", payload={
        "ratings": s.get_ratings(), "whatif": s.get_current()["whatif"],
        "mc": s.get_current()["mc"]}, team_id="a1")
    auto = s.save_history(type="auto", title="auto", payload={
        "ratings": {}, "whatif": {"groups": {}, "ko": {}},
        "mc": {"n": 1000, "bias": 0.0, "use_current_picks": True}})
    ids = {h["id"] for h in s.list_history()}
    assert named["id"] in ids and auto["id"] in ids
    s.rename(named["id"], "Renamed")
    assert s.get_history(named["id"])["title"] == "Renamed"
    s.restore(named["id"])
    assert s.get_current()["whatif"]["groups"]["A"]["first"] == "a1"
    assert s.delete(auto["id"]) is True
    assert s.get_history(auto["id"]) is None


def test_auto_cap_50(tmp_path):
    s = SimStore(str(tmp_path / "sim"))
    for i in range(55):
        s.save_history(type="auto", title=f"a{i}", payload={
            "ratings": {}, "whatif": {"groups": {}, "ko": {}},
            "mc": {"n": 1000, "bias": 0.0, "use_current_picks": True}})
    autos = [h for h in s.list_history() if h["type"] == "auto"]
    assert len(autos) == 50
```

- [ ] **Step 2: Run — expect FAIL** (`No module named 'simulation.store'` or import error).

- [ ] **Step 3: Implement `simulation/store.py`**

```python
"""Server-side JSON persistence for simulator state and history."""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path

_DEFAULT_CURRENT = {
    "whatif": {"groups": {}, "ko": {}},
    "mc": {"n": 1000, "bias": 0.0, "use_current_picks": True},
}
_AUTO_CAP = 50
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class SimStore:
    def __init__(self, root_dir: str):
        self.root = Path(root_dir)
        self.history_dir = self.root / "history"
        self._lock = threading.Lock()
        self.ensure()

    def ensure(self) -> None:
        self.history_dir.mkdir(parents=True, exist_ok=True)
        if not (self.root / "ratings.json").exists():
            self._atomic_write(self.root / "ratings.json", {})
        if not (self.root / "current.json").exists():
            self._atomic_write(self.root / "current.json", _DEFAULT_CURRENT)
        if not (self.root / "index.json").exists():
            self._atomic_write(self.root / "index.json", [])

    def _atomic_write(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def _read(self, path: Path, default):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return default

    def get_ratings(self) -> dict:
        with self._lock:
            self.ensure()
            data = self._read(self.root / "ratings.json", {})
            return data if isinstance(data, dict) else {}

    def put_ratings(self, data: dict) -> dict:
        with self._lock:
            self.ensure()
            clean = {str(k): float(v) for k, v in (data or {}).items()}
            self._atomic_write(self.root / "ratings.json", clean)
            return clean

    def get_current(self) -> dict:
        with self._lock:
            self.ensure()
            data = self._read(self.root / "current.json", _DEFAULT_CURRENT)
            if not isinstance(data, dict):
                return json.loads(json.dumps(_DEFAULT_CURRENT))
            data.setdefault("whatif", {"groups": {}, "ko": {}})
            data["whatif"].setdefault("groups", {})
            data["whatif"].setdefault("ko", {})
            data.setdefault("mc", dict(_DEFAULT_CURRENT["mc"]))
            return data

    def put_current(self, data: dict) -> dict:
        with self._lock:
            self.ensure()
            cur = {
                "whatif": (data or {}).get("whatif") or {"groups": {}, "ko": {}},
                "mc": {**_DEFAULT_CURRENT["mc"], **((data or {}).get("mc") or {})},
            }
            self._atomic_write(self.root / "current.json", cur)
            return cur

    def list_history(self) -> list:
        with self._lock:
            self.ensure()
            idx = self._read(self.root / "index.json", [])
            return idx if isinstance(idx, list) else []

    def _slug(self, title: str) -> str:
        s = _SLUG_RE.sub("-", (title or "scenario").lower()).strip("-") or "scenario"
        return s[:40]

    def save_history(self, *, type: str, title: str, payload: dict, team_id: str | None = None) -> dict:
        if type not in ("auto", "named"):
            raise ValueError("type must be auto or named")
        with self._lock:
            self.ensure()
            ts = time.strftime("%Y%m%d-%H%M%S")
            hid = f"{type}-{ts}-{uuid.uuid4().hex[:8]}"
            entry = {
                "id": hid,
                "type": type,
                "title": title or hid,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "team_id": team_id,
                "ratings": (payload or {}).get("ratings") or {},
                "whatif": (payload or {}).get("whatif") or {"groups": {}, "ko": {}},
                "mc": (payload or {}).get("mc") or dict(_DEFAULT_CURRENT["mc"]),
            }
            if "mc_summary" in (payload or {}):
                entry["mc_summary"] = payload["mc_summary"]
            fname = f"{hid}.json" if type == "auto" else f"named-{self._slug(title)}-{uuid.uuid4().hex[:6]}.json"
            # keep id as filename stem for lookup
            if type == "named":
                hid = Path(fname).stem
                entry["id"] = hid
            path = self.history_dir / f"{entry['id']}.json"
            self._atomic_write(path, entry)
            idx = self._read(self.root / "index.json", [])
            if not isinstance(idx, list):
                idx = []
            meta = {k: entry[k] for k in ("id", "type", "title", "created_at", "team_id")}
            idx.insert(0, meta)
            # cap autos
            autos = [h for h in idx if h.get("type") == "auto"]
            drop = autos[_AUTO_CAP:]
            drop_ids = {h["id"] for h in drop}
            idx = [h for h in idx if h["id"] not in drop_ids]
            for did in drop_ids:
                p = self.history_dir / f"{did}.json"
                if p.exists():
                    p.unlink()
            self._atomic_write(self.root / "index.json", idx)
            return entry

    def get_history(self, id: str):
        with self._lock:
            path = self.history_dir / f"{id}.json"
            if not path.exists():
                return None
            data = self._read(path, None)
            return data if isinstance(data, dict) else None

    def restore(self, id: str) -> dict:
        with self._lock:
            path = self.history_dir / f"{id}.json"
            data = self._read(path, None)
            if not isinstance(data, dict):
                raise KeyError(id)
            ratings = data.get("ratings") or {}
            current = {
                "whatif": data.get("whatif") or {"groups": {}, "ko": {}},
                "mc": {**_DEFAULT_CURRENT["mc"], **(data.get("mc") or {})},
            }
            self._atomic_write(self.root / "ratings.json", ratings)
            self._atomic_write(self.root / "current.json", current)
            return data

    def rename(self, id: str, title: str) -> dict:
        with self._lock:
            path = self.history_dir / f"{id}.json"
            data = self._read(path, None)
            if not isinstance(data, dict):
                raise KeyError(id)
            data["title"] = title
            self._atomic_write(path, data)
            idx = self._read(self.root / "index.json", [])
            for h in idx if isinstance(idx, list) else []:
                if h.get("id") == id:
                    h["title"] = title
            self._atomic_write(self.root / "index.json", idx if isinstance(idx, list) else [])
            return data

    def delete(self, id: str) -> bool:
        with self._lock:
            path = self.history_dir / f"{id}.json"
            if not path.exists():
                return False
            path.unlink()
            idx = self._read(self.root / "index.json", [])
            idx = [h for h in (idx if isinstance(idx, list) else []) if h.get("id") != id]
            self._atomic_write(self.root / "index.json", idx)
            return True
```

- [ ] **Step 4: Run — expect PASS**

Run: `./venv/bin/pytest tests/test_simulation_store.py -v`

- [ ] **Step 5: Commit**

```bash
git add simulation/store.py tests/test_simulation_store.py
git commit -m "feat(simulation): JSON store with named and auto history"
```

---

### Task 3: What-if engine

**Files:**
- Create: `simulation/whatif.py`
- Test: `tests/test_simulation_whatif.py`

**Interfaces:**
- Consumes: `projection.load.build_context`, `projection.path.project_team`
- Produces:
  - `validate_picks(ctx, picks: dict) -> str | None` — error message or None
  - `apply_picks(ctx, picks: dict) -> Context` — deep-copied context with picks applied; clears `_reach_memo`
  - `preview(team_id: str, ctx, picks: dict) -> dict` — `{ok: True, projection: ...}` or raises `ValueError`

Picks shape:
```python
{
  "groups": {"A": {"first": "a1", "second": "a2"}, ...},  # both required if group key present
  "ko": {"1": "a1", ...}  # match_no(str) -> winner team_id
}
```

Apply rules:
- Group: set `group_resolved[g]` to `[first, second, *remaining_members]` (remaining in original order excluding first/second).
- KO: for match `n`, set winner’s side concrete name: put winner country string into `home_team` or `away_team` only after both sides are known is hard — instead set **both** sides’ concrete teams when sampling isn’t needed: for what-if, set the winner by writing the winner’s `country` into the side they occupy if known, OR simpler v1: set `home_team`/`away_team` such that `_side_set` returns `{winner}` for the winner side and leave the other unresolved until needed.

**Simpler v1 KO apply (required):** For match `match_no` with winner `tid`, set `match["home_team"] = ctx.teams[tid]["country"]` and `match["away_team"] = None` is wrong. Correct approach: resolve candidate sets for home/away; if `tid` in home set, set `home_team` to that country’s name and also set `away_team` only if away is singleton — actually for path projection of **possible opponents**, forcing a KO winner means: clone match and set the winner label resolution via making that match’s both sides concrete with winner on one side and a placeholder? 

**Required implementation (explicit):** After applying group picks, for each KO pick `match_no -> winner_id`:
1. Look up match.
2. Let `H = _side_set(match,"home",ctx)`, `A = _side_set(match,"away",ctx)`.
3. If `winner_id` not in `H|A`, validation error.
4. Set `match["home_team"]` / `match["away_team"]` to the **country** strings of winner and a representative opponent: if winner in H, `home_team = winner.country`, and if A is singleton set `away_team` to that team’s country else leave `away_team` as None but set `away_label` unchanged — wait, `_side_set` prefers concrete over label. So only set the winner’s side to concrete country; leave the other side as labels (possible set). That is enough for `project_team` opponent sets to shrink on the winner’s path when this match is an ancestor.

Also: after mutations, `ctx._reach_memo.clear()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_simulation_whatif.py
from projection.load import build_context
from tests.test_projection_load import TEAMS, BRACKET, UNRESOLVED
from simulation.whatif import validate_picks, preview


def test_bad_group_member_errors():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    err = validate_picks(ctx, {"groups": {"A": {"first": "b1", "second": "a2"}}, "ko": {}})
    assert err and "group" in err.lower()


def test_force_group_shrinks_path():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    base = preview("a1", ctx, {"groups": {}, "ko": {}})
    forced = preview("a1", ctx, {"groups": {"A": {"first": "a1", "second": "a2"},
                                            "B": {"first": "b1", "second": "b2"}}, "ko": {}})
    # With all groups forced, R32 opponents for group winner a1 should be only b2 (2nd of B)
    rounds = forced["projection"]["scenarios"]["group_winner"]
    r32 = next(r for r in rounds if r["round"] == "R32")
    assert [o["id"] for o in r32["possible_opponents"]] == ["b2"]
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `simulation/whatif.py`**

```python
"""Apply what-if picks onto a projection Context and re-project a team."""
from __future__ import annotations

import copy

from projection.resolver import _side_set
from projection.path import project_team


def validate_picks(ctx, picks: dict) -> str | None:
    picks = picks or {}
    groups = picks.get("groups") or {}
    ko = picks.get("ko") or {}
    for g, slot in groups.items():
        members = set(ctx.group_members.get(g, []))
        if not members:
            return f"Unknown group {g}"
        first, second = slot.get("first"), slot.get("second")
        if not first or not second:
            return f"Group {g} needs first and second"
        if first == second:
            return f"Group {g} first and second must differ"
        if first not in members or second not in members:
            return f"Pick not in group {g}"
    for mno, winner in ko.items():
        try:
            match_no = int(mno)
        except (TypeError, ValueError):
            return f"Invalid match_no {mno}"
        match = ctx.matches.get(match_no)
        if not match:
            return f"Unknown match {match_no}"
        if winner not in ctx.teams:
            return f"Unknown winner {winner}"
        # candidates checked after groups applied in apply; light check here
    return None


def apply_picks(ctx, picks: dict):
    ctx = copy.deepcopy(ctx)
    ctx._reach_memo = {}
    picks = picks or {}
    for g, slot in (picks.get("groups") or {}).items():
        first, second = slot["first"], slot["second"]
        rest = [t for t in ctx.group_members.get(g, []) if t not in (first, second)]
        ctx.group_resolved[g] = [first, second, *rest]
    ctx._reach_memo.clear()
    for mno, winner in (picks.get("ko") or {}).items():
        match = ctx.matches[int(mno)]
        H = _side_set(match, "home", ctx)
        A = _side_set(match, "away", ctx)
        if winner not in H | A:
            raise ValueError(f"Winner {winner} not in match {mno} candidates")
        country = ctx.teams[winner]["country"]
        if winner in H:
            match["home_team"] = country
        if winner in A:
            match["away_team"] = country
        # If winner only on one side, clear the other concrete so labels remain for opp set
        if winner in H and winner not in A:
            # keep away as labels
            pass
        if winner in A and winner not in H:
            pass
    ctx._reach_memo.clear()
    return ctx


def preview(team_id: str, ctx, picks: dict) -> dict:
    if team_id not in ctx.teams:
        raise ValueError(f"Unknown team {team_id}")
    err = validate_picks(ctx, picks)
    if err:
        raise ValueError(err)
    applied = apply_picks(ctx, picks)
    return {"ok": True, "projection": project_team(team_id, applied)}
```

- [ ] **Step 4: Run — expect PASS**

Run: `./venv/bin/pytest tests/test_simulation_whatif.py -v`

- [ ] **Step 5: Commit**

```bash
git add simulation/whatif.py tests/test_simulation_whatif.py
git commit -m "feat(simulation): what-if picks apply and path preview"
```

---

### Task 4: Monte Carlo runner

**Files:**
- Create: `simulation/montecarlo.py`
- Test: `tests/test_simulation_montecarlo.py`

**Interfaces:**
- Produces `run_montecarlo(*, team_id, ctx, standings_list, ratings, n, bias, picks=None, use_current_picks=True, seed=None) -> dict`

Return shape:
```python
{
  "ok": True,
  "n": n,
  "bias": bias,
  "standings_signal": bool,
  "reach": {"R32": 0.0, "R16": 0.0, ...},  # fraction 0..1 of trials where team plays that round
  "opponents": {
     "R32": [{"id", "country", "team_name", "pct"}, ...],  # sorted by pct desc, top 10
     ...
  }
}
```

Algorithm per trial:
1. `trial_ctx = deepcopy(base_ctx)`; if `use_current_picks` and picks: `trial_ctx = apply_picks(trial_ctx, picks)`.
2. For each group still unresolved (`group_resolved[g] is None`): sample a finishing order — repeatedly `weighted_choice` without replacement using strengths, assign `group_resolved[g]`.
3. Process KO matches in ascending `match_no` (or by stages R32→Final): if both sides resolvable to concrete winners needed — sample winner with `weighted_choice` among `H|A` if not already concrete singleton winner; set winner’s side concrete country (same as what-if).
4. Determine focus team finishing position from `group_resolved[team.group]`; if not 1st or 2nd, they reach nothing.
5. Else project path with `project_team` on fully/mostly resolved ctx; for each round, if `possible_opponents` is size 1, count that opponent; if size 0 skip; if size >1 count each? After full KO resolution opponents should be size ≤1. Prefer walking only matches the team actually plays: find entry match for their scenario, then follow winners.

**Practical walk helper:** After full resolution, every match has concrete home_team and away_team countries. Find matches involving focus team’s country; record round + opponent.

Raise `ValueError` if `n < 1` or `n > 10000`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_simulation_montecarlo.py
from projection.load import build_context
from tests.test_projection_load import TEAMS, BRACKET, UNRESOLVED
from simulation.montecarlo import run_montecarlo


def test_rejects_too_many():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    try:
        run_montecarlo(team_id="a1", ctx=ctx, standings_list=UNRESOLVED,
                       ratings={}, n=10001, bias=0.0, seed=1)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "10000" in str(e)


def test_seeded_run_returns_shape():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    out = run_montecarlo(team_id="a1", ctx=ctx, standings_list=UNRESOLVED,
                         ratings={}, n=200, bias=0.0, seed=42)
    assert out["ok"] is True and out["n"] == 200
    assert "R32" in out["reach"]
    assert out["reach"]["R32"] > 0  # a1 can finish top2 often enough in tiny groups
    assert isinstance(out["opponents"].get("R32", []), list)


def test_bias_favors_strong_override():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    weak = run_montecarlo(team_id="a2", ctx=ctx, standings_list=UNRESOLVED,
                          ratings={"a1": 100.0, "a2": 0.01, "b1": 1, "b2": 1},
                          n=400, bias=1.0, seed=7)
    strong = run_montecarlo(team_id="a1", ctx=ctx, standings_list=UNRESOLVED,
                            ratings={"a1": 100.0, "a2": 0.01, "b1": 1, "b2": 1},
                            n=400, bias=1.0, seed=7)
    assert strong["reach"]["R32"] > weak["reach"]["R32"]
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `simulation/montecarlo.py`**

```python
"""Monte Carlo path-to-final frequencies for one focus team."""
from __future__ import annotations

import copy
import random
from collections import Counter, defaultdict

from projection.resolver import _side_set
from simulation.strength import standings_have_signal, team_strengths, weighted_choice
from simulation.whatif import apply_picks


def _sample_group_order(rng, members, strengths, bias):
    remaining = list(members)
    order = []
    while remaining:
        pick = weighted_choice(rng, remaining, strengths, bias)
        order.append(pick)
        remaining.remove(pick)
    return order


def _set_winner(ctx, match, winner_id):
    country = ctx.teams[winner_id]["country"]
    H = _side_set(match, "home", ctx)
    A = _side_set(match, "away", ctx)
    if winner_id in H:
        match["home_team"] = country
    if winner_id in A:
        match["away_team"] = country
    ctx._reach_memo.clear()


def _resolve_all_ko(rng, ctx, strengths, bias):
    for match_no in sorted(ctx.matches):
        match = ctx.matches[match_no]
        H = _side_set(match, "home", ctx)
        A = _side_set(match, "away", ctx)
        cands = list(H | A)
        if not cands:
            continue
        # Already concrete single winner on both sides resolved to one each:
        if match.get("home_team") and match.get("away_team"):
            # pick winner among the two concrete teams
            home_id = next(iter(H)) if len(H) == 1 else None
            away_id = next(iter(A)) if len(A) == 1 else None
            pair = [x for x in (home_id, away_id) if x]
            if len(pair) == 2:
                w = weighted_choice(rng, pair, strengths, bias)
                # encode winner by clearing loser concrete? keep both teams; path walker uses both
                match["_winner_id"] = w
            continue
        if len(cands) == 1:
            _set_winner(ctx, match, cands[0])
            match["_winner_id"] = cands[0]
            continue
        w = weighted_choice(rng, cands, strengths, bias)
        _set_winner(ctx, match, w)
        match["_winner_id"] = w
        # Also concretize a loser so both sides exist for display walks
        losers = [c for c in cands if c != w]
        if losers and not (match.get("home_team") and match.get("away_team")):
            loser = losers[0]
            loc = ctx.teams[loser]["country"]
            if match.get("home_team"):
                match["away_team"] = loc
            else:
                match["home_team"] = loc
        ctx._reach_memo.clear()


def _team_path_played(team_id, ctx):
    """Return [(stage, opponent_id), ...] for matches the team actually plays."""
    team = ctx.teams[team_id]
    country = (team.get("country") or "").lower()
    # Build winner map for progression
    played = []
    # Order matches by stage pipeline using next_match links from R32 entries
    for m in sorted(ctx.matches.values(), key=lambda x: x.get("match_no") or 0):
        home = (m.get("home_team") or "").lower()
        away = (m.get("away_team") or "").lower()
        if country not in (home, away):
            continue
        # opponent is the other side's team id
        opp_country = away if home == country else home
        opp_id = ctx.team_id_by_name.get(opp_country)
        played.append((m.get("stage") or "?", opp_id))
        # If this team did not win, stop path
        winner_id = m.get("_winner_id")
        if winner_id and winner_id != team_id:
            break
        if not winner_id:
            # infer: if only one concrete side matched team and we set winner earlier
            break
    return played


def run_montecarlo(*, team_id, ctx, standings_list, ratings, n, bias,
                   picks=None, use_current_picks=True, seed=None):
    if n < 1 or n > 10000:
        raise ValueError("n must be between 1 and 10000")
    if team_id not in ctx.teams:
        raise ValueError(f"Unknown team {team_id}")
    rng = random.Random(seed)
    strengths = team_strengths(standings_list, overrides=ratings or {})
    # ensure every team has a strength
    for tid in ctx.teams:
        strengths.setdefault(tid, 1.0)

    reach_counts = Counter()
    opp_counts = defaultdict(Counter)
    trials = int(n)

    for _ in range(trials):
        trial = copy.deepcopy(ctx)
        trial._reach_memo = {}
        if use_current_picks and picks:
            trial = apply_picks(trial, picks)
        for g, members in trial.group_members.items():
            if trial.group_resolved.get(g) is None:
                trial.group_resolved[g] = _sample_group_order(rng, members, strengths, bias)
        trial._reach_memo.clear()
        _resolve_all_ko(rng, trial, strengths, bias)
        path = _team_path_played(team_id, trial)
        for stage, opp_id in path:
            reach_counts[stage] += 1
            if opp_id:
                opp_counts[stage][opp_id] += 1

    reach = {k: reach_counts[k] / trials for k in reach_counts}
    opponents = {}
    for stage, counter in opp_counts.items():
        items = []
        for oid, cnt in counter.most_common(10):
            brief = ctx.team_brief(oid)
            items.append({**brief, "pct": cnt / trials})
        opponents[stage] = items

    return {
        "ok": True,
        "n": trials,
        "bias": float(bias),
        "standings_signal": standings_have_signal(standings_list),
        "reach": reach,
        "opponents": opponents,
    }
```

- [ ] **Step 4: Run — expect PASS**

Run: `./venv/bin/pytest tests/test_simulation_montecarlo.py -v`

- [ ] **Step 5: Commit**

```bash
git add simulation/montecarlo.py tests/test_simulation_montecarlo.py
git commit -m "feat(simulation): Monte Carlo reach and opponent frequencies"
```

---

### Task 5: Flask sim APIs

**Files:**
- Create: `dashboard/sim_api.py`
- Modify: `dashboard/app.py` — `create_app(data_dir=..., sim_dir=None, job=None)`; register blueprint; default `sim_dir` = sibling `data/simulations` when `data_dir` ends with `latest`, else `tmp`/`simulations`
- Test: `tests/test_sim_api.py`
- Modify: `tests/dashboard_fixture.py` if needed for client fixture

**Interfaces:**
- Produces blueprint routes exactly as spec §8.
- `create_app` builds `SimStore(sim_dir)` and `load_context(data_dir)` on demand (or from DataStore lists via `build_context`).

JSON helpers:
```python
def ok(data, code=200): return jsonify({"ok": True, **data}), code
def err(msg, code=400): return jsonify({"ok": False, "error": msg}), code
```

- [ ] **Step 1: Write failing API tests**

```python
# tests/test_sim_api.py
import json
from dashboard.app import create_app
from tests.dashboard_fixture import write_minimal_dataset  # adapt if name differs


def _client(tmp_path):
    data = tmp_path / "latest"
    sim = tmp_path / "simulations"
    data.mkdir(); sim.mkdir()
    # seed minimal teams/standings/bracket/projections/manifest like existing fixture helper
    from tests.test_projection_load import TEAMS, BRACKET, UNRESOLVED
    (data / "teams.json").write_text(json.dumps(TEAMS))
    (data / "standings.json").write_text(json.dumps(UNRESOLVED))
    (data / "bracket.json").write_text(json.dumps(BRACKET))
    (data / "fixtures.json").write_text("[]")
    (data / "scorers.json").write_text("[]")
    (data / "rosters.json").write_text("[]")
    (data / "projections.json").write_text("{}")
    (data / "manifest.json").write_text("{}")
    app = create_app(data_dir=str(data), sim_dir=str(sim), job=None)
    app.config["TESTING"] = True
    return app.test_client()


def test_ratings_and_current_roundtrip(tmp_path):
    c = _client(tmp_path)
    r = c.put("/api/sim/ratings", json={"a1": 3})
    assert r.get_json()["ok"] is True
    assert c.get("/api/sim/ratings").get_json()["ratings"]["a1"] == 3


def test_whatif_preview(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sim/whatif/preview", json={
        "team_id": "a1",
        "picks": {"groups": {"A": {"first": "a1", "second": "a2"},
                             "B": {"first": "b1", "second": "b2"}}, "ko": {}}})
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert "projection" in r.get_json()


def test_mc_rejects_large_n(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sim/montecarlo/run", json={"team_id": "a1", "n": 10001, "bias": 0})
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_history_save_restore(tmp_path):
    c = _client(tmp_path)
    c.put("/api/sim/current", json={"whatif": {"groups": {"A": {"first": "a1", "second": "a2"}}, "ko": {}},
                                    "mc": {"n": 100, "bias": 0.5, "use_current_picks": True}})
    r = c.post("/api/sim/history", json={"type": "named", "title": "Mine", "team_id": "a1"})
    hid = r.get_json()["entry"]["id"]
    c.put("/api/sim/current", json={"whatif": {"groups": {}, "ko": {}},
                                    "mc": {"n": 1000, "bias": 0, "use_current_picks": True}})
    c.post(f"/api/sim/history/{hid}/restore")
    cur = c.get("/api/sim/current").get_json()["current"]
    assert cur["whatif"]["groups"]["A"]["first"] == "a1"
```

- [ ] **Step 2: Run — expect FAIL** (routes missing)

- [ ] **Step 3: Implement `dashboard/sim_api.py` and wire `create_app`**

`create_app` signature becomes:
```python
def create_app(data_dir="./data/latest", sim_dir=None, job=None):
    ...
    if sim_dir is None:
        p = Path(data_dir)
        sim_dir = str(p.parent / "simulations") if p.name == "latest" else str(p / "simulations")
    sim_store = SimStore(sim_dir)
    app.register_blueprint(make_sim_blueprint(store, sim_store, data_dir))
```

Ensure RefreshJob still only touches scraper/projection — no sim_dir.

Auto-snapshot: on `PUT /api/sim/current` when body `autosave: true` (default true), call `save_history(type="auto", ...)`.

- [ ] **Step 4: Run — expect PASS**

Run: `./venv/bin/pytest tests/test_sim_api.py tests/test_dashboard_*.py -v`  
(Adapt glob to existing dashboard tests.)

- [ ] **Step 5: Commit**

```bash
git add dashboard/sim_api.py dashboard/app.py tests/test_sim_api.py
git commit -m "feat(dashboard): simulator JSON APIs and SimStore wiring"
```

---

### Task 6: Team page simulator UI

**Files:**
- Modify: `dashboard/templates/team_detail.html`
- Create: `dashboard/static/js/sim.js`
- Modify: `dashboard/templates/base.html` — include `sim.js` only on team detail **or** always (guard with `document.getElementById('sim-root')`)
- Modify: `dashboard/static/css/style.css` — mode tabs, drawer, banners, skeletons
- Modify: `dashboard/app.py` `team_detail` — pass `standings_signal`, `group_teams`, `ko_slots` helpers for what-if dropdowns

**UI requirements (spec):**
- Mode tabs: Possible | What-if | Monte Carlo — only one panel visible (`hidden` attribute or `.is-active`).
- Mode A: existing projection UI + CTA button `Open in What-if`.
- Mode B: group 1st/2nd selects; KO winner selects; Reset; Save as…; live preview via `POST /api/sim/whatif/preview`.
- Mode C: n input, bias range, use_current_picks checkbox, Run (disabled while pending), results table; strength banner when `!standings_signal`.
- History drawer: closed by default; list; restore/rename/delete.
- Roster in a second tab below or `details`/sub-tab — not side-by-side competing with sim.

- [ ] **Step 1: Manual structure check** — rewrite `team_detail.html` skeleton:

```html
{% extends "base.html" %}
{% block content %}
<div id="sim-root" data-team-id="{{ team.id }}" data-standings-signal="{{ 1 if standings_signal else 0 }}">
  <!-- header -->
  <div class="sim-tabs" role="tablist">
    <button type="button" data-mode="possible" class="sim-tab is-active">Possible opponents</button>
    <button type="button" data-mode="whatif" class="sim-tab">What-if</button>
    <button type="button" data-mode="montecarlo" class="sim-tab">Monte Carlo</button>
    <button type="button" id="history-open" class="btn-secondary">History</button>
  </div>
  <section id="panel-possible" class="sim-panel is-active">...</section>
  <section id="panel-whatif" class="sim-panel" hidden>...</section>
  <section id="panel-montecarlo" class="sim-panel" hidden>...</section>
  <aside id="history-drawer" class="history-drawer" hidden>...</aside>
  <section class="roster-block">...</section>
</div>
<script src="{{ url_for('static', filename='js/sim.js') }}"></script>
{% endblock %}
```

- [ ] **Step 2: Implement `sim.js`** — tab switching; debounce preview; MC run; history CRUD. Use `fetch` with JSON. On errors show `.sim-error` text.

- [ ] **Step 3: CSS** for `.sim-tabs`, `.sim-panel`, `.history-drawer`, `.strength-banner`, loading skeleton.

- [ ] **Step 4: Smoke test with Flask client**

```python
def test_team_page_has_sim_root(tmp_path):
    c = _client(tmp_path)  # same helper as Task 5, ensure team a1 exists
    html = c.get("/teams/a1").data.decode()
    assert 'id="sim-root"' in html
    assert "Possible opponents" in html
```

Add to `tests/test_sim_api.py` or new `tests/test_team_sim_page.py`.

- [ ] **Step 5: Run pytest for new page test + start server manually optional**

Run: `./venv/bin/pytest tests/test_sim_api.py tests/test_team_sim_page.py -v`

- [ ] **Step 6: Commit**

```bash
git add dashboard/templates/team_detail.html dashboard/static/js/sim.js dashboard/static/css/style.css dashboard/templates/base.html dashboard/app.py tests/test_team_sim_page.py
git commit -m "feat(dashboard): team page simulator modes and history drawer"
```

---

### Task 7: Dashboard-wide polish

**Files:**
- Modify: `dashboard/static/css/style.css`
- Modify: `dashboard/templates/base.html`, `overview.html`, `teams.html`, `fixtures.html`, `standings.html`, `bracket.html`, `scorers.html`
- Modify: `dashboard/static/js/app.js` if refresh UX is broken

**Requirements:**
- Align closer to `design-system/aiub-world-cup-dashboard/MASTER.md` (spacing tokens, soft surfaces, consistent page headers).
- Every list page: real empty state (`No fixtures yet`, etc.) when data empty — never blank white.
- Topbar: active nav, refresh button states already present — verify polling still works.
- Theme toggle if missing but design system expects light/dark — keep `data-theme` support already in CSS.
- No SPA; no new CSS framework.

- [ ] **Step 1: Audit each template for missing empty states; patch.**

- [ ] **Step 2: Tighten CSS** — page header block, section spacing using `--space-*` if adding variables from MASTER; ensure focus rings.

- [ ] **Step 3: Run full suite**

Run: `./venv/bin/pytest -v`  
Expected: all pass (including prior 46+ new tests).

- [ ] **Step 4: Commit**

```bash
git add dashboard/templates dashboard/static
git commit -m "style(dashboard): polish layout, empty states, and design tokens"
```

---

### Task 8: README + verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document**

Add a **Simulator** section:
- Open `/teams/<id>`
- Modes A/B/C
- Data under `data/simulations/`
- API overview one-liner
- Note MC defaults n=1000 max 10000

- [ ] **Step 2: Full verification**

```bash
./venv/bin/pytest -v
./venv/bin/python -m dashboard.app   # or flask run pattern used in README
# manually: open team page, switch modes, run MC n=200, save named history, restore
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document team simulator usage and data layout"
```

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Mode A possible opponents on team page | 6 |
| Mode B what-if group 1st/2nd + KO | 3, 5, 6 |
| Mode C Monte Carlo bias dial | 1, 4, 5, 6 |
| Hybrid strength + overrides | 1, 6 |
| JSON store + auto/named history | 2, 5, 6 |
| APIs §8 | 5 |
| Pre-tournament banner | 6 |
| MC n default/max | 4, 5 |
| `use_current_picks` | 4, 5 |
| Dashboard polish | 7 |
| Refresh ignores sim dir | 5 (verify), 8 |
| Tests | 1–6, 8 |

## Placeholder / consistency self-review

- No TBD steps; Task 4 includes full `montecarlo.py` source matching the tests.
- `SimStore` / `create_app(..., sim_dir=...)` names consistent across Tasks 2, 5, 6.
- Picks shape `{groups, ko}` consistent in whatif, store current, APIs, JS.
- Error JSON `{ok:false, error}` consistent.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-22-team-simulator.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — run tasks in this session with executing-plans checkpoints  

Which approach?
