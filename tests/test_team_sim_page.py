import json

from dashboard.app import create_app


def _client(tmp_path):
    data = tmp_path / "latest"
    sim = tmp_path / "simulations"
    data.mkdir()
    sim.mkdir()
    # Same fixture as test_sim_api.py's helper: ensures team a1 exists.
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


def test_team_page_has_sim_root(tmp_path):
    c = _client(tmp_path)
    html = c.get("/teams/a1").data.decode()
    assert 'id="sim-root"' in html
    assert "Possible opponents" in html


def test_team_page_has_mode_tabs_and_history_closed(tmp_path):
    c = _client(tmp_path)
    html = c.get("/teams/a1").data.decode()
    assert 'data-mode="possible"' in html
    assert 'data-mode="whatif"' in html
    assert 'data-mode="montecarlo"' in html
    assert 'id="history-drawer" class="history-drawer" hidden' in html


def test_team_page_only_possible_panel_visible_initially(tmp_path):
    c = _client(tmp_path)
    html = c.get("/teams/a1").data.decode()
    assert '<section id="panel-possible" class="sim-panel is-active"' in html
    assert '<section id="panel-whatif" class="sim-panel" hidden' in html
    assert '<section id="panel-montecarlo" class="sim-panel" hidden' in html


def test_team_page_strength_banner_exact_copy_when_no_signal(tmp_path):
    c = _client(tmp_path)
    html = c.get("/teams/a1").data.decode()
    assert "Using equal strength — no group results yet" in html


def test_team_page_roster_demoted_below_sim(tmp_path):
    c = _client(tmp_path)
    html = c.get("/teams/a1").data.decode()
    sim_pos = html.index('id="sim-root"')
    roster_pos = html.index('class="roster-block"')
    assert roster_pos > sim_pos


def test_team_page_passes_group_teams_and_ko_slots(tmp_path):
    c = _client(tmp_path)
    html = c.get("/teams/a1").data.decode()
    assert "Alpha" in html and "Bravo" in html   # group_teams embedded as JSON
    assert '"match_no": 3' in html or '"match_no":3' in html  # Final ko slot with 2 candidates


def test_team_page_sim_js_included(tmp_path):
    c = _client(tmp_path)
    html = c.get("/teams/a1").data.decode()
    assert "js/sim.js" in html
