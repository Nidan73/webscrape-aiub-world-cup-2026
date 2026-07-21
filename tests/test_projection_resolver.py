from projection.load import build_context
from projection.resolver import resolve, reach_set
from tests.test_projection_load import TEAMS, BRACKET, UNRESOLVED, RESOLVED


def test_group_seed_unresolved_is_whole_group():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    assert resolve("1st of Group A", ctx) == {"a1", "a2"}
    assert resolve("2nd of Group B", ctx) == {"b1", "b2"}


def test_group_seed_resolved_is_single_team():
    ctx = build_context(TEAMS, RESOLVED, BRACKET)
    assert resolve("1st of Group A", ctx) == {"a1"}
    assert resolve("2nd of Group B", ctx) == {"b2"}


def test_winner_label_recurses_through_tree():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    # Winner of M1 = teams that can reach M1 = (1st A) U (2nd B)
    assert reach_set(1, ctx) == {"a1", "a2", "b1", "b2"}
    assert resolve("Winner of M1", ctx) == {"a1", "a2", "b1", "b2"}


def test_concrete_name_and_empty():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    assert resolve("Alpha", ctx) == {"a1"}       # by country
    assert resolve("BE", ctx) == {"b2"}           # by team_name
    assert resolve("", ctx) == set() and resolve(None, ctx) == set()
