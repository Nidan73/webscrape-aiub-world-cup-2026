from projection.load import build_context
from projection.path import entry_matches, project_team
from tests.test_projection_load import TEAMS, BRACKET, UNRESOLVED, RESOLVED


def _opp_ids(rounds, rnd):
    row = next(r for r in rounds if r["round"] == rnd)
    return {o["id"] for o in row["possible_opponents"]}


def test_entry_matches_two_scenarios():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    a1 = ctx.teams["a1"]
    entries = entry_matches(a1, ctx)
    scenarios = {scen: (m["match_no"], side) for m, side, scen in entries}
    assert scenarios == {"group_winner": (1, "home"), "runner_up": (2, "away")}


def test_project_team_unresolved_sets():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    proj = project_team("a1", ctx)
    gw = proj["scenarios"]["group_winner"]
    assert _opp_ids(gw, "R32") == {"b1", "b2"}            # opponent = 2nd of Group B
    assert _opp_ids(gw, "Final") == {"a2", "b1", "b2"}    # winner of M2 minus self
    ru = proj["scenarios"]["runner_up"]
    assert _opp_ids(ru, "R32") == {"b1", "b2"}            # opponent = 1st of Group B
    assert _opp_ids(ru, "Final") == {"a2", "b1", "b2"}


def test_project_team_resolved_narrows():
    ctx = build_context(TEAMS, RESOLVED, BRACKET)
    proj = project_team("a1", ctx)
    gw = proj["scenarios"]["group_winner"]
    assert _opp_ids(gw, "R32") == {"b2"}                  # 2nd of B is now exactly b2
    assert _opp_ids(gw, "Final") == {"a2", "b1"}          # winner of M2 = 1st B (b1) or 2nd A (a2)
