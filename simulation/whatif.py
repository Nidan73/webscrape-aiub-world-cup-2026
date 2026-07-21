"""Apply what-if picks onto a projection Context and re-project a team."""
from __future__ import annotations

import copy

from projection.resolver import _side_set
from projection.path import project_team


def _apply_group_picks(ctx, groups: dict) -> None:
    for g, slot in (groups or {}).items():
        first, second = slot["first"], slot["second"]
        rest = [t for t in ctx.group_members.get(g, []) if t not in (first, second)]
        ctx.group_resolved[g] = [first, second, *rest]
    ctx._reach_memo.clear()


def _apply_ko_pick(ctx, match_no: int, winner) -> None:
    """Concretize `winner` on their side of `match_no` and rewrite every
    "Winner of M{match_no}" label elsewhere to the winner's country, so
    `resolve()` hits `team_id_by_name` directly instead of unioning both
    sides of the match via `reach_set`. Raises ValueError if `winner` is
    not a candidate for the match."""
    match = ctx.matches[match_no]
    H = _side_set(match, "home", ctx)
    A = _side_set(match, "away", ctx)
    if winner not in H | A:
        raise ValueError(f"Winner {winner} not in match {match_no} candidates")
    country = ctx.teams[winner]["country"]
    if winner in H:
        match["home_team"] = country
    if winner in A:
        match["away_team"] = country
    winner_label = f"winner of m{match_no}"
    for other in ctx.matches.values():
        if other is match:
            continue
        if (other.get("home_label") or "").strip().lower() == winner_label:
            other["home_label"] = country
        if (other.get("away_label") or "").strip().lower() == winner_label:
            other["away_label"] = country
    ctx._reach_memo.clear()


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
    if not ko:
        return None
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
    # Apply group + KO picks onto a scratch context so KO winners are checked
    # against the actual candidates after groups are forced (and after any
    # earlier KO picks are concretized).
    scratch = copy.deepcopy(ctx)
    scratch._reach_memo = {}
    _apply_group_picks(scratch, groups)
    for mno, winner in ko.items():
        match_no = int(mno)
        try:
            _apply_ko_pick(scratch, match_no, winner)
        except ValueError:
            return f"Winner {winner} not in match {match_no} candidates"
    return None


def apply_picks(ctx, picks: dict):
    ctx = copy.deepcopy(ctx)
    ctx._reach_memo = {}
    picks = picks or {}
    _apply_group_picks(ctx, picks.get("groups") or {})
    for mno, winner in (picks.get("ko") or {}).items():
        _apply_ko_pick(ctx, int(mno), winner)
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
