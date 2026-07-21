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


def test_ko_winner_narrows_final_opponent_to_single_team():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    picks = {"groups": {"A": {"first": "a1", "second": "a2"},
                         "B": {"first": "b1", "second": "b2"}},
             "ko": {"1": "a1"}}
    forced = preview("b1", ctx, picks)
    # b1 (group_winner of B) reaches the Final; M1's winner is forced to a1, so
    # the Final opponent set must be exactly {a1}, not the whole M1 side union.
    rounds = forced["projection"]["scenarios"]["group_winner"]
    final = next(r for r in rounds if r["round"] == "Final")
    assert [o["id"] for o in final["possible_opponents"]] == ["a1"]


def test_validate_picks_rejects_ko_winner_not_in_candidates_after_groups():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    picks = {"groups": {"A": {"first": "a1", "second": "a2"},
                         "B": {"first": "b1", "second": "b2"}},
             "ko": {"1": "b1"}}
    # M1 = 1st of Group A vs 2nd of Group B -> {a1, b2}; b1 is not a candidate.
    err = validate_picks(ctx, picks)
    assert err and "1" in err


def test_ko_pick_keeps_labels_intact_for_other_side_final_opponents():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    picks = {"groups": {"A": {"first": "a1", "second": "a2"},
                         "B": {"first": "b1", "second": "b2"}},
             "ko": {"1": "a1"}}
    # Forcing M1's winner must not rewrite "Winner of M1" labels to a country
    # string elsewhere, or path_for_entry's label comparison in the Final
    # match breaks and a1's own Final opponents come back empty.
    forced = preview("a1", ctx, picks)
    rounds = forced["projection"]["scenarios"]["group_winner"]
    final = next(r for r in rounds if r["round"] == "Final")
    opponent_ids = [o["id"] for o in final["possible_opponents"]]
    assert opponent_ids, "Final possible_opponents must not be empty"
    # Opponents must be M2's candidates (b1 and/or a2), never empty and never a1.
    assert set(opponent_ids) <= {"a2", "b1"}
    assert "a1" not in opponent_ids


def test_validate_picks_rejects_contradictory_ko_picks_applied_ascending():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    # M1 candidates after groups forced: {a1, b2}. M3 (Final) = Winner of M1
    # vs Winner of M2. Picks are given out of order in the dict; applying
    # ascending (M1 before M3) forces M1's winner to b2, so a1 can no longer
    # win M3 - the picks are contradictory and must be rejected.
    picks = {"groups": {"A": {"first": "a1", "second": "a2"},
                         "B": {"first": "b1", "second": "b2"}},
             "ko": {"3": "a1", "1": "b2"}}
    err = validate_picks(ctx, picks)
    assert err and "3" in err
