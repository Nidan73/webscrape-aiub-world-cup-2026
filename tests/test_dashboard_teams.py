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
