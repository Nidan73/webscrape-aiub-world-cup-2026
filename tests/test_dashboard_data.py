import json
from dashboard.data_access import DataStore


def _seed(dirpath, manifest_stamp="A"):
    (dirpath / "teams.json").write_text(json.dumps(
        [{"id": "42", "country": "Netherlands", "team_name": "CS Backbencher", "group": "A"}]))
    (dirpath / "manifest.json").write_text(json.dumps({"scraped_at": manifest_stamp}))


def test_reads_and_caches(tmp_path):
    _seed(tmp_path)
    store = DataStore(str(tmp_path))
    assert store.teams()[0]["team_name"] == "CS Backbencher"
    assert store.team("42")["country"] == "Netherlands"
    assert store.team("nope") is None


def test_missing_file_returns_default(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    store = DataStore(str(tmp_path))
    assert store.fixtures() == [] and store.projections() == {}


def test_cache_invalidates_on_manifest_change(tmp_path):
    _seed(tmp_path)
    store = DataStore(str(tmp_path))
    assert store.teams()[0]["team_name"] == "CS Backbencher"
    # rewrite teams + bump manifest -> cache must refresh
    (tmp_path / "teams.json").write_text(json.dumps([{"id": "1", "country": "X", "team_name": "Y", "group": "A"}]))
    import os, time
    (tmp_path / "manifest.json").write_text(json.dumps({"scraped_at": "B"}))
    os.utime(tmp_path / "manifest.json", (time.time() + 5, time.time() + 5))
    assert store.teams()[0]["team_name"] == "Y"
