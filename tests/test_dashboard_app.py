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
