# AIUB World Cup Scraper — Phase 1 (Scraper) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a re-runnable Python scraper for https://ofsportsaiub.org/ that writes the full AIUB World Cup 2026 dataset (teams, rosters, fixtures, standings, scorers, bracket) as structured JSON.

**Architecture:** A thin HTTP client fetches server-rendered HTML from the site's `tab-api.php` endpoint and per-team profile pages. Pure `html -> dataclass` parser functions (one per entity) turn that HTML into typed records. A writer serializes the records to `data/latest/*.json` plus a timestamped snapshot and a run manifest. An orchestrator (`run.py`) wires it together with per-entity isolation and a small CLI.

**Tech Stack:** Python 3, `requests`, `beautifulsoup4`, `lxml`; `pytest` for tests.

**Spec:** `docs/superpowers/specs/2026-07-21-aiub-world-cup-scraper-design.md` (§2–§7 cover this phase).

## Global Constraints

- Python 3.10+ (`list[X]`, `tuple[...]`, `X | None` syntax used throughout).
- Dependencies limited to: `requests`, `beautifulsoup4`, `lxml` (+ `pytest` dev). No headless browser.
- Parsers are **pure functions** `html: str -> dataclass(s)`; **no network in parser code or in any test**.
- Every parser must tolerate BOTH the empty pre-tournament state (scores/points all `0`, scorers empty) AND a populated state — missing/renamed fields yield `None`/`0` + a logged warning, never an exception.
- Real team name = `.profile-team-name` text with the leading `"Team · "` stripped.
- BeautifulSoup parser backend is `"lxml"` in every `BeautifulSoup(html, "lxml")` call.
- Politeness: descriptive User-Agent, ~0.5s delay between requests, retry ×3 with backoff.
- **Commit messages must NOT contain any `Co-Authored-By` or AI-tool trailer** (explicit user directive). Use plain `-m` messages only.
- Base URL constant: `https://ofsportsaiub.org`.

---

### Task 1: Project scaffold + config

**Files:**
- Create: `requirements.txt`
- Create: `scraper/__init__.py` (empty)
- Create: `scraper/parsers/__init__.py` (empty)
- Create: `scraper/config.py`
- Create: `tests/__init__.py` (empty)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `scraper.config.BASE_URL: str`, `config.TABS: dict[str,str]`, `config.USER_AGENT: str`, `config.DEFAULT_DELAY: float`, `config.ENTITY_FILES: tuple[str,...]`.

- [ ] **Step 1: Create the virtualenv and `requirements.txt`**

Run:
```bash
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install requests beautifulsoup4 lxml pytest
```
Create `requirements.txt`:
```
requests>=2.31
beautifulsoup4>=4.12
lxml>=5.0
pytest>=8.0
```

- [ ] **Step 2: Write the failing test**

`tests/test_config.py`:
```python
from scraper import config

def test_base_url_and_tabs():
    assert config.BASE_URL == "https://ofsportsaiub.org"
    assert config.TABS["standings"] == "groups"          # standings tab is served as tab=groups
    assert set(config.TABS) >= {"teams", "fixtures", "standings", "scorers", "bracket"}
    assert config.DEFAULT_DELAY > 0
    assert "teams" in config.ENTITY_FILES
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'scraper'`).

- [ ] **Step 4: Create the package files and `scraper/config.py`**

Create empty `scraper/__init__.py`, `scraper/parsers/__init__.py`, `tests/__init__.py`.
`scraper/config.py`:
```python
"""Static configuration for the scraper."""

BASE_URL = "https://ofsportsaiub.org"

# Logical entity name -> tab-api.php `tab` value.
TABS = {
    "teams": "teams",
    "fixtures": "fixtures",
    "standings": "groups",
    "scorers": "scorers",
    "bracket": "bracket",
}

USER_AGENT = (
    "aiub-worldcup-scraper/1.0 (personal tournament dataset; "
    "contact: idublinfourir@gmail.com)"
)

DEFAULT_DELAY = 0.5          # seconds between requests
DEFAULT_TIMEOUT = 20         # seconds
DEFAULT_RETRIES = 3

# Files written under data/latest/
ENTITY_FILES = ("teams", "rosters", "fixtures", "standings", "scorers", "bracket")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt scraper/__init__.py scraper/config.py scraper/parsers/__init__.py tests/__init__.py tests/test_config.py
git commit -m "feat(scraper): project scaffold and static config"
```

---

### Task 2: Data models

**Files:**
- Create: `scraper/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces dataclasses (all fields keyword-constructible): `Captain`, `Team`, `Player`, `Roster`, `FixtureSide`, `Fixture`, `StandingRow`, `GroupStanding`, `Scorer`, `KnockoutMatch`, `BracketStage`. Field lists exactly as below — later tasks construct these by keyword.

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
from dataclasses import asdict
from scraper.models import Team, Captain, Fixture, FixtureSide

def test_team_round_trips_to_dict():
    t = Team(id="42", slug="netherlands", profile_url="/teams/42-netherlands",
             flag_url="/f/nl.png", country="Netherlands", team_name="CS Backbencher",
             faculty="FST", group="A",
             captain=Captain(player_id="657", name="Zarif Arian", player_url="/players/657-x"))
    d = asdict(t)
    assert d["country"] == "Netherlands" and d["team_name"] == "CS Backbencher"
    assert d["captain"]["name"] == "Zarif Arian"

def test_fixture_defaults_unplayed():
    f = Fixture(match_id="1", slug="a-vs-b", match_url="/m/1", match_no=1, group="A",
                date="Jul 28", time="8:00 AM", datetime_iso=None,
                home=FixtureSide(country="Turkey/Turkiye", flag_code="tr"),
                away=FixtureSide(country="Netherlands", flag_code="nl"),
                home_score=None, away_score=None, status="scheduled", raw_score="VS")
    assert f.home.flag_code == "tr" and f.home_score is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'scraper.models'`).

- [ ] **Step 3: Write `scraper/models.py`**

```python
"""Typed records for every scraped entity (see spec §3)."""
from dataclasses import dataclass, field

@dataclass
class Captain:
    player_id: str
    name: str
    player_url: str

@dataclass
class Team:
    id: str
    slug: str
    profile_url: str
    flag_url: str | None
    country: str
    team_name: str | None
    faculty: str | None
    group: str
    captain: Captain | None = None

@dataclass
class Player:
    player_id: str
    slug: str
    player_url: str
    jersey_number: str | None
    name: str
    role: str | None
    is_captain: bool
    photo_url: str | None
    goals: int
    assists: int
    cards: int

@dataclass
class Roster:
    team_id: str
    country: str
    team_name: str | None
    players: list[Player] = field(default_factory=list)

@dataclass
class FixtureSide:
    country: str
    flag_code: str | None

@dataclass
class Fixture:
    match_id: str
    slug: str
    match_url: str
    match_no: int | None
    group: str | None
    date: str | None
    time: str | None
    datetime_iso: str | None
    home: FixtureSide
    away: FixtureSide
    home_score: int | None
    away_score: int | None
    status: str
    raw_score: str

@dataclass
class StandingRow:
    position: int
    team_id: str | None
    country: str
    team_url: str | None
    played: int
    points: int
    goal_diff: int
    goals_for: int
    fair_play: int
    qualified: bool

@dataclass
class GroupStanding:
    group: str
    table: list[StandingRow] = field(default_factory=list)

@dataclass
class Scorer:
    rank: int
    player_id: str | None
    name: str
    team: str | None
    goals: int

@dataclass
class KnockoutMatch:
    match_no: int | None
    next_match_no: int | None
    match_url: str | None
    stage: str
    home_label: str | None
    away_label: str | None
    home_team: str | None
    away_team: str | None
    home_score: int | None
    away_score: int | None
    status: str

@dataclass
class BracketStage:
    stage: str
    matches: list[KnockoutMatch] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper/models.py tests/test_models.py
git commit -m "feat(scraper): typed data models for all entities"
```

---

### Task 3: HTTP client

**Files:**
- Create: `scraper/client.py`
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: `scraper.config`.
- Produces: `Client(base_url=config.BASE_URL, delay=0.0, timeout=..., retries=...)` with methods `fetch_tab(name: str) -> str` (GETs `tab-api.php?tab=<name>`, returns the unwrapped `html` string) and `fetch_page(path: str) -> str` (GETs an absolute path/URL, returns `.text`).

- [ ] **Step 1: Write the failing test** (uses `monkeypatch`, no real network)

`tests/test_client.py`:
```python
import json
from scraper.client import Client

class FakeResp:
    def __init__(self, *, text="", payload=None, status=200):
        self._text = text
        self._payload = payload
        self.status_code = status
    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"status {self.status_code}")
    @property
    def text(self):
        return self._text
    def json(self):
        return self._payload

def test_fetch_tab_unwraps_html(monkeypatch):
    c = Client(delay=0.0)
    calls = {}
    def fake_get(url, timeout=None):
        calls["url"] = url
        return FakeResp(payload={"html": "<div>hi</div>", "tab": "teams"})
    monkeypatch.setattr(c.session, "get", fake_get)
    html = c.fetch_tab("teams")
    assert html == "<div>hi</div>"
    assert calls["url"] == "https://ofsportsaiub.org/tab-api.php?tab=teams"

def test_fetch_page_returns_text(monkeypatch):
    c = Client(delay=0.0)
    monkeypatch.setattr(c.session, "get", lambda url, timeout=None: FakeResp(text="<h1>NL</h1>"))
    assert c.fetch_page("/teams/42-netherlands") == "<h1>NL</h1>"

def test_get_retries_then_raises(monkeypatch):
    c = Client(delay=0.0, retries=3)
    n = {"i": 0}
    def boom(url, timeout=None):
        n["i"] += 1
        return FakeResp(status=503)
    monkeypatch.setattr(c.session, "get", boom)
    import pytest, requests
    with pytest.raises(requests.HTTPError):
        c.fetch_tab("teams")
    assert n["i"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_client.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'scraper.client'`).

- [ ] **Step 3: Write `scraper/client.py`**

```python
"""HTTP client: polite, retrying access to the tournament site."""
import logging
import time
import requests

from scraper import config

log = logging.getLogger(__name__)

class Client:
    def __init__(self, base_url=config.BASE_URL, delay=config.DEFAULT_DELAY,
                 timeout=config.DEFAULT_TIMEOUT, retries=config.DEFAULT_RETRIES,
                 user_agent=config.USER_AGENT):
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": user_agent, "X-Requested-With": "XMLHttpRequest"}
        )

    def _get(self, url):
        last_exc = None
        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                log.warning("GET %s failed (%d/%d): %s", url, attempt, self.retries, exc)
                if attempt < self.retries:
                    time.sleep(self.delay * attempt)
        raise last_exc

    def fetch_tab(self, name):
        if self.delay:
            time.sleep(self.delay)
        url = f"{self.base_url}/tab-api.php?tab={name}"
        return self._get(url).json().get("html", "")

    def fetch_page(self, path):
        if self.delay:
            time.sleep(self.delay)
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        return self._get(url).text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_client.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scraper/client.py tests/test_client.py
git commit -m "feat(scraper): polite retrying HTTP client with tab-api unwrap"
```

---

### Task 4: Teams parser

**Files:**
- Create: `scraper/parsers/teams.py`
- Test: `tests/test_parse_teams.py`

**Interfaces:**
- Consumes: `scraper.models.Team`.
- Produces: `parse_teams(html: str) -> list[Team]` (stubs only: `team_name=None`, `captain=None`; enriched later by the profile parser).

- [ ] **Step 1: Write the failing test**

`tests/test_parse_teams.py`:
```python
from scraper.parsers.teams import parse_teams

HTML = """
<div class="teams-directory-grid">
  <a class="team-directory-card" href="/teams/38-algeria" data-search="algeria bba blackout fba group a">
    <span class="team-directory-flag"><img class="flag-icon" src="/assets/flags/w40/dz.png"></span>
    <span class="team-directory-names"><strong>Algeria</strong><small>FBA</small></span>
    <span class="team-directory-group">Group A</span>
  </a>
  <a class="team-directory-card" href="/teams/42-netherlands">
    <span class="team-directory-names"><strong>Netherlands</strong><small>FST</small></span>
    <span class="team-directory-group">Group A</span>
  </a>
</div>
"""

def test_parse_teams_extracts_directory_fields():
    teams = parse_teams(HTML)
    assert len(teams) == 2
    algeria = teams[0]
    assert algeria.id == "38" and algeria.slug == "algeria"
    assert algeria.country == "Algeria" and algeria.faculty == "FBA"
    assert algeria.group == "A"
    assert algeria.profile_url == "/teams/38-algeria"
    assert algeria.flag_url == "/assets/flags/w40/dz.png"
    assert algeria.team_name is None and algeria.captain is None
    assert teams[1].flag_url is None   # missing flag -> None, no crash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_parse_teams.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `scraper/parsers/teams.py`**

```python
"""Parse the teams-directory fragment (tab=teams) into Team stubs."""
from bs4 import BeautifulSoup
from scraper.models import Team

def parse_teams(html: str) -> list[Team]:
    soup = BeautifulSoup(html, "lxml")
    teams: list[Team] = []
    for card in soup.select("a.team-directory-card"):
        href = card.get("href", "")
        last = href.rsplit("/", 1)[-1]              # "38-algeria"
        team_id, _, slug = last.partition("-")
        strong = card.select_one("strong")
        country = strong.get_text(strip=True) if strong else ""
        small = card.select_one("small")
        faculty = small.get_text(strip=True) if small else None
        group_el = card.select_one(".team-directory-group")
        group = group_el.get_text(strip=True).replace("Group", "").strip() if group_el else ""
        flag = card.select_one("img.flag-icon")
        flag_url = flag.get("src") if flag else None
        teams.append(Team(
            id=team_id, slug=slug, profile_url=href, flag_url=flag_url,
            country=country, team_name=None, faculty=faculty, group=group, captain=None,
        ))
    return teams
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_parse_teams.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper/parsers/teams.py tests/test_parse_teams.py
git commit -m "feat(scraper): teams directory parser"
```

---

### Task 5: Team profile parser (real name, captain, roster)

**Files:**
- Create: `scraper/parsers/profile.py`
- Test: `tests/test_parse_profile.py`

**Interfaces:**
- Consumes: `scraper.models.Team`, `Roster`, `Player`, `Captain`.
- Produces: `parse_profile(html: str, team: Team) -> tuple[Team, Roster]` — returns an enriched copy of `team` (with `country`, `team_name`, `captain` filled) and its `Roster`.

- [ ] **Step 1: Write the failing test**

`tests/test_parse_profile.py`:
```python
from dataclasses import replace
from scraper.models import Team
from scraper.parsers.profile import parse_profile

STUB = Team(id="42", slug="netherlands", profile_url="/teams/42-netherlands",
            flag_url="/f/nl.png", country="Netherlands", team_name=None,
            faculty="FST", group="A", captain=None)

HTML = """
<div class="profile-identity">
  <div><h1>Netherlands</h1>
    <div class="profile-meta">
      <span class="profile-team-name">Team · CS BACKBENCHER</span>
      <span>Group A</span><span>FST</span>
    </div>
  </div>
</div>
<a class="profile-captain-feature" href="/players/657-zarif-arian">
  <span class="profile-captain-copy"><em>Captain</em><strong>Zarif Arian</strong><span>#1</span></span>
</a>
<a class="profile-player profile-player-captain " href="/players/657-zarif-arian">
  <span class="profile-player-photo"><img src="/img/a.png"><b>01</b></span>
  <div><strong>Zarif Arian</strong><small>Player</small>
       <span class="roster-captain-mark"><b>C</b> Team captain</span></div>
  <div class="player-totals"><span><b>0</b> goals</span><span><b>0</b> assists</span><span><b>0</b> cards</span></div>
</a>
<a class="profile-player  " href="/players/658-rezuwanul-haque-rezu">
  <span class="profile-player-photo"><img src="/img/b.jpeg"><b>02</b></span>
  <div><strong>Rezuwanul Haque</strong><small>Player</small></div>
  <div class="player-totals"><span><b>1</b> goals</span><span><b>2</b> assists</span><span><b>3</b> cards</span></div>
</a>
"""

def test_profile_extracts_real_name_captain_and_roster():
    team, roster = parse_profile(HTML, STUB)
    assert team.country == "Netherlands"
    assert team.team_name == "CS BACKBENCHER"          # "Team · " prefix stripped
    assert team.captain.player_id == "657" and team.captain.name == "Zarif Arian"
    assert roster.team_id == "42" and roster.team_name == "CS BACKBENCHER"
    assert len(roster.players) == 2
    cap, other = roster.players
    assert cap.is_captain is True and cap.jersey_number == "01"
    assert other.is_captain is False
    assert (other.goals, other.assists, other.cards) == (1, 2, 3)
    assert other.player_id == "658"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_parse_profile.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `scraper/parsers/profile.py`**

```python
"""Parse a team profile page into (enriched Team, Roster)."""
from dataclasses import replace
from bs4 import BeautifulSoup
from scraper.models import Team, Roster, Player, Captain

def _digits(text: str) -> int:
    d = "".join(c for c in (text or "") if c.isdigit())
    return int(d) if d else 0

def _strip_team_prefix(text: str) -> str:
    text = (text or "").strip()
    if "·" in text:
        return text.split("·", 1)[1].strip()
    if text.lower().startswith("team"):
        return text[4:].strip()
    return text

def parse_profile(html: str, team: Team) -> tuple[Team, Roster]:
    soup = BeautifulSoup(html, "lxml")

    h1 = soup.select_one("h1")
    country = h1.get_text(strip=True) if h1 else team.country

    tn = soup.select_one(".profile-team-name")
    team_name = _strip_team_prefix(tn.get_text(strip=True)) if tn else None

    captain = None
    cap = soup.select_one("a.profile-captain-feature")
    if cap:
        href = cap.get("href", "")
        cap_id = href.rsplit("/", 1)[-1].partition("-")[0]
        name_el = cap.select_one(".profile-captain-copy strong") or cap.select_one("strong")
        captain = Captain(player_id=cap_id,
                          name=name_el.get_text(strip=True) if name_el else "",
                          player_url=href)

    players: list[Player] = []
    for p in soup.select("a.profile-player"):
        href = p.get("href", "")
        last = href.rsplit("/", 1)[-1]
        pid, _, slug = last.partition("-")
        photo = p.select_one(".profile-player-photo img")
        num = p.select_one(".profile-player-photo b")
        name_el = p.select_one("strong")
        role_el = p.select_one("small")
        classes = p.get("class", [])
        is_captain = "profile-player-captain" in classes or bool(p.select_one(".roster-captain-mark"))
        totals = p.select(".player-totals span")
        goals = _digits(totals[0].get_text()) if len(totals) > 0 else 0
        assists = _digits(totals[1].get_text()) if len(totals) > 1 else 0
        cards = _digits(totals[2].get_text()) if len(totals) > 2 else 0
        players.append(Player(
            player_id=pid, slug=slug, player_url=href,
            jersey_number=num.get_text(strip=True) if num else None,
            name=name_el.get_text(strip=True) if name_el else "",
            role=role_el.get_text(strip=True) if role_el else None,
            is_captain=is_captain,
            photo_url=photo.get("src") if photo else None,
            goals=goals, assists=assists, cards=cards,
        ))

    enriched = replace(team, country=country or team.country, team_name=team_name, captain=captain)
    roster = Roster(team_id=team.id, country=country or team.country,
                    team_name=team_name, players=players)
    return enriched, roster
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_parse_profile.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper/parsers/profile.py tests/test_parse_profile.py
git commit -m "feat(scraper): team profile parser (real name, captain, roster)"
```

---

### Task 6: Fixtures parser

**Files:**
- Create: `scraper/parsers/fixtures.py`
- Test: `tests/test_parse_fixtures.py`

**Interfaces:**
- Consumes: `scraper.models.Fixture`, `FixtureSide`.
- Produces: `parse_fixtures(html: str) -> list[Fixture]`.

- [ ] **Step 1: Write the failing test** (covers unplayed AND a played card)

`tests/test_parse_fixtures.py`:
```python
from scraper.parsers.fixtures import parse_fixtures

HTML = """
<div class="fixture-board">
  <article class="fixture-row google-fixture" data-fixture-card
           data-fixture-search-text="turkey/turkiye netherlands">
    <a class="fixture-card-link" href="/matches/15968-turkey-turkiye-vs-netherlands"></a>
    <div class="fixture-card-head"><span>Group A</span><span>Jul 28, 8:00 AM</span></div>
    <div class="fixture-card-main">
      <div class="fixture-side home"><span class="fixture-team">
        <img class="flag-icon" src="/assets/flags/w40/tr.png"> Turkey/Turkiye</span></div>
      <strong class="fixture-score" data-live-fixture-score>VS</strong>
      <div class="fixture-side away"><span class="fixture-team">
        <img class="flag-icon" src="/assets/flags/w40/nl.png"> Netherlands</span></div>
    </div>
    <div class="fixture-card-foot"><span class="fixture-no">Match 1</span>
      <span class="fixture-status">Scheduled</span></div>
  </article>
  <article class="fixture-row google-fixture" data-fixture-card>
    <a class="fixture-card-link" href="/matches/15969-japan-vs-mexico"></a>
    <div class="fixture-card-head"><span>Group B</span><span>Jul 28, 10:00 AM</span></div>
    <div class="fixture-card-main">
      <div class="fixture-side home"><span class="fixture-team">
        <img class="flag-icon" src="/assets/flags/w40/jp.png"> Japan</span></div>
      <strong class="fixture-score" data-live-fixture-score>2:1</strong>
      <div class="fixture-side away"><span class="fixture-team">
        <img class="flag-icon" src="/assets/flags/w40/mx.png"> Mexico</span></div>
    </div>
    <div class="fixture-card-foot"><span class="fixture-no">Match 2</span>
      <span class="fixture-status">Full time</span></div>
  </article>
</div>
"""

def test_parse_fixtures_unplayed_and_played():
    fx = parse_fixtures(HTML)
    assert len(fx) == 2
    a = fx[0]
    assert a.match_id == "15968" and a.match_no == 1 and a.group == "A"
    assert a.date == "Jul 28" and a.time == "8:00 AM"
    assert a.home.country == "Turkey/Turkiye" and a.home.flag_code == "tr"
    assert a.away.country == "Netherlands" and a.away.flag_code == "nl"
    assert a.raw_score == "VS" and a.home_score is None and a.status == "scheduled"
    b = fx[1]
    assert b.home_score == 2 and b.away_score == 1 and b.status == "final"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_parse_fixtures.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `scraper/parsers/fixtures.py`**

```python
"""Parse the fixtures fragment (tab=fixtures) into Fixture records."""
import re
from bs4 import BeautifulSoup
from scraper.models import Fixture, FixtureSide

_MATCH_NO = re.compile(r"Match\s*(\d+)", re.I)
_FLAG = re.compile(r"/([a-z]{2})\.png")

def _flag_code(team_el):
    img = team_el.select_one("img") if team_el else None
    if not img:
        return None
    m = _FLAG.search(img.get("src", ""))
    return m.group(1) if m else None

def _split_score(raw):
    raw = (raw or "").strip()
    if raw and raw.upper() != "VS" and ":" in raw:
        h, _, a = raw.partition(":")
        try:
            return int(h), int(a)
        except ValueError:
            return None, None
    return None, None

def parse_fixtures(html: str) -> list[Fixture]:
    soup = BeautifulSoup(html, "lxml")
    out: list[Fixture] = []
    for card in soup.select("article.fixture-row"):
        link = card.select_one("a.fixture-card-link")
        href = link.get("href", "") if link else ""
        last = href.rsplit("/", 1)[-1]
        match_id = last.partition("-")[0]

        head = card.select(".fixture-card-head span")
        group = head[0].get_text(strip=True).replace("Group", "").strip() if len(head) > 0 else None
        dt = head[1].get_text(strip=True) if len(head) > 1 else None
        date = time = None
        if dt:
            parts = dt.split(",", 1)
            date = parts[0].strip()
            time = parts[1].strip() if len(parts) > 1 else None

        home_el = card.select_one(".fixture-side.home .fixture-team")
        away_el = card.select_one(".fixture-side.away .fixture-team")
        home_country = home_el.get_text(strip=True) if home_el else ""
        away_country = away_el.get_text(strip=True) if away_el else ""

        score_el = card.select_one(".fixture-score")
        raw_score = score_el.get_text(strip=True) if score_el else "VS"
        hs, as_ = _split_score(raw_score)

        no_el = card.select_one(".fixture-no")
        if no_el and _MATCH_NO.search(no_el.get_text()):
            match_no = int(_MATCH_NO.search(no_el.get_text()).group(1))
        else:
            match_no = None

        status_el = card.select_one(".fixture-status")
        status_txt = status_el.get_text(strip=True).lower() if status_el else ""
        if raw_score.upper() == "VS":
            status = "scheduled"
        elif "live" in status_txt or "'" in status_txt:
            status = "live"
        else:
            status = "final"

        out.append(Fixture(
            match_id=match_id, slug=last.partition("-")[2], match_url=href,
            match_no=match_no, group=group, date=date, time=time, datetime_iso=None,
            home=FixtureSide(country=home_country, flag_code=_flag_code(home_el)),
            away=FixtureSide(country=away_country, flag_code=_flag_code(away_el)),
            home_score=hs, away_score=as_, status=status, raw_score=raw_score,
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_parse_fixtures.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper/parsers/fixtures.py tests/test_parse_fixtures.py
git commit -m "feat(scraper): fixtures parser (scheduled + played states)"
```

---

### Task 7: Standings parser

**Files:**
- Create: `scraper/parsers/standings.py`
- Test: `tests/test_parse_standings.py`

**Interfaces:**
- Consumes: `scraper.models.GroupStanding`, `StandingRow`.
- Produces: `parse_standings(html: str) -> list[GroupStanding]`.

- [ ] **Step 1: Write the failing test**

`tests/test_parse_standings.py`:
```python
from scraper.parsers.standings import parse_standings

HTML = """
<div class="panel"><h3>Group A</h3>
  <table class="data-table">
    <thead><tr><th>Nation</th><th>P</th><th>Pts</th><th>GD</th><th>GF</th><th>FP</th></tr></thead>
    <tbody>
      <tr class="qualify"><td><a href="/teams/30-turkey-turkiye">Turkey/Turkiye</a></td>
        <td>2</td><td>6</td><td>3</td><td>4</td><td>0</td></tr>
      <tr class="qualify"><td><a href="/teams/42-netherlands">Netherlands</a></td>
        <td>2</td><td>3</td><td>0</td><td>2</td><td>1</td></tr>
      <tr><td><a href="/teams/99-foo">Foo</a></td>
        <td>2</td><td>0</td><td>-3</td><td>1</td><td>2</td></tr>
    </tbody>
  </table>
</div>
"""

def test_parse_standings():
    groups = parse_standings(HTML)
    assert len(groups) == 1
    g = groups[0]
    assert g.group == "A" and len(g.table) == 3
    top = g.table[0]
    assert top.position == 1 and top.country == "Turkey/Turkiye"
    assert top.team_id == "30" and top.played == 2 and top.points == 6
    assert top.goal_diff == 3 and top.goals_for == 4 and top.qualified is True
    assert g.table[2].qualified is False and g.table[2].goal_diff == -3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_parse_standings.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `scraper/parsers/standings.py`**

```python
"""Parse the standings fragment (tab=groups) into GroupStanding records."""
from bs4 import BeautifulSoup
from scraper.models import GroupStanding, StandingRow

def _to_int(text: str) -> int:
    text = (text or "").strip().replace("+", "")
    try:
        return int(text)
    except ValueError:
        return 0

def parse_standings(html: str) -> list[GroupStanding]:
    soup = BeautifulSoup(html, "lxml")
    groups: list[GroupStanding] = []
    for table in soup.select("table.data-table"):
        panel = table.find_parent(class_="panel")
        h3 = panel.select_one("h3") if panel else None
        group = h3.get_text(strip=True).replace("Group", "").strip() if h3 else "?"
        rows: list[StandingRow] = []
        for i, tr in enumerate(table.select("tbody tr"), start=1):
            tds = tr.select("td")
            if not tds:
                continue
            link = tds[0].select_one("a")
            country = (link or tds[0]).get_text(strip=True)
            href = link.get("href", "") if link else ""
            team_id = href.rsplit("/", 1)[-1].partition("-")[0] if href else None
            vals = [_to_int(td.get_text()) for td in tds[1:6]]
            vals += [0] * (5 - len(vals))
            played, points, gd, gf, fp = vals[:5]
            rows.append(StandingRow(
                position=i, team_id=team_id, country=country, team_url=href or None,
                played=played, points=points, goal_diff=gd, goals_for=gf, fair_play=fp,
                qualified="qualify" in tr.get("class", []),
            ))
        groups.append(GroupStanding(group=group, table=rows))
    return groups
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_parse_standings.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper/parsers/standings.py tests/test_parse_standings.py
git commit -m "feat(scraper): standings parser"
```

---

### Task 8: Scorers parser

**Files:**
- Create: `scraper/parsers/scorers.py`
- Test: `tests/test_parse_scorers.py`

**Interfaces:**
- Consumes: `scraper.models.Scorer`.
- Produces: `parse_scorers(html: str) -> list[Scorer]` — returns `[]` for the empty-state panel.

> Note: the tournament is pre-goals, so only the empty state exists live. The populated selectors below are a best-effort guess and MUST be re-verified against real HTML once the first goal is scored (spec §2). The empty-state test is the authoritative one for now.

- [ ] **Step 1: Write the failing test**

`tests/test_parse_scorers.py`:
```python
from scraper.parsers.scorers import parse_scorers

EMPTY = '<div class="scorers-shell"><div class="scorers-empty"><h3>The race starts</h3></div></div>'

POPULATED = """
<div class="scorers-shell">
  <ol class="scorers-list">
    <li class="scorers-row"><a href="/players/658-rezu"><strong>Rezuwanul Haque</strong></a>
        <small>Netherlands</small><b>3</b></li>
  </ol>
</div>
"""

def test_scorers_empty_state_returns_empty_list():
    assert parse_scorers(EMPTY) == []

def test_scorers_populated_best_effort():
    rows = parse_scorers(POPULATED)
    assert len(rows) == 1
    assert rows[0].rank == 1 and rows[0].name == "Rezuwanul Haque"
    assert rows[0].goals == 3 and rows[0].player_id == "658"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_parse_scorers.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `scraper/parsers/scorers.py`**

```python
"""Parse the top-scorers fragment (tab=scorers). Empty until first goal."""
from bs4 import BeautifulSoup
from scraper.models import Scorer

def _digits(text: str) -> int:
    d = "".join(c for c in (text or "") if c.isdigit())
    return int(d) if d else 0

def parse_scorers(html: str) -> list[Scorer]:
    soup = BeautifulSoup(html, "lxml")
    if soup.select_one(".scorers-empty"):
        return []
    out: list[Scorer] = []
    for i, row in enumerate(soup.select(".scorers-row"), start=1):
        name_el = row.select_one("strong")
        team_el = row.select_one("small")
        goals_el = row.select_one("b")
        link = row.select_one("a[href*='/players/']")
        pid = link.get("href", "").rsplit("/", 1)[-1].partition("-")[0] if link else None
        out.append(Scorer(
            rank=i, player_id=pid,
            name=name_el.get_text(strip=True) if name_el else "",
            team=team_el.get_text(strip=True) if team_el else None,
            goals=_digits(goals_el.get_text()) if goals_el else 0,
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_parse_scorers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper/parsers/scorers.py tests/test_parse_scorers.py
git commit -m "feat(scraper): scorers parser (empty-state + best-effort populated)"
```

---

### Task 9: Bracket parser

**Files:**
- Create: `scraper/parsers/bracket.py`
- Test: `tests/test_parse_bracket.py`

**Interfaces:**
- Consumes: `scraper.models.BracketStage`, `KnockoutMatch`.
- Produces: `parse_bracket(html: str) -> list[BracketStage]`. Slot text like "1st of Group A"/"Winner of M49" goes to `home_label`/`away_label`; a resolved team name goes to `home_team`/`away_team`.

- [ ] **Step 1: Write the failing test**

`tests/test_parse_bracket.py`:
```python
from scraper.parsers.bracket import parse_bracket

HTML = """
<section class="knockout-stage stage-r32" data-bracket-stage>
  <header><span>R32</span><h3>Round of 32</h3></header>
  <article class="knockout-match" data-match-no="49" data-next-match="65">
    <a class="knockout-match-link" href="/matches/16016-home-vs-away"></a>
    <div class="match-meta"><a href="/matches/16016-home-vs-away">Match 49</a><span>R32</span></div>
    <div class="ko-team "><span>1st of Group A</span><b>-</b></div>
    <div class="ko-team "><span>2nd of Group I</span><b>-</b></div>
  </article>
</section>
<section class="knockout-stage stage-r16" data-bracket-stage>
  <header><span>R16</span><h3>Round of 16</h3></header>
  <article class="knockout-match" data-match-no="65" data-next-match="73">
    <div class="match-meta"><a href="/matches/16032-x">Match 65</a><span>R16</span></div>
    <div class="ko-team "><span>Winner of M49</span><b>-</b></div>
    <div class="ko-team "><span>Winner of M50</span><b>-</b></div>
  </article>
</section>
"""

def test_parse_bracket_tree_and_labels():
    stages = parse_bracket(HTML)
    assert [s.stage for s in stages] == ["R32", "R16"]
    m49 = stages[0].matches[0]
    assert m49.match_no == 49 and m49.next_match_no == 65
    assert m49.home_label == "1st of Group A" and m49.away_label == "2nd of Group I"
    assert m49.home_team is None and m49.away_team is None
    assert m49.match_url == "/matches/16016-home-vs-away"
    m65 = stages[1].matches[0]
    assert m65.home_label == "Winner of M49" and m65.next_match_no == 73
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_parse_bracket.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `scraper/parsers/bracket.py`**

```python
"""Parse the knockout-bracket fragment (tab=bracket) into BracketStage records."""
import re
from bs4 import BeautifulSoup
from scraper.models import BracketStage, KnockoutMatch

_STAGE_MAP = {"r32": "R32", "r16": "R16", "qf": "QF", "sf": "SF", "final": "Final"}
_LABEL_RE = re.compile(r"(^\s*(1st|2nd|3rd)\b)|(of group)|(winner of)|(loser of)", re.I)

def _stage_of(section) -> str:
    for cls in section.get("class", []):
        if cls.startswith("stage-"):
            key = cls[len("stage-"):]
            return _STAGE_MAP.get(key, key.upper())
    return "?"

def _is_placeholder(text: str) -> bool:
    return bool(_LABEL_RE.search(text or ""))

def _int_or_none(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

def parse_bracket(html: str) -> list[BracketStage]:
    soup = BeautifulSoup(html, "lxml")
    stages: list[BracketStage] = []
    for section in soup.select("section.knockout-stage"):
        stage = _stage_of(section)
        matches: list[KnockoutMatch] = []
        for art in section.select("article.knockout-match"):
            link = art.select_one("a.knockout-match-link") or art.select_one(".match-meta a")
            sides = art.select(".ko-team")

            def side(i):
                if i >= len(sides):
                    return None, None
                span = sides[i].select_one("span")
                text = span.get_text(strip=True) if span else ""
                if _is_placeholder(text):
                    return text, None          # label
                return None, (text or None)     # resolved team

            home_label, home_team = side(0)
            away_label, away_team = side(1)
            matches.append(KnockoutMatch(
                match_no=_int_or_none(art.get("data-match-no")),
                next_match_no=_int_or_none(art.get("data-next-match")),
                match_url=link.get("href") if link else None,
                stage=stage,
                home_label=home_label, away_label=away_label,
                home_team=home_team, away_team=away_team,
                home_score=None, away_score=None, status="scheduled",
            ))
        stages.append(BracketStage(stage=stage, matches=matches))
    return stages
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_parse_bracket.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper/parsers/bracket.py tests/test_parse_bracket.py
git commit -m "feat(scraper): bracket parser (tree + seed labels)"
```

---

### Task 10: JSON writer (latest + snapshot + manifest)

**Files:**
- Create: `scraper/writer.py`
- Test: `tests/test_writer.py`

**Interfaces:**
- Produces: `write_all(entities: dict[str, dict], out_root: str, source: str) -> dict`.
  `entities` maps entity name → `{"ok": bool, "data": list, "count": int, "source_url": str, "error": str | None}`.
  Writes `<out_root>/latest/<name>.json` and `<out_root>/snapshots/<ts>/<name>.json` for each `ok` entity, plus `manifest.json` in both. Dataclasses serialize via `dataclasses.asdict`. Returns the manifest dict.

- [ ] **Step 1: Write the failing test**

`tests/test_writer.py`:
```python
import json, os
from scraper.models import Team
from scraper.writer import write_all

def test_write_all_creates_latest_snapshot_and_manifest(tmp_path):
    teams = [Team(id="1", slug="x", profile_url="/teams/1-x", flag_url=None,
                  country="X", team_name="Real X", faculty="FST", group="A", captain=None)]
    entities = {
        "teams": {"ok": True, "data": teams, "count": 1, "source_url": "u", "error": None},
        "scorers": {"ok": False, "data": [], "count": 0, "source_url": "u2", "error": "boom"},
    }
    manifest = write_all(entities, str(tmp_path), source="https://ofsportsaiub.org")

    latest = tmp_path / "latest" / "teams.json"
    assert latest.exists()
    loaded = json.loads(latest.read_text())
    assert loaded[0]["team_name"] == "Real X"           # real name persisted
    assert loaded[0]["country"] == "X"

    # failed entity is NOT written to latest but is recorded in the manifest
    assert not (tmp_path / "latest" / "scorers.json").exists()
    assert manifest["entities"]["scorers"]["ok"] is False
    assert manifest["entities"]["scorers"]["error"] == "boom"
    assert manifest["entities"]["teams"]["count"] == 1

    # snapshot dir exists and also holds teams.json + manifest.json
    snap = tmp_path / "snapshots"
    assert snap.is_dir()
    ts_dir = next(snap.iterdir())
    assert (ts_dir / "teams.json").exists()
    assert (ts_dir / "manifest.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_writer.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `scraper/writer.py`**

```python
"""Serialize scraped entities to data/latest/ + a timestamped snapshot + manifest."""
import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone

def _default(obj):
    if is_dataclass(obj):
        return asdict(obj)
    raise TypeError(f"not serializable: {type(obj)!r}")

def _dump(obj, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, default=_default, ensure_ascii=False, indent=2)

def write_all(entities: dict, out_root: str, source: str) -> dict:
    latest = os.path.join(out_root, "latest")
    os.makedirs(latest, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    snap = os.path.join(out_root, "snapshots", ts)
    os.makedirs(snap, exist_ok=True)

    manifest = {"scraped_at": ts, "source": source, "entities": {}, "snapshot_dir": snap}
    for name, result in entities.items():
        if result.get("ok"):
            _dump(result["data"], os.path.join(latest, f"{name}.json"))
            _dump(result["data"], os.path.join(snap, f"{name}.json"))
        manifest["entities"][name] = {
            "count": result.get("count"),
            "source_url": result.get("source_url"),
            "ok": bool(result.get("ok")),
            "error": result.get("error"),
        }
    _dump(manifest, os.path.join(latest, "manifest.json"))
    _dump(manifest, os.path.join(snap, "manifest.json"))
    return manifest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_writer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper/writer.py tests/test_writer.py
git commit -m "feat(scraper): JSON writer with snapshots and run manifest"
```

---

### Task 11: Orchestrator + CLI + live smoke run

**Files:**
- Create: `scraper/run.py`
- Test: `tests/test_run.py`
- Modify: `README.md` (add a "Scraper" usage section)

**Interfaces:**
- Consumes: `Client`, all `parse_*` functions, `write_all`, `config`.
- Produces: `scrape(client, out_root, only=None, no_rosters=False) -> dict` (returns the manifest) and a `main(argv=None)` CLI entry (`python -m scraper.run`).

- [ ] **Step 1: Write the failing test** (fake client — no network)

`tests/test_run.py`:
```python
import json
from scraper.run import scrape

TEAMS_FRAG = """
<div class="teams-directory-grid">
  <a class="team-directory-card" href="/teams/42-netherlands">
    <span class="team-directory-names"><strong>Netherlands</strong><small>FST</small></span>
    <span class="team-directory-group">Group A</span></a>
</div>"""
PROFILE = """
<h1>Netherlands</h1><span class="profile-team-name">Team · CS BACKBENCHER</span>
<a class="profile-player" href="/players/658-rezu">
  <span class="profile-player-photo"><img src="/i.png"><b>02</b></span>
  <div><strong>Rezu</strong><small>Player</small></div>
  <div class="player-totals"><span><b>0</b> goals</span><span><b>0</b> assists</span><span><b>0</b> cards</span></div>
</a>"""
FIXTURES = '<article class="fixture-row"><a class="fixture-card-link" href="/matches/1-a-vs-b"></a>' \
           '<div class="fixture-card-head"><span>Group A</span><span>Jul 28, 8:00 AM</span></div>' \
           '<div class="fixture-card-main"><div class="fixture-side home"><span class="fixture-team">A</span></div>' \
           '<strong class="fixture-score">VS</strong>' \
           '<div class="fixture-side away"><span class="fixture-team">B</span></div></div>' \
           '<div class="fixture-card-foot"><span class="fixture-no">Match 1</span></div></article>'
GROUPS = '<div class="panel"><h3>Group A</h3><table class="data-table"><tbody>' \
         '<tr class="qualify"><td><a href="/teams/42-netherlands">Netherlands</a></td>' \
         '<td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr></tbody></table></div>'
SCORERS = '<div class="scorers-empty"></div>'
BRACKET = '<section class="knockout-stage stage-r32"><article class="knockout-match" data-match-no="49">' \
          '<div class="ko-team "><span>1st of Group A</span></div>' \
          '<div class="ko-team "><span>2nd of Group I</span></div></article></section>'

class FakeClient:
    def fetch_tab(self, name):
        return {"teams": TEAMS_FRAG, "fixtures": FIXTURES, "groups": GROUPS,
                "scorers": SCORERS, "bracket": BRACKET}[name]
    def fetch_page(self, path):
        return PROFILE

def test_scrape_writes_all_entities(tmp_path):
    manifest = scrape(FakeClient(), str(tmp_path))
    latest = tmp_path / "latest"
    for name in ("teams", "rosters", "fixtures", "standings", "scorers", "bracket"):
        assert (latest / f"{name}.json").exists(), name
        assert manifest["entities"][name]["ok"] is True

    teams = json.loads((latest / "teams.json").read_text())
    assert teams[0]["team_name"] == "CS BACKBENCHER"       # enriched from profile
    rosters = json.loads((latest / "rosters.json").read_text())
    assert rosters[0]["players"][0]["name"] == "Rezu"
    assert json.loads((latest / "scorers.json").read_text()) == []

def test_scrape_only_subset(tmp_path):
    manifest = scrape(FakeClient(), str(tmp_path), only=["fixtures"], no_rosters=True)
    assert (tmp_path / "latest" / "fixtures.json").exists()
    assert "teams" not in manifest["entities"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_run.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `scraper/run.py`**

```python
"""Orchestrate a full scrape: fetch -> parse -> write, with per-entity isolation."""
import argparse
import logging

from scraper import config
from scraper.client import Client
from scraper.parsers.teams import parse_teams
from scraper.parsers.profile import parse_profile
from scraper.parsers.fixtures import parse_fixtures
from scraper.parsers.standings import parse_standings
from scraper.parsers.scorers import parse_scorers
from scraper.parsers.bracket import parse_bracket
from scraper.writer import write_all

log = logging.getLogger(__name__)

# entity name -> (tab value, parser). "teams"/"rosters" are handled specially.
_TAB_ENTITIES = {
    "fixtures": ("fixtures", parse_fixtures),
    "standings": ("groups", parse_standings),
    "scorers": ("scorers", parse_scorers),
    "bracket": ("bracket", parse_bracket),
}

def _ok(data, url):
    return {"ok": True, "data": data, "count": len(data), "source_url": url, "error": None}

def _fail(url, exc):
    return {"ok": False, "data": [], "count": 0, "source_url": url, "error": str(exc)}

def scrape(client, out_root, only=None, no_rosters=False) -> dict:
    wanted = set(only) if only else set(config.ENTITY_FILES)
    entities: dict[str, dict] = {}

    # teams (+ rosters) come from the teams directory + per-team profiles
    if wanted & {"teams", "rosters"}:
        turl = f"{config.BASE_URL}/tab-api.php?tab=teams"
        try:
            team_stubs = parse_teams(client.fetch_tab("teams"))
            teams, rosters = [], []
            if no_rosters:
                teams = team_stubs
            else:
                for stub in team_stubs:
                    try:
                        enriched, roster = parse_profile(client.fetch_page(stub.profile_url), stub)
                        teams.append(enriched)
                        rosters.append(roster)
                    except Exception as exc:                       # per-team isolation
                        log.warning("profile %s failed: %s", stub.profile_url, exc)
                        teams.append(stub)
            if "teams" in wanted:
                entities["teams"] = _ok(teams, turl)
            if "rosters" in wanted and not no_rosters:
                entities["rosters"] = _ok(rosters, turl)
        except Exception as exc:
            if "teams" in wanted:
                entities["teams"] = _fail(turl, exc)
            if "rosters" in wanted:
                entities["rosters"] = _fail(turl, exc)

    for name, (tab, parser) in _TAB_ENTITIES.items():
        if name not in wanted:
            continue
        url = f"{config.BASE_URL}/tab-api.php?tab={tab}"
        try:
            entities[name] = _ok(parser(client.fetch_tab(tab)), url)
        except Exception as exc:                                    # per-entity isolation
            log.warning("entity %s failed: %s", name, exc)
            entities[name] = _fail(url, exc)

    return write_all(entities, out_root, source=config.BASE_URL)

def main(argv=None):
    ap = argparse.ArgumentParser(description="Scrape the AIUB World Cup 2026 site.")
    ap.add_argument("--only", nargs="+", metavar="ENTITY",
                    help="subset of: " + ", ".join(config.ENTITY_FILES))
    ap.add_argument("--no-rosters", action="store_true", help="skip per-team profile fetches")
    ap.add_argument("--delay", type=float, default=config.DEFAULT_DELAY)
    ap.add_argument("--out", default="./data", help="output root (default ./data)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    client = Client(delay=args.delay)
    manifest = scrape(client, args.out, only=args.only, no_rosters=args.no_rosters)
    for name, info in manifest["entities"].items():
        flag = "ok" if info["ok"] else f"FAIL ({info['error']})"
        print(f"  {name:10s} {info['count'] if info['count'] is not None else '-':>4} {flag}")
    print(f"snapshot: {manifest['snapshot_dir']}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_run.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the FULL test suite**

Run: `./venv/bin/pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Live smoke run against the real site**

Run: `./venv/bin/python -m scraper.run`
Expected: prints a per-entity table with `teams 48`, `rosters 48`, `fixtures 80`, `standings 16`, `scorers 0`, `bracket` (5 stages) — all `ok` — and a snapshot path. Then verify:
```bash
./venv/bin/python -c "import json; d=json.load(open('data/latest/teams.json')); print(len(d), d[0]['country'], '/', d[0]['team_name'])"
```
Expected: `48 <Country> / <Real Team Name>` (a non-null real name), confirming the end-to-end pipeline and the country+team_name requirement.

- [ ] **Step 7: Add a README usage section and commit**

Append to `README.md`:
```markdown
## Scraper

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python -m scraper.run              # scrape everything -> data/latest/*.json
./venv/bin/python -m scraper.run --no-rosters # fast refresh (skip 48 profile fetches)
./venv/bin/pytest -q                          # run tests
```
```

Then:
```bash
git add scraper/run.py tests/test_run.py README.md
git commit -m "feat(scraper): orchestrator, CLI, and live end-to-end run"
```

---

## Self-Review

**1. Spec coverage (§2–§7):**
- Server-rendered fetch via `tab-api.php` + profile pages → Task 3 (client). ✓
- Entities teams, rosters, fixtures, standings, scorers, bracket → Tasks 4–9. ✓
- Real `team_name` (strip "Team · ") → Task 5 + verified in Task 11 Step 6. ✓
- Data model §3 (all dataclasses incl. `KnockoutMatch` tree fields) → Task 2. ✓
- JSON output: latest + snapshots + manifest → Task 10. ✓
- CLI flags `--only/--no-rosters/--delay/--out` → Task 11. ✓
- Per-entity + per-team isolation (§5) → Task 11 `scrape()`. ✓
- Empty-vs-populated handling (§2) → played-fixture test (Task 6), empty scorers (Task 8), zeros in standings (Task 7). ✓
- Offline tests, no network (§7) → all parser/writer/run tests use inline HTML or a fake client. ✓
- Politeness (§6): UA, delay, retries → Tasks 1 + 3. ✓
- Projection (§8) and dashboard (§9) are intentionally **out of this phase** (separate plans).

**2. Placeholder scan:** No TBD/TODO; every step has real code or an exact command. The scorers populated-selectors caveat is called out explicitly (honest limitation, not a placeholder), with the empty-state as the authoritative test.

**3. Type consistency:** `Client.fetch_tab/fetch_page`, `parse_teams/parse_profile/parse_fixtures/parse_standings/parse_scorers/parse_bracket`, `write_all(entities, out_root, source)`, and `scrape(client, out_root, only, no_rosters)` signatures are used identically wherever referenced. `parse_profile` returns `(Team, Roster)` consistently in Tasks 5 and 11. Entity names match `config.ENTITY_FILES` across writer/run/tests.
