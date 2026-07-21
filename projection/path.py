"""Build a team's round-by-round possible opponents up to the final."""
from projection.resolver import _side_set


def entry_matches(team, ctx):
    """R32 matches a team can enter, with the side it occupies and the scenario."""
    g = team["group"]
    out = []
    for m in ctx.matches.values():
        if m.get("stage") != "R32":
            continue
        if m.get("home_label") == f"1st of Group {g}":
            out.append((m, "home", "group_winner"))
        if m.get("away_label") == f"2nd of Group {g}":
            out.append((m, "away", "runner_up"))
    return out


def path_for_entry(entry, my_side, team_id, ctx):
    rounds = []
    opp_side = "away" if my_side == "home" else "home"
    rounds.append({"round": entry["stage"],
                   "possible_opponents": _side_set(entry, opp_side, ctx) - {team_id}})
    cur = entry
    while cur.get("next_match_no"):
        parent = ctx.matches.get(cur["next_match_no"])
        if not parent:
            break
        winner_label = f"Winner of M{cur['match_no']}"
        opp_side = "away" if parent.get("home_label") == winner_label else "home"
        rounds.append({"round": parent["stage"],
                       "possible_opponents": _side_set(parent, opp_side, ctx) - {team_id}})
        cur = parent
    return rounds


def project_team(team_id, ctx):
    team = ctx.teams[team_id]
    scenarios = {}
    for entry, side, scenario in entry_matches(team, ctx):
        rounds = path_for_entry(entry, side, team_id, ctx)
        scenarios[scenario] = [
            {"round": r["round"],
             "possible_opponents": [
                 ctx.team_brief(t)
                 for t in sorted(r["possible_opponents"], key=lambda i: (ctx.teams[i]["country"] or ""))
             ]}
            for r in rounds
        ]
    return {"country": team["country"], "team_name": team["team_name"], "scenarios": scenarios}
