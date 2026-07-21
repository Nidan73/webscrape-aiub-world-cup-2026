import pytest

from simulation.store import SimStore


def test_defaults_when_missing(tmp_path):
    s = SimStore(str(tmp_path / "sim"))
    assert s.get_ratings() == {}
    cur = s.get_current()
    assert cur["mc"]["n"] == 1000 and cur["whatif"]["groups"] == {}


def test_ratings_roundtrip(tmp_path):
    s = SimStore(str(tmp_path / "sim"))
    s.put_ratings({"a1": 2.5})
    assert s.get_ratings()["a1"] == 2.5


def test_named_and_auto_history(tmp_path):
    s = SimStore(str(tmp_path / "sim"))
    s.put_ratings({"a1": 1})
    s.put_current({"whatif": {"groups": {"A": {"first": "a1", "second": "a2"}}, "ko": {}},
                   "mc": {"n": 500, "bias": 0.2, "use_current_picks": True}})
    named = s.save_history(type="named", title="Upset path", payload={
        "ratings": s.get_ratings(), "whatif": s.get_current()["whatif"],
        "mc": s.get_current()["mc"]}, team_id="a1")
    auto = s.save_history(type="auto", title="auto", payload={
        "ratings": {}, "whatif": {"groups": {}, "ko": {}},
        "mc": {"n": 1000, "bias": 0.0, "use_current_picks": True}})
    ids = {h["id"] for h in s.list_history()}
    assert named["id"] in ids and auto["id"] in ids
    s.rename(named["id"], "Renamed")
    assert s.get_history(named["id"])["title"] == "Renamed"
    s.restore(named["id"])
    assert s.get_current()["whatif"]["groups"]["A"]["first"] == "a1"
    assert s.delete(auto["id"]) is True
    assert s.get_history(auto["id"]) is None


def test_auto_cap_50(tmp_path):
    s = SimStore(str(tmp_path / "sim"))
    for i in range(55):
        s.save_history(type="auto", title=f"a{i}", payload={
            "ratings": {}, "whatif": {"groups": {}, "ko": {}},
            "mc": {"n": 1000, "bias": 0.0, "use_current_picks": True}})
    autos = [h for h in s.list_history() if h["type"] == "auto"]
    assert len(autos) == 50


def test_reject_path_traversal_id(tmp_path):
    root = tmp_path / "sim"
    s = SimStore(str(root))
    s.put_ratings({"a1": 2.5})
    s.put_current({"whatif": {"groups": {"A": {"first": "a1"}}, "ko": {}},
                   "mc": {"n": 500, "bias": 0.0, "use_current_picks": True}})

    assert s.get_history("../current") is None
    assert s.delete("../current") is False
    assert s.delete("../ratings") is False

    assert (root / "ratings.json").exists()
    assert (root / "current.json").exists()
    assert s.get_ratings() == {"a1": 2.5}
    assert s.get_current()["whatif"]["groups"]["A"]["first"] == "a1"

    with pytest.raises(ValueError):
        s.restore("../current")
    with pytest.raises(ValueError):
        s.rename("../current", "hijacked")

    assert s.get_history("") is None
    assert s.delete("") is False


def test_store_lock_file_created_on_write(tmp_path):
    root = tmp_path / "sim"
    s = SimStore(str(root))
    s.put_ratings({"x": 1.0})
    assert (root / "store.lock").exists()
