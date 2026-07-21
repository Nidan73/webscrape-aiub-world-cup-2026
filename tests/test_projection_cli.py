from projection.load import build_context
from projection.cli import find_team_id, render_team
from tests.test_projection_load import TEAMS, BRACKET, UNRESOLVED


def test_find_team_id_by_country_and_name():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    assert find_team_id(ctx, "Alpha") == "a1"
    assert find_team_id(ctx, "be") == "b2"          # by real team_name, case-insensitive
    assert find_team_id(ctx, "nope") is None


def test_render_team_mentions_rounds_and_opponents():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    text = render_team(ctx, "a1")
    assert "Alpha" in text and "GROUP WINNER" in text and "RUNNER-UP" in text
    assert "R32" in text and "Final" in text
    assert "Bravo" in text            # a possible opponent country appears
