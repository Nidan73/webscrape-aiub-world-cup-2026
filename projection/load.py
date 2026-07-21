"""Load data/latest JSON into a Context for the projection engine."""
import json
import os
from dataclasses import dataclass, field


@dataclass
class Context:
    teams: dict            # id -> {id, country, team_name, group}
    group_members: dict    # group -> [id]
    group_resolved: dict   # group -> [id ordered by position] or None
    matches: dict          # match_no(int) -> match dict
    team_id_by_name: dict  # lowercased country/team_name -> id
    _reach_memo: dict = field(default_factory=dict)

    def team_brief(self, tid):
        t = self.teams[tid]
        return {"id": t["id"], "country": t["country"], "team_name": t["team_name"]}


def build_context(teams_list, standings_list, bracket_list) -> Context:
    teams, group_members, team_id_by_name = {}, {}, {}
    for t in teams_list:
        tid = t["id"]
        teams[tid] = {"id": tid, "country": t.get("country"),
                      "team_name": t.get("team_name"), "group": t.get("group")}
        group_members.setdefault(t.get("group"), []).append(tid)
        if t.get("country"):
            team_id_by_name[t["country"].lower()] = tid
        if t.get("team_name"):
            team_id_by_name[t["team_name"].lower()] = tid

    group_resolved = {}
    for gs in standings_list:
        group = gs.get("group")
        table = gs.get("table", [])
        size = len(group_members.get(group, [])) or len(table)
        need = size - 1
        decided = bool(table) and need > 0 and all((row.get("played") or 0) >= need for row in table)
        group_resolved[group] = [row.get("team_id") for row in table] if decided else None

    matches = {}
    for stage in bracket_list:
        for m in stage.get("matches", []):
            if m.get("match_no") is not None:
                matches[m["match_no"]] = m

    return Context(teams=teams, group_members=group_members, group_resolved=group_resolved,
                   matches=matches, team_id_by_name=team_id_by_name)


def load_context(data_dir) -> Context:
    def _load(name):
        with open(os.path.join(data_dir, name), encoding="utf-8") as fh:
            return json.load(fh)
    return build_context(_load("teams.json"), _load("standings.json"), _load("bracket.json"))
