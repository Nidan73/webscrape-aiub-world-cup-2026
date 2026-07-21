"""Resolve bracket slot labels to sets of possible team ids."""
import re

_GROUP_SEED = re.compile(r"^\s*(\d+)(?:st|nd|rd|th)\s+of\s+group\s+([a-p])\s*$", re.I)
_WINNER = re.compile(r"^\s*winner of m(\d+)\s*$", re.I)


def _side_set(match, side, ctx):
    concrete = match.get(f"{side}_team")
    if concrete:
        tid = ctx.team_id_by_name.get(concrete.strip().lower())
        return {tid} if tid else set()
    return resolve(match.get(f"{side}_label"), ctx)


def resolve(label, ctx):
    if not label:
        return set()
    m = _GROUP_SEED.match(label)
    if m:
        pos = int(m.group(1))
        group = m.group(2).upper()
        resolved = ctx.group_resolved.get(group)
        if resolved and 0 <= pos - 1 < len(resolved) and resolved[pos - 1]:
            return {resolved[pos - 1]}
        return set(ctx.group_members.get(group, []))
    w = _WINNER.match(label)
    if w:
        return reach_set(int(w.group(1)), ctx)
    tid = ctx.team_id_by_name.get(label.strip().lower())
    return {tid} if tid else set()


def reach_set(match_no, ctx):
    if match_no in ctx._reach_memo:
        return ctx._reach_memo[match_no]
    ctx._reach_memo[match_no] = set()          # cycle guard (tree has none, but safe)
    m = ctx.matches.get(match_no)
    if not m:
        return set()
    result = _side_set(m, "home", ctx) | _side_set(m, "away", ctx)
    ctx._reach_memo[match_no] = result
    return result
