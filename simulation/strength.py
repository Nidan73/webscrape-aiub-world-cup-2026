"""Hybrid team strength and bias-blended sampling."""
from __future__ import annotations


def standings_have_signal(standings_list: list) -> bool:
    for gs in standings_list or []:
        for row in gs.get("table") or []:
            if (row.get("played") or 0) > 0 or (row.get("points") or 0) > 0:
                return True
            if (row.get("goal_diff") or 0) != 0 or (row.get("goals_for") or 0) > 0:
                return True
    return False


def team_strengths(standings_list: list, overrides: dict[str, float] | None = None) -> dict[str, float]:
    overrides = overrides or {}
    out: dict[str, float] = {}
    signal = standings_have_signal(standings_list)
    for gs in standings_list or []:
        for row in gs.get("table") or []:
            tid = row.get("team_id")
            if not tid:
                continue
            if signal:
                pts = float(row.get("points") or 0)
                gd = float(row.get("goal_diff") or 0)
                gf = float(row.get("goals_for") or 0)
                # Strictly positive weight: pts primary, small GD/GF tie-break.
                out[tid] = max(0.01, 1.0 + pts + 0.1 * gd + 0.01 * gf)
            else:
                out[tid] = 1.0
    for tid, val in overrides.items():
        out[str(tid)] = float(val)
    return out


def blend_probs(weights: list[float], bias: float) -> list[float]:
    n = len(weights)
    if n == 0:
        return []
    bias = max(0.0, min(1.0, float(bias)))
    pos = [max(0.0, float(w)) for w in weights]
    if sum(pos) <= 0:
        pos = [1.0] * n
    s = sum(pos)
    p_s = [w / s for w in pos]
    p_u = [1.0 / n] * n
    mixed = [(1 - bias) * u + bias * st for u, st in zip(p_u, p_s)]
    tot = sum(mixed) or 1.0
    return [m / tot for m in mixed]


def weighted_choice(rng, candidates: list[str], strengths: dict[str, float], bias: float) -> str:
    if not candidates:
        raise ValueError("candidates must be non-empty")
    weights = [float(strengths.get(c, 1.0)) for c in candidates]
    probs = blend_probs(weights, bias)
    r = rng.random()
    acc = 0.0
    for c, p in zip(candidates, probs):
        acc += p
        if r < acc:
            return c
    return candidates[-1]
