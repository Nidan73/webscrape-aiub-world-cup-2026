# Team-wise Opponent Simulator + Dashboard Polish — Design Spec

**Date:** 2026-07-22  
**Status:** Approved — ready for user review, then implementation planning  
**Parent:** `docs/superpowers/specs/2026-07-21-aiub-world-cup-scraper-design.md`  
**Supersedes:** Parent §10 claim that Monte Carlo is entirely out of scope — this release adds a **bounded** Monte Carlo mode (uniform ↔ strength via bias dial). Full statistical match models (Poisson, trained ELO, etc.) remain out of scope.

## 1. Goal

Ship **one release** that:

1. **Polishes** the existing Flask dashboard (currently thin / partially broken relative to the design system).
2. Adds a **team-wise opponent simulator** on the team detail page with three modes:
   - **A — Possible opponents** (deterministic path-to-final sets).
   - **B — What-if** (manual group 1st/2nd and KO winners; path updates live).
   - **C — Monte Carlo** (N trials; uniform, strength-based, or blended via bias dial).

Persistence is **server-side JSON** with **both** auto-snapshots and named scenario history.

## 2. Decisions (locked)

| Topic | Choice |
|--------|--------|
| Scope | A + B + C + UI polish in one release |
| MC outcome models | Uniform, strength-based, and user bias dial (0 = uniform, 1 = full strength) |
| Strength signal | Hybrid: standings (pts / GD / GF) when available; else equal; optional manual overrides |
| UI shape | Team-first: mode switcher on `/teams/<id>`; keep and polish other dashboard pages |
| Persistence | `data/simulations/` JSON on the server |
| History | Auto-snapshots **and** named saves |
| Architecture | Extend Flask in place + new `simulation/` package (Approach 1) |

## 3. Architecture

```
ofsportsaiub.org
      │
      ▼
  scraper/  ──writes──►  data/latest/*.json
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
        projection/     simulation/      dashboard/ (Flask)
        (Mode A sets)   (B + C + store)   reads latest + sim
                              │
                              ▼
                    data/simulations/
                    (ratings, current, history)
```

| Piece | Role |
|--------|------|
| `projection/` | Unchanged responsibility: deterministic possible-opponent sets → `projections.json`. Mode A reads this (and/or recomputes via shared helpers if needed). |
| `simulation/` (new) | What-if application, hybrid strength, Monte Carlo runner, JSON store. **No Flask imports** — pure Python, unit-testable. |
| `data/simulations/` | Ratings, active picks/settings, history index + files. **Never** overwritten by scraper refresh. |
| `dashboard/` | Design-system polish; team page as simulator hub; thin JSON APIs over `simulation/`. |

### Approach rejected (for this release)

- **SPA rewrite** — too large for one release.
- **Separate sim microservice** — unnecessary ops for a local tool.

## 4. Team page UX (simulator hub)

Route: `GET /teams/<team_id>` (existing), expanded.

### Layout

1. **Header** — country, team name, group, record when available.
2. **Mode switcher** — Possible opponents | What-if | Monte Carlo. **Only one mode panel visible at a time** (mitigates page weight).
3. **Active mode panel** — content for A, B, or C.
4. **History drawer** — collapsed by default; open on demand. Lists named saves + auto-snapshots; load / rename / delete.
5. **Roster** — separate sub-tab or below the fold so it does not compete with the simulator.

Shared empty/loading skeletons per mode so the page never looks half-broken.

### Mode A — Possible opponents

Elevate the existing path-to-final UI:

- Scenarios: `group_winner` and `runner_up`.
- Rounds: R32 → Final with possible opponent lists.
- Clear empty / pre-start messaging.
- CTA to jump to What-if with the same team selected.

### Mode B — What-if

**v1 pick surface (deliberately narrow):**

- Per group: choose **1st** and **2nd** (dropdowns of that group’s teams only).
- Per unresolved knockout slot: choose **winner** from the two candidate sides / resolved labels.
- **Not in v1:** match scores, goal margins, or editing every group match.

Behavior:

- Path for the focus team updates on each change (preview API).
- **Reset picks** clears active what-if state.
- Meaningful changes create an **auto-snapshot**; **Save as…** creates a **named** scenario.

### Mode C — Monte Carlo

Controls:

- Focus team (page context).
- **N** trials — default **1_000**, max **10_000**.
- **Bias dial** ∈ [0, 1] — 0 = uniform random among legal outcomes; 1 = full strength weighting.
- Optional **manual rating overrides** (shared with strength store).

Results:

- % chance the focus team reaches each KO round.
- Top likely opponents per round (frequency / %).
- Pre-tournament banner when standings have no signal (see §6).

Run button disables while the request is in flight; show a clear timeout/error if the call fails.

## 5. Simulation engine

### 5.1 `simulation/strength.py`

Inputs: standings rows, optional `{team_id: float}` overrides, bias ∈ [0, 1].

Rules:

1. Base strength from standings when any of pts / GD / GF indicate play has started for that group/team; otherwise treat as equal.
2. Apply manual overrides on top of (or instead of) standings-derived values for those teams.
3. When sampling a two-outcome (or multi-outcome) contest, probability mass is a blend:
   - `p_uniform` = equal among legal candidates
   - `p_strength` ∝ positive strength weights among candidates
   - `p = (1 - bias) * p_uniform + bias * p_strength` (renormalize)

When standings are all zeros, bias only differentiates teams with **manual overrides**; others stay equal. UI must explain this (§6).

### 5.2 `simulation/whatif.py`

- Start from a copy of projection `Context` (teams, standings, bracket).
- Apply user picks: forced group 1st/2nd; forced KO winners where specified.
- Re-project the focus team’s path (reuse `projection.path` / resolver ideas; do not duplicate bracket math in Flask).
- Invalid picks (team not in group, contradictory 1st/2nd) → structured error.

### 5.3 `simulation/montecarlo.py`

- For each trial: sample unresolved group finishes and KO outcomes using strength+bias; respect already-played results from live data.
- Request flag `use_current_picks` (default **true**): when true, treat active what-if picks as fixed before sampling the rest; when false, ignore what-if and sample from live unresolved state only.
- Aggregate reach percentages and opponent frequencies for the focus team.
- Accept a **seed** for deterministic tests.
- Cap N at 10_000; reject above with 400.

### 5.4 `simulation/store.py`

Atomic write (temp file + rename) and simple file lock so concurrent UI actions do not corrupt JSON.

## 6. Pre-tournament / weak-signal UX

- If standings have no meaningful differentiation, show banner:  
  **“Using equal strength — no group results yet”** (or “partial results” when some groups have played).
- Mode A remains fully useful without results (bracket structure only).
- At bias = 0, all unresolved outcomes are equal regardless of ratings.
- At bias = 1 with empty standings, only manual overrides create edges.

## 7. On-disk layout

```
data/simulations/
  ratings.json           # { "team_id": number, ... }
  current.json           # active what-if picks + MC defaults (n, bias, flags)
  index.json             # [{ id, type: "auto"|"named", title, created_at, team_id? }]
  history/
    auto-<timestamp>.json
    named-<slug>.json
```

Each history entry stores at least:

- `id`, `type`, `title`, `created_at`
- optional `team_id` (focus team when saved from a team page)
- `ratings` snapshot
- `whatif` picks
- `mc` config (`n`, `bias`, seed if any)
- optional `mc_summary` (last run aggregates, for named/auto after MC)

**Retention:** keep the latest **50** auto-snapshots (FIFO drop); named saves until user deletes.

Scraper / projection refresh **must not** delete or rewrite this tree.

## 8. HTTP APIs

All return JSON. Errors: `{ "ok": false, "error": "<message>" }` with appropriate 4xx.

| Method | Path | Purpose |
|--------|------|---------|
| GET/PUT | `/api/sim/ratings` | Read/replace manual ratings map |
| GET/PUT | `/api/sim/current` | Active what-if + MC settings |
| POST | `/api/sim/whatif/preview` | Body: `{ team_id, picks }` → path projection |
| POST | `/api/sim/montecarlo/run` | Body: `{ team_id, n, bias, use_current_picks? }` → aggregates |
| GET | `/api/sim/history` | List index |
| POST | `/api/sim/history` | Create named save (and/or force auto) |
| POST | `/api/sim/history/<id>/restore` | Load into `current` (+ ratings if stored) |
| PATCH | `/api/sim/history/<id>` | Rename |
| DELETE | `/api/sim/history/<id>` | Delete file + index row |

Missing or corrupt sim files → empty defaults; pages still render (same resilience pattern as `DataStore`).

### Monte Carlo latency (v1)

- Prefer a single synchronous response for default N (1_000).
- Disable Run while in flight; surface timeout/errors in the UI.
- No background job queue in this release. Keep the API body/response shape such that a later async job can be added without redesigning the team page.

## 9. Dashboard polish (non-simulator)

Align templates/CSS/JS with `design-system/aiub-world-cup-dashboard/MASTER.md`:

- Fira Sans / Fira Code, red primary Soft UI tokens, light + dark.
- Fix broken nav / refresh / empty states observed on current pages.
- Dense but readable layouts; consistent headers and muted empty copy.
- Do **not** rewrite as an SPA.

Pages in scope for polish: overview, teams, team detail, fixtures, standings, bracket, scorers, base layout.

## 10. Error handling summary

| Case | Behavior |
|------|----------|
| Missing/corrupt sim JSON | Defaults; no crash |
| Invalid team_id / picks | 400 + message |
| N > 10_000 | 400 |
| Concurrent store writes | Lock + atomic rename |
| Scraper refresh failure | Sim history untouched |
| MC request failure | UI message; Run re-enabled |

## 11. Testing

- **strength:** equal when empty standings; overrides win at bias=1; blend at intermediate bias.
- **whatif:** forcing a group 1st/2nd changes focus team path vs baseline; bad picks error.
- **montecarlo:** fixed seed → stable frequencies; bias=0 ≈ flat; bias=1 favors higher strength.
- **store:** round-trip ratings/current; auto-cap at 50; named save / restore / rename / delete.
- **dashboard APIs:** happy path + bad payload; team page renders with zero sim files.
- Existing scraper / projection / dashboard tests remain green.

## 12. Out of scope (this release)

- Poisson / trained ELO / market odds models
- Editing individual group match scores in what-if
- Multi-user auth or cloud sync
- SPA or separate simulation service
- Background MC job queue (API should remain forward-compatible)
- Changing scraper HTML parsers except as needed for dashboard bugs

## 13. Risk mitigations (baked into design)

| Risk | Mitigation |
|------|------------|
| Team page too heavy | One mode panel at a time; history drawer closed by default; roster demoted |
| Pre-tournament equal strength | Explicit banner; Mode A still useful; overrides + bias documented |
| MC blocks request thread | Default N=1_000; max 10_000; disabled Run + errors; no queue yet |
| What-if control sprawl | Only group 1st/2nd + KO winners in v1 |

## 14. Success criteria

- User can open any team, switch A/B/C, and understand possible opponents without leaving the page.
- What-if picks persist in server JSON and appear in history (auto + named).
- Monte Carlo returns reach % and opponent frequencies with bias control.
- Dashboard matches design-system look; refresh and empty states work.
- Tests cover engine + store + API smoke; prior suites pass.
