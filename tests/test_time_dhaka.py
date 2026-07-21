from dashboard.timefmt import format_dhaka
from scraper.writer import write_all
from scraper.models import Team
from simulation.store import SimStore


def test_format_dhaka_converts_legacy_utc_z():
    # 12:00 UTC → 18:00 Asia/Dhaka
    out = format_dhaka("2026-07-21T12-00-00Z")
    assert "18:00" in out
    assert "Asia/Dhaka" in out


def test_format_dhaka_keeps_offset_local():
    out = format_dhaka("2026-07-22T01:30:00+06:00")
    assert "01:30" in out
    assert "Asia/Dhaka" in out


def test_writer_scraped_at_is_dhaka_offset(tmp_path):
    teams = [Team(id="1", slug="x", profile_url="/teams/1-x", flag_url=None,
                  country="X", team_name="Real X", faculty="FST", group="A", captain=None)]
    entities = {"teams": {"ok": True, "data": teams, "count": 1, "source_url": "u", "error": None}}
    manifest = write_all(entities, str(tmp_path), source="https://ofsportsaiub.org")
    assert "+06" in manifest["scraped_at"]
    assert not manifest["scraped_at"].endswith("Z")


def test_sim_history_created_at_dhaka(tmp_path):
    s = SimStore(str(tmp_path / "sim"))
    entry = s.save_history(type="named", title="t", payload={
        "ratings": {}, "whatif": {"groups": {}, "ko": {}},
        "mc": {"n": 1000, "bias": 0.0, "use_current_picks": True}})
    assert "+06:00" in entry["created_at"] or entry["created_at"].endswith("+06:00")
