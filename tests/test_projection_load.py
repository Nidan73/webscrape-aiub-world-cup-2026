import json
from projection.load import build_context, load_context

TEAMS = [
    {"id": "a1", "country": "Alpha", "team_name": "AA", "group": "A"},
    {"id": "a2", "country": "Ares",  "team_name": "AR", "group": "A"},
    {"id": "b1", "country": "Bravo", "team_name": "BB", "group": "B"},
    {"id": "b2", "country": "Bern",  "team_name": "BE", "group": "B"},
]
BRACKET = [
    {"stage": "R32", "matches": [
        {"match_no": 1, "next_match_no": 3, "stage": "R32",
         "home_label": "1st of Group A", "away_label": "2nd of Group B",
         "home_team": None, "away_team": None},
        {"match_no": 2, "next_match_no": 3, "stage": "R32",
         "home_label": "1st of Group B", "away_label": "2nd of Group A",
         "home_team": None, "away_team": None},
    ]},
    {"stage": "Final", "matches": [
        {"match_no": 3, "next_match_no": None, "stage": "Final",
         "home_label": "Winner of M1", "away_label": "Winner of M2",
         "home_team": None, "away_team": None},
    ]},
]
UNRESOLVED = [
    {"group": "A", "table": [{"team_id": "a1", "played": 0}, {"team_id": "a2", "played": 0}]},
    {"group": "B", "table": [{"team_id": "b1", "played": 0}, {"team_id": "b2", "played": 0}]},
]
RESOLVED = [
    {"group": "A", "table": [{"team_id": "a1", "played": 1}, {"team_id": "a2", "played": 1}]},
    {"group": "B", "table": [{"team_id": "b1", "played": 1}, {"team_id": "b2", "played": 1}]},
]


def test_build_context_groups_and_names():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    assert ctx.group_members["A"] == ["a1", "a2"]
    assert ctx.group_resolved["A"] is None            # nobody has played -> unresolved
    assert set(ctx.matches) == {1, 2, 3}
    assert ctx.team_id_by_name["alpha"] == "a1" and ctx.team_id_by_name["aa"] == "a1"
    assert ctx.team_brief("b2") == {"id": "b2", "country": "Bern", "team_name": "BE"}


def test_resolved_group_orders_by_position():
    ctx = build_context(TEAMS, RESOLVED, BRACKET)
    assert ctx.group_resolved["A"] == ["a1", "a2"]     # size 2, need 1 game -> resolved
    assert ctx.group_resolved["B"] == ["b1", "b2"]


def test_load_context_reads_files(tmp_path):
    (tmp_path / "teams.json").write_text(json.dumps(TEAMS))
    (tmp_path / "standings.json").write_text(json.dumps(UNRESOLVED))
    (tmp_path / "bracket.json").write_text(json.dumps(BRACKET))
    ctx = load_context(str(tmp_path))
    assert set(ctx.matches) == {1, 2, 3} and ctx.group_members["B"] == ["b1", "b2"]
