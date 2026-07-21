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
