"""Apply what-if picks onto a projection Context and re-project a team."""
from __future__ import annotations

import copy

from projection.resolver import _side_set
from projection.path import project_team


def validate_picks(ctx, picks: dict) -> str | None:
    picks = picks or {}
    groups = picks.get("groups") or {}
    ko = picks.get("ko") or {}
    for g, slot in groups.items():
        members = set(ctx.group_members.get(g, []))
        if not members:
            return f"Unknown group {g}"
        first, second = slot.get("first"), slot.get("second")
        if not first or not second:
            return f"Group {g} needs first and second"
        if first == second:
            return f"Group {g} first and second must differ"
        if first not in members or second not in members:
            return f"Pick not in group {g}"
    for mno, winner in ko.items():
        try:
            match_no = int(mno)
        except (TypeError, ValueError):
            return f"Invalid match_no {mno}"
        match = ctx.matches.get(match_no)
        if not match:
            return f"Unknown match {match_no}"
        if winner not in ctx.teams:
            return f"Unknown winner {winner}"
        # candidates checked after groups applied in apply; light check here
    return None


def apply_picks(ctx, picks: dict):
    ctx = copy.deepcopy(ctx)
    ctx._reach_memo = {}
    picks = picks or {}
    for g, slot in (picks.get("groups") or {}).items():
        first, second = slot["first"], slot["second"]
        rest = [t for t in ctx.group_members.get(g, []) if t not in (first, second)]
        ctx.group_resolved[g] = [first, second, *rest]
    ctx._reach_memo.clear()
    for mno, winner in (picks.get("ko") or {}).items():
        match = ctx.matches[int(mno)]
        H = _side_set(match, "home", ctx)
        A = _side_set(match, "away", ctx)
        if winner not in H | A:
            raise ValueError(f"Winner {winner} not in match {mno} candidates")
        country = ctx.teams[winner]["country"]
        if winner in H:
            match["home_team"] = country
        if winner in A:
            match["away_team"] = country
        # If winner only on one side, clear the other concrete so labels remain for opp set
        if winner in H and winner not in A:
            # keep away as labels
            pass
        if winner in A and winner not in H:
            pass
    ctx._reach_memo.clear()
    return ctx


def preview(team_id: str, ctx, picks: dict) -> dict:
    if team_id not in ctx.teams:
        raise ValueError(f"Unknown team {team_id}")
    err = validate_picks(ctx, picks)
    if err:
        raise ValueError(err)
    applied = apply_picks(ctx, picks)
    return {"ok": True, "projection": project_team(team_id, applied)}
