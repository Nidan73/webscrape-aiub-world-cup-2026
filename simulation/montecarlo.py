"""Monte Carlo path-to-final frequencies for one focus team."""
from __future__ import annotations

import copy
import random
from collections import Counter, defaultdict

from projection.resolver import _side_set
from simulation.strength import standings_have_signal, team_strengths, weighted_choice
from simulation.whatif import apply_picks


def _sample_group_order(rng, members, strengths, bias):
    remaining = list(members)
    order = []
    while remaining:
        pick = weighted_choice(rng, remaining, strengths, bias)
        order.append(pick)
        remaining.remove(pick)
    return order


def _resolve_all_ko(rng, ctx, strengths, bias, ko_locked=None):
    """Resolve every KO match in ascending match_no order.

    For each match: pick a winner (locked by `ko_locked`, forced if only one
    candidate, else sampled), concretize BOTH sides of the match with the
    actual playing teams' countries (for the path walker), and propagate the
    winner's country directly into any OTHER match's concrete home_team/
    away_team field whose label reads "Winner of M{match_no}" -- mirroring
    `simulation.whatif._apply_ko_pick` so that `_side_set` never has to fall
    back to `reach_set`, which would otherwise union both playing teams of
    this match together instead of resolving to the single winner.
    """
    ko_locked = ko_locked or {}
    for match_no in sorted(ctx.matches):
        match = ctx.matches[match_no]
        H = _side_set(match, "home", ctx)
        A = _side_set(match, "away", ctx)
        cands = list(H | A)
        if not cands:
            continue
        if match_no in ko_locked and ko_locked[match_no] in cands:
            winner = ko_locked[match_no]
        elif len(cands) == 1:
            winner = cands[0]
        else:
            winner = weighted_choice(rng, cands, strengths, bias)
        match["_winner_id"] = winner

        winner_country = ctx.teams[winner]["country"]
        if winner in H:
            match["home_team"] = winner_country
        if winner in A:
            match["away_team"] = winner_country
        losers = [c for c in cands if c != winner]
        if losers:
            loser_country = ctx.teams[losers[0]]["country"]
            if winner in H and not match.get("away_team"):
                match["away_team"] = loser_country
            elif winner in A and not match.get("home_team"):
                match["home_team"] = loser_country

        winner_label = f"winner of m{match_no}"
        for other in ctx.matches.values():
            if other is match:
                continue
            if (other.get("home_label") or "").strip().lower() == winner_label:
                other["home_team"] = winner_country
            if (other.get("away_label") or "").strip().lower() == winner_label:
                other["away_team"] = winner_country
        ctx._reach_memo.clear()


def _team_path_played(team_id, ctx):
    """Return [(stage, opponent_id), ...] for matches the team actually plays.

    A team that does not finish 1st or 2nd in its group never enters the
    knockout bracket, so it never "reaches" any KO round.
    """
    team = ctx.teams[team_id]
    positions = ctx.group_resolved.get(team.get("group"))
    if not positions or team_id not in positions[:2]:
        return []

    country = (team.get("country") or "").lower()
    played = []
    for m in sorted(ctx.matches.values(), key=lambda x: x.get("match_no") or 0):
        home = (m.get("home_team") or "").lower()
        away = (m.get("away_team") or "").lower()
        if country not in (home, away):
            continue
        opp_country = away if home == country else home
        opp_id = ctx.team_id_by_name.get(opp_country) if opp_country else None
        played.append((m.get("stage") or "?", opp_id))
        if m.get("_winner_id") != team_id:
            break
    return played


def run_montecarlo(*, team_id, ctx, standings_list, ratings, n, bias,
                   picks=None, use_current_picks=True, seed=None):
    if n < 1 or n > 10000:
        raise ValueError("n must be between 1 and 10000")
    if team_id not in ctx.teams:
        raise ValueError(f"Unknown team {team_id}")
    rng = random.Random(seed)
    strengths = team_strengths(standings_list, overrides=ratings or {})
    for tid in ctx.teams:
        strengths.setdefault(tid, 1.0)

    apply = bool(use_current_picks and picks)
    ko_locked = {}
    if apply:
        ko_locked = {int(mno): wid for mno, wid in (picks.get("ko") or {}).items()}

    reach_counts = Counter()
    opp_counts = defaultdict(Counter)
    trials = int(n)

    for _ in range(trials):
        if apply:
            trial = apply_picks(ctx, picks)
        else:
            trial = copy.deepcopy(ctx)
            trial._reach_memo = {}

        for g, members in trial.group_members.items():
            if trial.group_resolved.get(g) is None:
                trial.group_resolved[g] = _sample_group_order(rng, members, strengths, bias)
        trial._reach_memo.clear()

        _resolve_all_ko(rng, trial, strengths, bias, ko_locked)
        path = _team_path_played(team_id, trial)
        for stage, opp_id in path:
            reach_counts[stage] += 1
            if opp_id:
                opp_counts[stage][opp_id] += 1

    reach = {k: reach_counts[k] / trials for k in reach_counts}
    opponents = {}
    for stage, counter in opp_counts.items():
        items = []
        for oid, cnt in counter.most_common(10):
            brief = ctx.team_brief(oid)
            items.append({**brief, "pct": cnt / trials})
        opponents[stage] = items

    return {
        "ok": True,
        "n": trials,
        "bias": float(bias),
        "standings_signal": standings_have_signal(standings_list),
        "reach": reach,
        "opponents": opponents,
    }
