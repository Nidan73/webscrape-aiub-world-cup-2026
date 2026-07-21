import json

from scraper.models import Team
from scraper.writer import write_all


def test_write_all_creates_latest_snapshot_and_manifest(tmp_path):
    teams = [Team(id="1", slug="x", profile_url="/teams/1-x", flag_url=None,
                  country="X", team_name="Real X", faculty="FST", group="A", captain=None)]
    entities = {
        "teams": {"ok": True, "data": teams, "count": 1, "source_url": "u", "error": None},
        "scorers": {"ok": False, "data": [], "count": 0, "source_url": "u2", "error": "boom"},
    }
    manifest = write_all(entities, str(tmp_path), source="https://ofsportsaiub.org")

    latest = tmp_path / "latest" / "teams.json"
    assert latest.exists()
    loaded = json.loads(latest.read_text())
    assert loaded[0]["team_name"] == "Real X"           # real name persisted
    assert loaded[0]["country"] == "X"

    # failed entity is NOT written to latest but is recorded in the manifest
    assert not (tmp_path / "latest" / "scorers.json").exists()
    assert manifest["entities"]["scorers"]["ok"] is False
    assert manifest["entities"]["scorers"]["error"] == "boom"
    assert manifest["entities"]["teams"]["count"] == 1

    # snapshot dir exists and also holds teams.json + manifest.json
    snap = tmp_path / "snapshots"
    assert snap.is_dir()
    ts_dir = next(snap.iterdir())
    assert (ts_dir / "teams.json").exists()
    assert (ts_dir / "manifest.json").exists()
