import json

import pytest

from dashboard.app import create_app


def _client(tmp_path):
    data = tmp_path / "latest"
    sim = tmp_path / "simulations"
    data.mkdir()
    sim.mkdir()
    # Prefer projection mini-bracket so what-if/MC tests have a closed Final.
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


def test_whatif_preview_missing_team_id_errors(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sim/whatif/preview", json={"picks": {}})
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_whatif_preview_bad_picks_errors(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sim/whatif/preview", json={
        "team_id": "a1",
        "picks": {"groups": {"A": {"first": "a1", "second": "a1"}}, "ko": {}}})
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_mc_rejects_large_n(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sim/montecarlo/run", json={"team_id": "a1", "n": 10001, "bias": 0})
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_mc_run_happy_path(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sim/montecarlo/run", json={"team_id": "a1", "n": 50, "bias": 0.5, "seed": 1})
    body = r.get_json()
    assert r.status_code == 200 and body["ok"] is True
    assert "reach" in body and "opponents" in body


def test_mc_run_unknown_team_errors(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sim/montecarlo/run", json={"team_id": "zzz", "n": 10, "bias": 0})
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


def test_history_list_rename_delete(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sim/history", json={"type": "named", "title": "First"})
    hid = r.get_json()["entry"]["id"]
    assert any(h["id"] == hid for h in c.get("/api/sim/history").get_json()["history"])

    r2 = c.patch(f"/api/sim/history/{hid}", json={"title": "Renamed"})
    assert r2.get_json()["ok"] is True and r2.get_json()["entry"]["title"] == "Renamed"

    r3 = c.delete(f"/api/sim/history/{hid}")
    assert r3.get_json()["ok"] is True
    assert not any(h["id"] == hid for h in c.get("/api/sim/history").get_json()["history"])


def test_history_restore_missing_id_404(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sim/history/does-not-exist/restore")
    assert r.status_code == 404 and r.get_json()["ok"] is False


def test_history_restore_path_traversal_400(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sim/history/%2e%2e/restore")
    assert r.status_code in (400, 404) and r.get_json()["ok"] is False


def test_put_current_autosave_default_creates_history(tmp_path):
    c = _client(tmp_path)
    c.put("/api/sim/current", json={"whatif": {"groups": {}, "ko": {}},
                                    "mc": {"n": 100, "bias": 0.1, "use_current_picks": True}})
    history = c.get("/api/sim/history").get_json()["history"]
    assert any(h["type"] == "auto" for h in history)


def test_put_current_autosave_false_skips_history(tmp_path):
    c = _client(tmp_path)
    c.put("/api/sim/current", json={"whatif": {"groups": {}, "ko": {}},
                                    "mc": {"n": 100, "bias": 0.1, "use_current_picks": True},
                                    "autosave": False})
    history = c.get("/api/sim/history").get_json()["history"]
    assert not any(h["type"] == "auto" for h in history)


@pytest.mark.parametrize("method,path", [
    ("post", "/api/sim/whatif/preview"),
    ("post", "/api/sim/montecarlo/run"),
    ("post", "/api/sim/history"),
    ("put", "/api/sim/current"),
    ("put", "/api/sim/ratings"),
])
def test_json_array_body_rejected(tmp_path, method, path):
    c = _client(tmp_path)
    r = getattr(c, method)(path, json=[1, 2, 3])
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_put_current_bad_mc_type_rejected(tmp_path):
    c = _client(tmp_path)
    r = c.put("/api/sim/current", json={"whatif": {"groups": {}, "ko": {}}, "mc": "bad"})
    assert r.status_code == 400 and r.get_json()["ok"] is False


@pytest.mark.parametrize("n", [1.9, 10000.9])
def test_mc_rejects_fractional_n(tmp_path, n):
    c = _client(tmp_path)
    r = c.post("/api/sim/montecarlo/run", json={"team_id": "a1", "n": n, "bias": 0})
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_mc_rejects_bias_out_of_range(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sim/montecarlo/run", json={"team_id": "a1", "n": 50, "bias": 2})
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_put_current_bad_group_shape_rejected(tmp_path):
    c = _client(tmp_path)
    r = c.put("/api/sim/current", json={
        "whatif": {"groups": {"A": "bad"}, "ko": {}},
        "mc": {"n": 100, "bias": 0, "use_current_picks": True},
    })
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_mc_rejects_nan_bias(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sim/montecarlo/run", json={"team_id": "a1", "n": 50, "bias": float("nan")})
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_whatif_preview_bad_group_shape_rejected(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sim/whatif/preview", json={
        "team_id": "a1",
        "picks": {"groups": {"A": "bad"}, "ko": {}},
    })
    assert r.status_code == 400 and r.get_json()["ok"] is False
