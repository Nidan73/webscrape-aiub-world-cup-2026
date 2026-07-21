# tests/test_simulation_strength.py
from simulation.strength import standings_have_signal, team_strengths, blend_probs, weighted_choice
import random

EMPTY = [
    {"group": "A", "table": [
        {"team_id": "a1", "played": 0, "points": 0, "goal_diff": 0, "goals_for": 0},
        {"team_id": "a2", "played": 0, "points": 0, "goal_diff": 0, "goals_for": 0},
    ]},
]
PLAYED = [
    {"group": "A", "table": [
        {"team_id": "a1", "played": 2, "points": 6, "goal_diff": 4, "goals_for": 5},
        {"team_id": "a2", "played": 2, "points": 0, "goal_diff": -4, "goals_for": 1},
    ]},
]


def test_no_signal_when_all_zero():
    assert standings_have_signal(EMPTY) is False
    s = team_strengths(EMPTY)
    assert s["a1"] == s["a2"] == 1.0


def test_signal_from_points():
    assert standings_have_signal(PLAYED) is True
    s = team_strengths(PLAYED)
    assert s["a1"] > s["a2"]


def test_overrides_replace_base():
    s = team_strengths(EMPTY, overrides={"a2": 9.0})
    assert s["a2"] == 9.0 and s["a1"] == 1.0


def test_blend_bias_zero_is_uniform():
    p = blend_probs([9.0, 1.0], bias=0.0)
    assert abs(p[0] - 0.5) < 1e-9 and abs(p[1] - 0.5) < 1e-9


def test_blend_bias_one_follows_strength():
    p = blend_probs([9.0, 1.0], bias=1.0)
    assert abs(p[0] - 0.9) < 1e-9 and abs(p[1] - 0.1) < 1e-9


def test_weighted_choice_deterministic_with_seed():
    strengths = {"a1": 1.0, "a2": 9.0}
    rng = random.Random(0)
    picks = [weighted_choice(rng, ["a1", "a2"], strengths, bias=1.0) for _ in range(200)]
    assert picks.count("a2") > picks.count("a1")


class _AlwaysZeroRng:
    def random(self):
        return 0.0


def test_zero_weight_never_chosen_at_bias_one():
    strengths = {"a1": 0.0, "a2": 9.0}
    rng = _AlwaysZeroRng()
    for _ in range(10):
        assert weighted_choice(rng, ["a1", "a2"], strengths, bias=1.0) == "a2"
