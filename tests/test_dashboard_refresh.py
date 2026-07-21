import pytest
from dashboard.app import create_app
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
