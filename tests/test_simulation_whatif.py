from projection.load import build_context
from tests.test_projection_load import TEAMS, BRACKET, UNRESOLVED
from simulation.whatif import validate_picks, preview


def test_bad_group_member_errors():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    err = validate_picks(ctx, {"groups": {"A": {"first": "b1", "second": "a2"}}, "ko": {}})
    assert err and "group" in err.lower()


def test_force_group_shrinks_path():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    base = preview("a1", ctx, {"groups": {}, "ko": {}})
    forced = preview("a1", ctx, {"groups": {"A": {"first": "a1", "second": "a2"},
                                            "B": {"first": "b1", "second": "b2"}}, "ko": {}})
    # With all groups forced, R32 opponents for group winner a1 should be only b2 (2nd of B)
    rounds = forced["projection"]["scenarios"]["group_winner"]
    r32 = next(r for r in rounds if r["round"] == "R32")
    assert [o["id"] for o in r32["possible_opponents"]] == ["b2"]
