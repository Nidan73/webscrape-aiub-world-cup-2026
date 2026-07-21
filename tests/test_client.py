import pytest
import requests

from scraper.client import Client


class FakeResp:
    def __init__(self, *, text="", payload=None, status=200):
        self._text = text
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
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
    with pytest.raises(requests.HTTPError):
        c.fetch_tab("teams")
    assert n["i"] == 3
