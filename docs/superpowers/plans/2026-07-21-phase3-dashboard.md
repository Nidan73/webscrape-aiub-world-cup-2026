# AIUB World Cup Scraper — Phase 3 (Flask Dashboard) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local Flask dashboard that visualizes the scraped data — overview, teams (country + real name), fixtures, standings, knockout bracket, top scorers, and each team's possible-opponents path to the final — with a non-blocking background "refresh data" button.

**Architecture:** A Flask app factory reads `data/latest/*.json` through a caching `DataStore` (invalidated when `manifest.json` changes) and renders Jinja templates. A `RefreshJob` runs the scraper+projection in a background thread so HTTP requests never block. All tournament logic stays in Phases 1–2; the dashboard only reads their JSON. Visual design follows `design-system/aiub-world-cup-dashboard/MASTER.md` (Soft UI Evolution; slate surfaces, red-600 primary, amber accent; Fira Sans/Fira Code; full light+dark; WCAG AA).

**Tech Stack:** Flask + Jinja2 (server-rendered), hand-written CSS (no build step), a few lines of vanilla JS for refresh polling. `pytest` + Flask test client.

**Spec:** `docs/superpowers/specs/2026-07-21-aiub-world-cup-scraper-design.md` §9. **Depends on:** Phase 1 (JSON) + Phase 2 (`projections.json`).

## Global Constraints

- Python 3.10+. Add `flask` to `requirements.txt` (already listed in the spec).
- Dashboard is **read-only over files**; it never scrapes inline — only the background `RefreshJob` does, via subprocess.
- App factory `create_app(data_dir="./data/latest", job=None)` so tests inject a fixture dir + fake job.
- Remote images (flags at `/assets/flags/...`, player photos at `/assets/player_img/...`) are hotlinked from `https://ofsportsaiub.org` via an `asset()` helper; always provide `alt` text so they degrade gracefully offline.
- Design tokens are CSS custom properties with light + dark values; **no raw hex in templates**. SVG icons only (no emoji). Focus-visible rings; honor `prefers-reduced-motion`. Responsive at 375/768/1024/1440, no horizontal scroll (wide tables scroll inside their own container).
- **Commit messages must NOT contain any `Co-Authored-By` or AI-tool trailer** (user directive). Plain `-m` only.
- Work on branch `feat/phase3-dashboard`, not `main`.

### Data shapes (from Phases 1–2, for template authors)
- `teams.json`: `[{id, slug, flag_url, country, team_name, faculty, group, captain:{player_id,name,player_url}|null}]`
- `rosters.json`: `[{team_id, country, team_name, players:[{player_id,jersey_number,name,role,is_captain,photo_url,goals,assists,cards}]}]`
- `fixtures.json`: `[{match_id, match_no, group, date, time, home:{country,flag_code}, away:{country,flag_code}, home_score, away_score, status, raw_score}]`
- `standings.json`: `[{group, table:[{position,team_id,country,played,points,goal_diff,goals_for,fair_play,qualified}]}]`
- `bracket.json`: `[{stage, matches:[{match_no,next_match_no,home_label,away_label,home_team,away_team,status}]}]`
- `scorers.json`: `[]` (empty until first goal) — items would be `{rank,player_id,name,team,goals}`
- `projections.json`: `{team_id: {country, team_name, scenarios:{group_winner:[{round,possible_opponents:[{id,country,team_name}]}], runner_up:[...]}}}`
- `manifest.json`: `{scraped_at, source, entities:{name:{count,ok,error}}, snapshot_dir}`

---

### Task 1: DataStore (cached JSON access)

**Files:**
- Create: `dashboard/__init__.py` (empty)
- Create: `dashboard/data_access.py`
- Test: `tests/test_dashboard_data.py`

**Interfaces:**
- Produces `DataStore(data_dir)` with `teams()`, `team(tid)`, `rosters()`, `roster(tid)`, `fixtures()`, `standings()`, `bracket()`, `scorers()`, `projections()`, `manifest()`. Cache clears when `manifest.json` mtime changes. Missing/broken files return a safe default (`[]` or `{}`), never raise.

- [ ] **Step 1: Write the failing test**

`tests/test_dashboard_data.py`:
```python
import json
from dashboard.data_access import DataStore


def _seed(dirpath, manifest_stamp="A"):
    (dirpath / "teams.json").write_text(json.dumps(
        [{"id": "42", "country": "Netherlands", "team_name": "CS Backbencher", "group": "A"}]))
    (dirpath / "manifest.json").write_text(json.dumps({"scraped_at": manifest_stamp}))


def test_reads_and_caches(tmp_path):
    _seed(tmp_path)
    store = DataStore(str(tmp_path))
    assert store.teams()[0]["team_name"] == "CS Backbencher"
    assert store.team("42")["country"] == "Netherlands"
    assert store.team("nope") is None


def test_missing_file_returns_default(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    store = DataStore(str(tmp_path))
    assert store.fixtures() == [] and store.projections() == {}


def test_cache_invalidates_on_manifest_change(tmp_path):
    _seed(tmp_path)
    store = DataStore(str(tmp_path))
    assert store.teams()[0]["team_name"] == "CS Backbencher"
    # rewrite teams + bump manifest -> cache must refresh
    (tmp_path / "teams.json").write_text(json.dumps([{"id": "1", "country": "X", "team_name": "Y", "group": "A"}]))
    import os, time
    (tmp_path / "manifest.json").write_text(json.dumps({"scraped_at": "B"}))
    os.utime(tmp_path / "manifest.json", (time.time() + 5, time.time() + 5))
    assert store.teams()[0]["team_name"] == "Y"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_dashboard_data.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'dashboard'`).

- [ ] **Step 3: Write `dashboard/__init__.py` (empty) and `dashboard/data_access.py`**

```python
"""Cached read access to the scraped data/latest JSON files."""
import json
import os


class DataStore:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self._cache = {}
        self._stamp = object()      # sentinel != any mtime

    def _manifest_mtime(self):
        try:
            return os.path.getmtime(os.path.join(self.data_dir, "manifest.json"))
        except OSError:
            return None

    def _get(self, name, default):
        stamp = self._manifest_mtime()
        if stamp != self._stamp:
            self._cache.clear()
            self._stamp = stamp
        if name not in self._cache:
            try:
                with open(os.path.join(self.data_dir, f"{name}.json"), encoding="utf-8") as fh:
                    self._cache[name] = json.load(fh)
            except (OSError, json.JSONDecodeError):
                self._cache[name] = default
        return self._cache[name]

    def teams(self):        return self._get("teams", [])
    def rosters(self):      return self._get("rosters", [])
    def fixtures(self):     return self._get("fixtures", [])
    def standings(self):    return self._get("standings", [])
    def bracket(self):      return self._get("bracket", [])
    def scorers(self):      return self._get("scorers", [])
    def projections(self):  return self._get("projections", {})
    def manifest(self):     return self._get("manifest", {})

    def team(self, tid):
        return next((t for t in self.teams() if t.get("id") == tid), None)

    def roster(self, tid):
        return next((r for r in self.rosters() if r.get("team_id") == tid), None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_dashboard_data.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add dashboard/__init__.py dashboard/data_access.py tests/test_dashboard_data.py
git commit -m "feat(dashboard): cached DataStore over scraped JSON"
```

---

### Task 2: Background refresh job

**Files:**
- Create: `dashboard/jobs.py`
- Test: `tests/test_dashboard_jobs.py`

**Interfaces:**
- Produces `RefreshJob(runner=None)` with `start() -> bool` (False if already running — single-flight), `status() -> {state, started_at, finished_at, error}` where `state ∈ {"idle","running","done","error"}`. Default `runner` runs `scraper.run` then `projection.run` via subprocess; tests inject a fake runner.

- [ ] **Step 1: Write the failing test**

`tests/test_dashboard_jobs.py`:
```python
import threading
from dashboard.jobs import RefreshJob


def test_runs_to_done():
    ran = []
    job = RefreshJob(runner=lambda: ran.append(1))
    assert job.start() is True
    job._thread.join(timeout=2)
    assert ran == [1]
    assert job.status()["state"] == "done" and job.status()["error"] is None


def test_error_is_captured():
    def boom():
        raise RuntimeError("nope")
    job = RefreshJob(runner=boom)
    job.start()
    job._thread.join(timeout=2)
    st = job.status()
    assert st["state"] == "error" and "nope" in st["error"]


def test_single_flight():
    gate = threading.Event()
    job = RefreshJob(runner=lambda: gate.wait(2))
    assert job.start() is True
    assert job.start() is False          # already running
    assert job.status()["state"] == "running"
    gate.set()
    job._thread.join(timeout=2)
    assert job.status()["state"] == "done"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_dashboard_jobs.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'dashboard.jobs'`).

- [ ] **Step 3: Write `dashboard/jobs.py`**

```python
"""Single-flight background refresh: run scraper + projection off the request thread."""
import subprocess
import sys
import threading
import time


class RefreshJob:
    def __init__(self, runner=None):
        self._runner = runner or self._default_runner
        self._lock = threading.Lock()
        self._thread = None
        self._state = "idle"
        self._started_at = None
        self._finished_at = None
        self._error = None

    @staticmethod
    def _default_runner():
        subprocess.run([sys.executable, "-m", "scraper.run"], check=True)
        subprocess.run([sys.executable, "-m", "projection.run"], check=True)

    def start(self):
        with self._lock:
            if self._state == "running":
                return False
            self._state = "running"
            self._started_at = time.time()
            self._finished_at = None
            self._error = None
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            return True

    def _run(self):
        try:
            self._runner()
            state, error = "done", None
        except Exception as exc:
            state, error = "error", str(exc)
        with self._lock:
            self._state = state
            self._error = error
            self._finished_at = time.time()

    def status(self):
        with self._lock:
            return {"state": self._state, "started_at": self._started_at,
                    "finished_at": self._finished_at, "error": self._error}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_dashboard_jobs.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add dashboard/jobs.py tests/test_dashboard_jobs.py
git commit -m "feat(dashboard): single-flight background refresh job"
```

---

### Task 3: App factory + base layout + CSS + overview

**Files:**
- Create: `dashboard/app.py`
- Create: `dashboard/templates/base.html`
- Create: `dashboard/templates/overview.html`
- Create: `dashboard/static/css/style.css`
- Test: `tests/test_dashboard_app.py` + `tests/dashboard_fixture.py` (shared fixture builder)

**Interfaces:**
- Consumes: `DataStore`, `RefreshJob`.
- Produces: `create_app(data_dir="./data/latest", job=None) -> Flask`. Routes added here: `GET /` (overview). Jinja globals: `asset(path)` (prefixes site host for `/…` paths), and `store` access via view functions. Later tasks add more routes to the same factory.

- [ ] **Step 1: Write the shared fixture builder and the failing test**

`tests/dashboard_fixture.py`:
```python
"""Write a minimal but complete data/latest set for dashboard tests."""
import json


def seed(dirpath):
    def w(name, obj):
        (dirpath / f"{name}.json").write_text(json.dumps(obj))

    w("teams", [
        {"id": "42", "slug": "netherlands", "flag_url": "/assets/flags/w40/nl.png",
         "country": "Netherlands", "team_name": "CS Backbencher", "faculty": "FST", "group": "A",
         "captain": {"player_id": "657", "name": "Zarif Arian", "player_url": "/players/657-x"}},
        {"id": "30", "slug": "turkey-turkiye", "flag_url": "/assets/flags/w40/tr.png",
         "country": "Turkey/Turkiye", "team_name": "CS Amigos", "faculty": "FST", "group": "A",
         "captain": None},
    ])
    w("rosters", [
        {"team_id": "42", "country": "Netherlands", "team_name": "CS Backbencher", "players": [
            {"player_id": "657", "jersey_number": "01", "name": "Zarif Arian", "role": "Player",
             "is_captain": True, "photo_url": "/assets/player_img/a.png", "goals": 0, "assists": 0, "cards": 0}]},
    ])
    w("fixtures", [
        {"match_id": "1", "match_no": 1, "group": "A", "date": "Jul 28", "time": "8:00 AM",
         "home": {"country": "Turkey/Turkiye", "flag_code": "tr"},
         "away": {"country": "Netherlands", "flag_code": "nl"},
         "home_score": None, "away_score": None, "status": "scheduled", "raw_score": "VS"},
    ])
    w("standings", [
        {"group": "A", "table": [
            {"position": 1, "team_id": "30", "country": "Turkey/Turkiye", "played": 0, "points": 0,
             "goal_diff": 0, "goals_for": 0, "fair_play": 0, "qualified": True},
            {"position": 2, "team_id": "42", "country": "Netherlands", "played": 0, "points": 0,
             "goal_diff": 0, "goals_for": 0, "fair_play": 0, "qualified": True}]},
    ])
    w("bracket", [
        {"stage": "R32", "matches": [
            {"match_no": 49, "next_match_no": 65, "home_label": "1st of Group A",
             "away_label": "2nd of Group I", "home_team": None, "away_team": None, "status": "scheduled"}]},
        {"stage": "Final", "matches": [
            {"match_no": 79, "next_match_no": None, "home_label": "Winner of M77",
             "away_label": "Winner of M78", "home_team": None, "away_team": None, "status": "scheduled"}]},
    ])
    w("scorers", [])
    w("projections", {
        "42": {"country": "Netherlands", "team_name": "CS Backbencher", "scenarios": {
            "group_winner": [
                {"round": "R32", "possible_opponents": [{"id": "99", "country": "Argentina", "team_name": "ECO Gladiators"}]},
                {"round": "Final", "possible_opponents": [{"id": "30", "country": "Turkey/Turkiye", "team_name": "CS Amigos"}]}],
            "runner_up": [
                {"round": "R32", "possible_opponents": [{"id": "99", "country": "Argentina", "team_name": "ECO Gladiators"}]}]}},
    })
    w("manifest", {"scraped_at": "2026-07-21T00-00-00Z", "source": "https://ofsportsaiub.org",
                   "entities": {"teams": {"count": 2, "ok": True, "error": None},
                                "fixtures": {"count": 1, "ok": True, "error": None}},
                   "snapshot_dir": "x"})
```

`tests/test_dashboard_app.py`:
```python
import pytest
from dashboard.app import create_app
from tests.dashboard_fixture import seed


@pytest.fixture
def client(tmp_path):
    seed(tmp_path)
    app = create_app(str(tmp_path))
    app.config.update(TESTING=True)
    return app.test_client()


def test_overview_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "AIUB World Cup" in body
    assert "/teams" in body and "/fixtures" in body          # nav present
    assert "ofsportsaiub.org" in body                          # asset() host applied to a flag
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_dashboard_app.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'dashboard.app'`).

- [ ] **Step 3: Write `dashboard/app.py`**

```python
"""Flask dashboard for the AIUB World Cup dataset."""
from flask import Flask, render_template, abort, jsonify

from dashboard.data_access import DataStore
from dashboard.jobs import RefreshJob

SITE = "https://ofsportsaiub.org"


def _asset(path):
    if not path:
        return ""
    return f"{SITE}{path}" if path.startswith("/") else path


def create_app(data_dir="./data/latest", job=None):
    app = Flask(__name__)
    store = DataStore(data_dir)
    refresh_job = job or RefreshJob()

    @app.context_processor
    def _globals():
        return {"asset": _asset, "manifest": store.manifest(),
                "nav": [("overview", "/"), ("teams", "/teams"), ("fixtures", "/fixtures"),
                        ("standings", "/standings"), ("bracket", "/bracket"), ("scorers", "/scorers")]}

    @app.route("/")
    def overview():
        fixtures = store.fixtures()
        upcoming = [f for f in fixtures if f.get("status") == "scheduled"][:6]
        played = [f for f in fixtures if f.get("status") in ("final", "live")]
        stats = {"teams": len(store.teams()), "fixtures": len(fixtures),
                 "played": len(played), "groups": len(store.standings())}
        return render_template("overview.html", title="Overview", stats=stats, upcoming=upcoming)

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
```

- [ ] **Step 4: Write `dashboard/templates/base.html`**

```html
<!doctype html>
<html lang="en" data-theme="auto">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }} · AIUB World Cup 2026</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;600&family=Fira+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/"><span class="dot"></span> AIUB World Cup <b>2026</b></a>
    <nav class="nav">
      {% for label, href in nav %}
        <a href="{{ href }}" class="nav-link{{ ' active' if request.path == href or (href != '/' and request.path.startswith(href)) }}">{{ label|capitalize }}</a>
      {% endfor %}
    </nav>
    <button id="refresh-btn" class="btn" type="button" aria-live="polite">Refresh data</button>
  </header>
  <main class="wrap">
    {% block content %}{% endblock %}
  </main>
  <footer class="foot">
    Data scraped from <a href="https://ofsportsaiub.org">ofsportsaiub.org</a>
    {% if manifest.scraped_at %} · last updated {{ manifest.scraped_at }}{% endif %}
  </footer>
  <script src="{{ url_for('static', filename='js/app.js') }}" defer></script>
</body>
</html>
```

- [ ] **Step 5: Write `dashboard/templates/overview.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="page-title">Tournament Overview</h1>
<section class="stat-row">
  <div class="stat"><span class="stat-num">{{ stats.teams }}</span><span class="stat-lbl">Teams</span></div>
  <div class="stat"><span class="stat-num">{{ stats.groups }}</span><span class="stat-lbl">Groups</span></div>
  <div class="stat"><span class="stat-num">{{ stats.fixtures }}</span><span class="stat-lbl">Matches</span></div>
  <div class="stat"><span class="stat-num">{{ stats.played }}</span><span class="stat-lbl">Played</span></div>
</section>

<h2 class="section-title">Next matches</h2>
<div class="card-grid">
  {% for f in upcoming %}
  <article class="match-card">
    <div class="match-meta"><span class="pill">Group {{ f.group }}</span><span>{{ f.date }} · {{ f.time }}</span></div>
    <div class="match-teams">
      <span class="side">{% if f.home.flag_code %}<img class="flag" src="{{ asset('/assets/flags/w40/' ~ f.home.flag_code ~ '.png') }}" alt="">{% endif %}{{ f.home.country }}</span>
      <span class="vs">{{ f.raw_score }}</span>
      <span class="side">{% if f.away.flag_code %}<img class="flag" src="{{ asset('/assets/flags/w40/' ~ f.away.flag_code ~ '.png') }}" alt="">{% endif %}{{ f.away.country }}</span>
    </div>
  </article>
  {% else %}
  <p class="muted">No upcoming matches.</p>
  {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 6: Write `dashboard/static/css/style.css`**

```css
:root{
  --bg:#f8fafc; --surface:#ffffff; --text:#0f172a; --muted:#64748b; --border:#e2e8f0;
  --primary:#dc2626; --on-primary:#ffffff; --accent:#d97706; --qualify:#16a34a; --live:#dc2626;
  --shadow:0 1px 2px rgba(15,23,42,.06),0 4px 12px rgba(15,23,42,.06); --radius:12px;
  --sans:"Fira Sans",system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  --mono:"Fira Code",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0f172a; --surface:#1e293b; --text:#f1f5f9; --muted:#94a3b8; --border:#334155;
  --primary:#ef4444; --accent:#fbbf24; --shadow:0 1px 2px rgba(0,0,0,.3),0 6px 16px rgba(0,0,0,.35);
}}
:root[data-theme="dark"]{--bg:#0f172a;--surface:#1e293b;--text:#f1f5f9;--muted:#94a3b8;--border:#334155;--primary:#ef4444;--accent:#fbbf24;}
:root[data-theme="light"]{--bg:#f8fafc;--surface:#ffffff;--text:#0f172a;--muted:#64748b;--border:#e2e8f0;--primary:#dc2626;--accent:#d97706;}

*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);font-size:16px;line-height:1.5}
a{color:inherit;text-decoration:none}
.wrap{max-width:1200px;margin:0 auto;padding:24px 20px 64px}

.topbar{position:sticky;top:0;z-index:10;display:flex;align-items:center;gap:16px;flex-wrap:wrap;
  padding:12px 20px;background:var(--surface);border-bottom:1px solid var(--border)}
.brand{font-weight:700;display:flex;align-items:center;gap:8px}
.brand b{color:var(--primary)}
.dot{width:10px;height:10px;border-radius:50%;background:var(--primary)}
.nav{display:flex;gap:4px;flex-wrap:wrap;margin-left:8px}
.nav-link{padding:8px 12px;border-radius:8px;color:var(--muted);font-weight:500;transition:background .15s,color .15s}
.nav-link:hover{background:var(--bg);color:var(--text)}
.nav-link.active{color:var(--primary);background:color-mix(in srgb,var(--primary) 10%,transparent)}
.btn{margin-left:auto;cursor:pointer;border:1px solid var(--border);background:var(--primary);color:var(--on-primary);
  font-weight:600;padding:9px 16px;border-radius:10px;font-family:var(--sans);transition:opacity .15s,transform .05s}
.btn:hover{opacity:.92}.btn:active{transform:translateY(1px)}.btn:disabled{opacity:.55;cursor:progress}
.btn:focus-visible,a:focus-visible,button:focus-visible{outline:2px solid var(--primary);outline-offset:2px}

.page-title{font-size:1.6rem;margin:8px 0 20px}
.section-title{font-size:1.15rem;margin:28px 0 12px}
.muted{color:var(--muted)}

.stat-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:18px;box-shadow:var(--shadow)}
.stat-num{display:block;font-family:var(--mono);font-size:2rem;font-weight:600;color:var(--primary)}
.stat-lbl{color:var(--muted);font-size:.85rem;text-transform:uppercase;letter-spacing:.04em}

.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow)}
.match-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px;box-shadow:var(--shadow)}
.match-meta{display:flex;justify-content:space-between;color:var(--muted);font-size:.82rem;margin-bottom:10px}
.match-teams{display:flex;align-items:center;justify-content:space-between;gap:10px;font-weight:500}
.match-teams .side{display:flex;align-items:center;gap:8px;flex:1}
.match-teams .side:last-child{justify-content:flex-end;text-align:right}
.vs{font-family:var(--mono);color:var(--muted)}
.flag{width:22px;height:auto;border-radius:2px;flex:none}
.pill{background:color-mix(in srgb,var(--primary) 12%,transparent);color:var(--primary);
  padding:2px 8px;border-radius:999px;font-size:.75rem;font-weight:600}

.table-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:var(--radius)}
table{width:100%;border-collapse:collapse;background:var(--surface)}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap}
th{font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
td.num,th.num{font-family:var(--mono);text-align:right}
tr.qualify td:first-child{box-shadow:inset 3px 0 0 var(--qualify)}

.grid-2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.team-name{font-weight:600}.country-sub{color:var(--muted);font-size:.85rem}
.badge-live{color:var(--live);font-weight:700}
.opp-list{display:flex;flex-wrap:wrap;gap:6px}
.opp{display:inline-flex;align-items:center;gap:6px;background:var(--bg);border:1px solid var(--border);
  border-radius:999px;padding:3px 10px;font-size:.85rem}
.round-row{display:grid;grid-template-columns:64px 1fr;gap:12px;padding:12px 0;border-bottom:1px solid var(--border)}
.round-tag{font-family:var(--mono);font-weight:600;color:var(--primary)}
.foot{max-width:1200px;margin:0 auto;padding:24px 20px;color:var(--muted);font-size:.85rem;border-top:1px solid var(--border)}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
```

- [ ] **Step 7: Add an empty JS file so `base.html` loads, run test, verify pass**

Create `dashboard/static/js/app.js` with a placeholder comment `// refresh polling added in Task 6`.
Run: `./venv/bin/pytest tests/test_dashboard_app.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add dashboard/app.py dashboard/templates/base.html dashboard/templates/overview.html dashboard/static/css/style.css dashboard/static/js/app.js tests/test_dashboard_app.py tests/dashboard_fixture.py
git commit -m "feat(dashboard): app factory, base layout, design-system CSS, overview"
```

---

### Task 4: Teams grid + team detail (roster + path-to-final)

**Files:**
- Modify: `dashboard/app.py` (add `/teams`, `/teams/<tid>`)
- Create: `dashboard/templates/teams.html`
- Create: `dashboard/templates/team_detail.html`
- Test: `tests/test_dashboard_teams.py`

**Interfaces:**
- Consumes: `DataStore.teams/team/roster/projections`.
- Produces routes `GET /teams` and `GET /teams/<tid>` (404 if team missing). Team detail shows both **country and team_name**, the roster, and both projection scenarios from `projections()[tid]`.

- [ ] **Step 1: Write the failing test**

`tests/test_dashboard_teams.py`:
```python
import pytest
from dashboard.app import create_app
from tests.dashboard_fixture import seed


@pytest.fixture
def client(tmp_path):
    seed(tmp_path)
    return create_app(str(tmp_path)).test_client()


def test_teams_grid_shows_country_and_real_name(client):
    body = client.get("/teams").get_data(as_text=True)
    assert "Netherlands" in body and "CS Backbencher" in body
    assert '/teams/42' in body


def test_team_detail_shows_roster_and_path(client):
    r = client.get("/teams/42")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "CS Backbencher" in body and "Zarif Arian" in body      # roster
    assert "GROUP WINNER" in body.upper() or "Group winner" in body
    assert "Argentina" in body and "R32" in body                    # projected opponent + round


def test_missing_team_404(client):
    assert client.get("/teams/does-not-exist").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_dashboard_teams.py -v`
Expected: FAIL (routes not defined → 404 for `/teams/42` too, and the grid assertion fails).

- [ ] **Step 3: Add routes to `dashboard/app.py`** (inside `create_app`, before `return app`)

```python
    @app.route("/teams")
    def teams_page():
        teams = sorted(store.teams(), key=lambda t: (t.get("group") or "", t.get("country") or ""))
        return render_template("teams.html", title="Teams", teams=teams)

    @app.route("/teams/<tid>")
    def team_detail(tid):
        team = store.team(tid)
        if not team:
            abort(404)
        roster = store.roster(tid) or {"players": []}
        projection = store.projections().get(tid, {"scenarios": {}})
        return render_template("team_detail.html", title=team.get("country"),
                               team=team, roster=roster, projection=projection)
```

- [ ] **Step 4: Write `dashboard/templates/teams.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="page-title">Teams <span class="muted">({{ teams|length }})</span></h1>
<div class="card-grid">
  {% for t in teams %}
  <a class="card" href="/teams/{{ t.id }}">
    <div class="match-teams" style="justify-content:flex-start;gap:10px">
      {% if t.flag_url %}<img class="flag" src="{{ asset(t.flag_url) }}" alt="">{% endif %}
      <div>
        <div class="team-name">{{ t.team_name or t.country }}</div>
        <div class="country-sub">{{ t.country }} · Group {{ t.group }}{% if t.faculty %} · {{ t.faculty }}{% endif %}</div>
      </div>
    </div>
  </a>
  {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 5: Write `dashboard/templates/team_detail.html`**

```html
{% extends "base.html" %}
{% block content %}
<a class="muted" href="/teams">← All teams</a>
<h1 class="page-title" style="margin-top:8px">
  {% if team.flag_url %}<img class="flag" src="{{ asset(team.flag_url) }}" alt="" style="width:30px;vertical-align:-4px">{% endif %}
  {{ team.country }} <span class="muted">— {{ team.team_name or "—" }}</span>
</h1>
<p class="muted">Group {{ team.group }}{% if team.faculty %} · {{ team.faculty }}{% endif %}
  {% if team.captain %} · Captain: {{ team.captain.name }}{% endif %}</p>

<div class="grid-2">
  <section class="card">
    <h2 class="section-title" style="margin-top:0">Squad <span class="muted">({{ roster.players|length }})</span></h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>#</th><th>Player</th><th class="num">G</th><th class="num">A</th><th class="num">C</th></tr></thead>
        <tbody>
        {% for p in roster.players %}
          <tr><td class="num">{{ p.jersey_number or '' }}</td>
              <td>{{ p.name }}{% if p.is_captain %} <span class="pill">C</span>{% endif %}</td>
              <td class="num">{{ p.goals }}</td><td class="num">{{ p.assists }}</td><td class="num">{{ p.cards }}</td></tr>
        {% else %}
          <tr><td colspan="5" class="muted">No roster data.</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </section>

  <section class="card">
    <h2 class="section-title" style="margin-top:0">Path to the final</h2>
    {% for scen, rounds in projection.scenarios.items() %}
      <h3 style="font-size:.95rem">{{ 'As group winner' if scen == 'group_winner' else 'As runner-up' }}</h3>
      {% for r in rounds %}
      <div class="round-row">
        <span class="round-tag">{{ r.round }}</span>
        <div class="opp-list">
          {% for o in r.possible_opponents %}
            <span class="opp">{{ o.country }}{% if o.team_name %} <span class="muted">{{ o.team_name }}</span>{% endif %}</span>
          {% else %}<span class="muted">(none)</span>{% endfor %}
        </div>
      </div>
      {% endfor %}
    {% else %}
      <p class="muted">No projection available.</p>
    {% endfor %}
  </section>
</div>
{% endblock %}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_dashboard_teams.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add dashboard/app.py dashboard/templates/teams.html dashboard/templates/team_detail.html tests/test_dashboard_teams.py
git commit -m "feat(dashboard): teams grid and team detail with path-to-final"
```

---

### Task 5: Fixtures, standings, bracket, scorers

**Files:**
- Modify: `dashboard/app.py` (add 4 routes)
- Create: `dashboard/templates/fixtures.html`, `standings.html`, `bracket.html`, `scorers.html`
- Test: `tests/test_dashboard_views.py`

**Interfaces:**
- Consumes: `DataStore.fixtures/standings/bracket/scorers`.
- Produces routes `GET /fixtures`, `/standings`, `/bracket`, `/scorers`. Fixtures grouped by `date` (insertion order preserved). Standings render one table per group with the `qualify` row marker. Bracket renders stage columns using labels (or resolved team names).

- [ ] **Step 1: Write the failing test**

`tests/test_dashboard_views.py`:
```python
import pytest
from dashboard.app import create_app
from tests.dashboard_fixture import seed


@pytest.fixture
def client(tmp_path):
    seed(tmp_path)
    return create_app(str(tmp_path)).test_client()


def test_fixtures_view(client):
    body = client.get("/fixtures").get_data(as_text=True)
    assert "Turkey/Turkiye" in body and "Netherlands" in body and "Jul 28" in body


def test_standings_view(client):
    r = client.get("/standings")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Group A" in body and "Turkey/Turkiye" in body and "Pts" in body


def test_bracket_view(client):
    body = client.get("/bracket").get_data(as_text=True)
    assert "R32" in body and "Final" in body and "1st of Group A" in body


def test_scorers_empty_state(client):
    body = client.get("/scorers").get_data(as_text=True)
    assert "scorer" in body.lower()          # empty-state copy, no crash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_dashboard_views.py -v`
Expected: FAIL (routes 404).

- [ ] **Step 3: Add routes to `dashboard/app.py`** (before `return app`)

```python
    @app.route("/fixtures")
    def fixtures_page():
        days = {}
        for f in store.fixtures():
            days.setdefault(f.get("date") or "TBD", []).append(f)
        return render_template("fixtures.html", title="Fixtures", days=days)

    @app.route("/standings")
    def standings_page():
        return render_template("standings.html", title="Standings", groups=store.standings())

    @app.route("/bracket")
    def bracket_page():
        return render_template("bracket.html", title="Bracket", stages=store.bracket())

    @app.route("/scorers")
    def scorers_page():
        return render_template("scorers.html", title="Top Scorers", scorers=store.scorers())
```

- [ ] **Step 4: Write `dashboard/templates/fixtures.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="page-title">Fixtures</h1>
{% for day, matches in days.items() %}
  <h2 class="section-title">{{ day }}</h2>
  <div class="card-grid">
    {% for f in matches %}
    <article class="match-card">
      <div class="match-meta">
        <span class="pill">{{ 'Group ' ~ f.group if f.group in 'ABCDEFGHIJKLMNOP' else f.group }}</span>
        <span>{{ f.time }}{% if f.status == 'live' %} · <span class="badge-live">LIVE</span>{% endif %}</span>
      </div>
      <div class="match-teams">
        <span class="side">{% if f.home.flag_code %}<img class="flag" src="{{ asset('/assets/flags/w40/' ~ f.home.flag_code ~ '.png') }}" alt="">{% endif %}{{ f.home.country }}</span>
        <span class="vs">{{ f.raw_score if f.status == 'scheduled' else (f.home_score|string ~ ':' ~ f.away_score|string) }}</span>
        <span class="side">{% if f.away.flag_code %}<img class="flag" src="{{ asset('/assets/flags/w40/' ~ f.away.flag_code ~ '.png') }}" alt="">{% endif %}{{ f.away.country }}</span>
      </div>
    </article>
    {% endfor %}
  </div>
{% endfor %}
{% endblock %}
```

- [ ] **Step 5: Write `dashboard/templates/standings.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="page-title">Standings</h1>
<div class="grid-2">
  {% for g in groups %}
  <section class="card">
    <h2 class="section-title" style="margin-top:0">Group {{ g.group }}</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>#</th><th>Nation</th><th class="num">P</th><th class="num">Pts</th><th class="num">GD</th><th class="num">GF</th><th class="num">FP</th></tr></thead>
        <tbody>
        {% for row in g.table %}
          <tr class="{{ 'qualify' if row.qualified }}">
            <td class="num">{{ row.position }}</td><td>{{ row.country }}</td>
            <td class="num">{{ row.played }}</td><td class="num">{{ row.points }}</td>
            <td class="num">{{ row.goal_diff }}</td><td class="num">{{ row.goals_for }}</td><td class="num">{{ row.fair_play }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </section>
  {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 6: Write `dashboard/templates/bracket.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="page-title">Knockout Bracket</h1>
<div class="table-wrap" style="padding:8px">
  <div style="display:flex;gap:16px;min-width:max-content">
    {% for stage in stages %}
    <div style="min-width:220px">
      <h2 class="section-title" style="margin-top:0">{{ stage.stage }}</h2>
      {% for m in stage.matches %}
      <div class="card" style="margin-bottom:10px;padding:12px">
        <div class="muted" style="font-size:.75rem">Match {{ m.match_no }}</div>
        <div>{{ m.home_team or m.home_label or 'TBD' }}</div>
        <div class="muted" style="font-size:.8rem">vs</div>
        <div>{{ m.away_team or m.away_label or 'TBD' }}</div>
      </div>
      {% endfor %}
    </div>
    {% endfor %}
  </div>
</div>
{% endblock %}
```

- [ ] **Step 7: Write `dashboard/templates/scorers.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="page-title">Top Scorers</h1>
{% if scorers %}
<div class="table-wrap">
  <table>
    <thead><tr><th>#</th><th>Player</th><th>Team</th><th class="num">Goals</th></tr></thead>
    <tbody>
    {% for s in scorers %}
      <tr><td class="num">{{ s.rank }}</td><td>{{ s.name }}</td><td>{{ s.team }}</td><td class="num">{{ s.goals }}</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% else %}
<div class="card"><p class="muted">No goals have been recorded yet — top scorers will appear after the first goal.</p></div>
{% endif %}
{% endblock %}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_dashboard_views.py -v`
Expected: PASS (4 tests).

- [ ] **Step 9: Commit**

```bash
git add dashboard/app.py dashboard/templates/fixtures.html dashboard/templates/standings.html dashboard/templates/bracket.html dashboard/templates/scorers.html tests/test_dashboard_views.py
git commit -m "feat(dashboard): fixtures, standings, bracket, scorers views"
```

---

### Task 6: Refresh endpoints + JS polling + live smoke run

**Files:**
- Modify: `dashboard/app.py` (add `POST /refresh`, `GET /refresh/status`)
- Modify: `dashboard/static/js/app.js` (button + polling + theme toggle)
- Modify: `README.md`
- Test: `tests/test_dashboard_refresh.py`

**Interfaces:**
- Consumes: injected `RefreshJob` (tests pass a fake).
- Produces: `POST /refresh` → `{"started": bool, ...status}`; `GET /refresh/status` → status dict. JS: clicking the button POSTs `/refresh`, disables itself, polls `/refresh/status` every 2s, and reloads the page on `done`.

- [ ] **Step 1: Write the failing test**

`tests/test_dashboard_refresh.py`:
```python
import pytest
from dashboard.app import create_app
from dashboard.jobs import RefreshJob
from tests.dashboard_fixture import seed


class FakeJob:
    def __init__(self):
        self._started = False
    def start(self):
        was = self._started
        self._started = True
        return not was
    def status(self):
        return {"state": "running" if self._started else "idle",
                "started_at": None, "finished_at": None, "error": None}


@pytest.fixture
def client(tmp_path):
    seed(tmp_path)
    return create_app(str(tmp_path), job=FakeJob()).test_client()


def test_refresh_starts_and_reports(client):
    r = client.post("/refresh")
    assert r.status_code == 200 and r.get_json()["started"] is True
    r2 = client.post("/refresh")
    assert r2.get_json()["started"] is False           # single-flight
    assert client.get("/refresh/status").get_json()["state"] == "running"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_dashboard_refresh.py -v`
Expected: FAIL (routes 404).

- [ ] **Step 3: Add routes to `dashboard/app.py`** (before `return app`)

```python
    @app.route("/refresh", methods=["POST"])
    def refresh():
        started = refresh_job.start()
        return jsonify(started=started, **refresh_job.status())

    @app.route("/refresh/status")
    def refresh_status():
        return jsonify(refresh_job.status())
```

- [ ] **Step 4: Write `dashboard/static/js/app.js`**

```javascript
// Theme toggle persistence (respects OS default unless user overrides).
(function () {
  const saved = localStorage.getItem("theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
})();

// Background refresh: POST /refresh, poll /refresh/status, reload when done.
(function () {
  const btn = document.getElementById("refresh-btn");
  if (!btn) return;
  let timer = null;

  function poll() {
    fetch("/refresh/status").then((r) => r.json()).then((s) => {
      if (s.state === "running") {
        btn.textContent = "Refreshing…";
        btn.disabled = true;
      } else if (s.state === "done") {
        clearInterval(timer);
        location.reload();
      } else if (s.state === "error") {
        clearInterval(timer);
        btn.disabled = false;
        btn.textContent = "Refresh failed — retry";
      }
    });
  }

  btn.addEventListener("click", () => {
    btn.disabled = true;
    btn.textContent = "Refreshing…";
    fetch("/refresh", { method: "POST" }).then(() => {
      if (timer) clearInterval(timer);
      timer = setInterval(poll, 2000);
    });
  });
})();
```

- [ ] **Step 5: Run test + full suite**

Run: `./venv/bin/pytest tests/test_dashboard_refresh.py -v && ./venv/bin/pytest -q`
Expected: refresh tests PASS; full suite (Phases 1–3) all pass.

- [ ] **Step 6: Live smoke run**

Ensure data exists (`./venv/bin/python -m scraper.run --no-rosters` and `./venv/bin/python -m projection.run` if needed). Then start the server in the background and probe routes:
```bash
./venv/bin/python -m dashboard.app & SERVER=$!
sleep 2
for p in / /teams /teams/42 /fixtures /standings /bracket /scorers; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5000$p")
  echo "$p -> $code"
done
curl -s -o /dev/null -w "refresh_status -> %{http_code}\n" http://127.0.0.1:5000/refresh/status
kill $SERVER
```
Expected: every route prints `200` (use a real team id from `data/latest/teams.json` for the `/teams/<id>` probe if `42` is absent), and `refresh_status -> 200`.

- [ ] **Step 7: Update README and commit**

Add to `README.md`:
```markdown
## Dashboard

```bash
./venv/bin/pip install -r requirements.txt   # installs flask
./venv/bin/python -m dashboard.app           # http://127.0.0.1:5000
```

A local Flask dashboard: overview, teams (country + real name), fixtures, standings, knockout
bracket, top scorers, and each team's possible-opponents path to the final. The **Refresh data**
button re-runs the scraper + projection in the background without blocking the page.
```

Then:
```bash
git add dashboard/app.py dashboard/static/js/app.js README.md tests/test_dashboard_refresh.py
git commit -m "feat(dashboard): background refresh endpoints, polling JS, live run"
```

---

## Self-Review

**1. Spec coverage (§9):**
- Data access with manifest-based cache invalidation → Task 1. ✓
- Background refresh job (single-flight, subprocess scraper+projection) → Task 2; endpoints + JS → Task 6. ✓
- Routes: overview (Task 3); teams + team_detail with path-to-final (Task 4); fixtures, standings, bracket, scorers (Task 5). ✓ (all 7 views)
- Teams show **country + real team_name** → Task 4 test asserts both. ✓
- Path-to-final view reads `projections.json`, both scenarios → Task 4. ✓
- Visual design from MASTER.md (Soft UI, slate+red+amber, Fira, light+dark, focus rings, reduced-motion, responsive, SVG/no-emoji) → Task 3 CSS. ✓
- Dashboard never scrapes inline; only the job does → Tasks 1–2, 6. ✓

**2. Placeholder scan:** No TBD/TODO in code. The bracket template's `'TBD'` is a legitimate *display* fallback for unresolved knockout slots, not a plan gap.

**3. Type consistency:** `create_app(data_dir, job)`, `DataStore` method names, and `RefreshJob.start()/status()` are used identically across `app.py`, tests, and JS (`/refresh`, `/refresh/status`, `state` values `idle/running/done/error`). Template variables (`stats`, `upcoming`, `teams`, `team`, `roster`, `projection`, `days`, `groups`, `stages`, `scorers`) each match the `render_template(...)` call that supplies them. `asset()` and `nav` are provided by the context processor to every template.
