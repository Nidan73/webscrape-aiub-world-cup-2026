# Task 5 Report: Flask sim APIs

## Status
Complete.

## Deliverables
- `dashboard/sim_api.py` — `make_sim_blueprint(store, sim_store, data_dir=None)`, `ok`/`err` JSON helpers, routes for `/api/sim/{ratings,current,whatif/preview,montecarlo/run,history,history/<id>,history/<id>/restore}` exactly per spec §8.
- `dashboard/app.py` — `create_app(data_dir="./data/latest", sim_dir=None, job=None)`; builds `SimStore(sim_dir)` (default: sibling `simulations` of `data_dir`'s parent when `data_dir` ends with `latest`, else `data_dir/simulations`) and registers the blueprint.
- `tests/test_sim_api.py` — brief's 4 required tests plus 9 extra: missing/invalid picks, MC happy path + unknown team, history list/rename/delete, restore-missing-id (404), restore-invalid-id (404 via `KeyError`), autosave on/off.

## Implementation notes
- Context for `whatif.preview` / `run_montecarlo` is built fresh per request via `projection.load.build_context(store.teams(), store.standings(), store.bracket())` — reuses `DataStore`'s own mtime-based cache, no second file read, no stale bracket state carried across requests. `data_dir` param is accepted per the brief's interface but unused (the on-demand `build_context` path was chosen over `load_context(data_dir)` since `store` is already the source of truth for the dashboard).
- `PUT /api/sim/ratings` body is the ratings map itself (not wrapped), matching the brief's test (`c.put("/api/sim/ratings", json={"a1": 3})`); non-numeric values are caught (`float()` raising in `SimStore.put_ratings`) and turned into a 400.
- `PUT /api/sim/current` autosaves (`type="auto"`) unless body has `autosave: false`; optional `team_id` in the body is passed through to the snapshot for team-page-scoped saves.
- `POST /api/sim/montecarlo/run` defaults `picks` to the store's current what-if (`sim_store.get_current()["whatif"]`) when the body omits `"picks"`, so the API works with just `{team_id, n, bias}` and still respects `use_current_picks`. `n`/`bias` bounds and unknown-team errors both surface as 400 (n>10000 raises inside `run_montecarlo`; caught and wrapped).
- `restore`/`rename` distinguish `ValueError` (malformed id, e.g. fails `SimStore`'s `_HISTORY_ID_RE`/path-containment check) from `KeyError` (well-formed id, file missing) — both surface as 4xx (400 / 404 respectively) rather than a 500.
- Verified `dashboard/jobs.py` (`RefreshJob`) is untouched — it only ever shells out to `scraper.run` + `projection.run`, no `sim_dir` reference, so a scrape refresh cannot disturb `data/simulations/`.

## Tests
```
./venv/bin/pytest tests/test_sim_api.py -v      → 13 passed
./venv/bin/pytest -q                            → 81 passed (full suite)
```

## Self-review
- All 4 of the brief's Step-1 tests pass unmodified.
- Existing dashboard tests (`test_dashboard_app.py`, `test_dashboard_teams.py`, `test_dashboard_views.py`, `test_dashboard_refresh.py`) call `create_app(str(tmp_path))` / `create_app(str(tmp_path), job=...)` positionally/by-keyword with no `sim_dir` — default-derives `tmp_path/simulations` (their `tmp_path` name is a pytest-random dir, never literally `"latest"`), isolated per test, no interference with `DataStore`'s named-file reads.
- `ok(data)`/`err(msg, code)` match the brief's helper signatures verbatim; every route returns one or the other, so `{"ok": bool, ...}` shape is uniform.

## Concerns
- `make_sim_blueprint`'s `data_dir` parameter is currently a no-op (kept only for interface parity with the brief's call site). If a future need arises to read `data_dir` directly (e.g. bypassing `DataStore`'s cache), it's already threaded through.
- Path-traversal / malformed history ids are rejected by `SimStore` itself (regex + `is_relative_to` containment check), not re-validated in the blueprint; the blueprint only translates the resulting `ValueError`/`KeyError` into HTTP codes. Note that ids containing a literal `/` never reach the handler at all — Flask's default `<hid>` string converter excludes `/`, so those 404 at the routing layer before any store code runs (verified empirically; test uses a slash-free malformed id instead to exercise the store's own check).

## Commit
`feat(dashboard): simulator JSON APIs and SimStore wiring`
SHA: `91e0605418c08d8dffaa299a486078adb4f95112` (parent `96c08f85fe30429c7e4076b5e4097ea3bda91e44`, branch `feat/team-simulator`).
Built via `git commit-tree` + `git update-ref` (rather than `git commit`) to keep the commit free of any `Co-authored-by` trailer; `git log -1 --format=full` confirms a clean Author/Commit with no trailers.

## Review fixes (2026-07-22)

Hardened request-body validation across sim API write routes:

- `_json_object()` — all mutating endpoints reject array/null/non-object bodies with 400 `{ok:false, error:"request body must be a JSON object"}` before any `.get()`.
- `PUT /api/sim/current` — `_normalize_whatif()` / `_normalize_mc()` validate nested shapes: `whatif.groups`/`whatif.ko` must be objects; `mc` must be an object with integer `n` ∈ [1,10000], numeric `bias` ∈ [0,1], and boolean `use_current_picks`. Corrupt types never reach `SimStore.put_current`.
- `POST /api/sim/montecarlo/run` — `_parse_int_param()` rejects non-int and fractional floats (e.g. `1.9`, `10000.9`); `_parse_bias()` rejects out-of-range bias before calling `run_montecarlo` (no silent `int()` truncate, no 200 with invalid bias).

### Tests
```
./venv/bin/pytest tests/test_sim_api.py -v  → 22 passed
```

New cases: JSON array body → 400 (parametrized over 5 write routes); `PUT current` with `mc:"bad"` → 400; MC `n=1.9`/`10000.9` → 400; MC `bias=2` → 400.

### Commit
`fix(dashboard): harden sim API request validation`
SHA: _(pending)_
