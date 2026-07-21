import json
from projection.load import build_context
from projection.run import build_projections, write_projections
from tests.test_projection_load import TEAMS, BRACKET, UNRESOLVED


def test_build_projections_covers_all_teams():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    data = build_projections(ctx)
    assert set(data) == {"a1", "a2", "b1", "b2"}
    assert data["a1"]["country"] == "Alpha"
    assert set(data["a1"]["scenarios"]) == {"group_winner", "runner_up"}


def test_write_projections_roundtrips(tmp_path):
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    out = tmp_path / "projections.json"
    write_projections(ctx, str(out))
    loaded = json.loads(out.read_text())
    rounds = loaded["a1"]["scenarios"]["group_winner"]
    assert [r["round"] for r in rounds] == ["R32", "Final"]
