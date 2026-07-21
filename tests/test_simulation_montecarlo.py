from projection.load import build_context
from tests.test_projection_load import TEAMS, BRACKET, UNRESOLVED
from simulation.montecarlo import run_montecarlo


def test_rejects_too_many():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    try:
        run_montecarlo(team_id="a1", ctx=ctx, standings_list=UNRESOLVED,
                       ratings={}, n=10001, bias=0.0, seed=1)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "10000" in str(e)


def test_seeded_run_returns_shape():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    out = run_montecarlo(team_id="a1", ctx=ctx, standings_list=UNRESOLVED,
                         ratings={}, n=200, bias=0.0, seed=42)
    assert out["ok"] is True and out["n"] == 200
    assert "R32" in out["reach"]
    assert out["reach"]["R32"] > 0  # a1 can finish top2 often enough in tiny groups
    assert isinstance(out["opponents"].get("R32", []), list)


def test_bias_favors_strong_override():
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    weak = run_montecarlo(team_id="a2", ctx=ctx, standings_list=UNRESOLVED,
                          ratings={"a1": 100.0, "a2": 0.01, "b1": 1, "b2": 1},
                          n=400, bias=1.0, seed=7)
    strong = run_montecarlo(team_id="a1", ctx=ctx, standings_list=UNRESOLVED,
                            ratings={"a1": 100.0, "a2": 0.01, "b1": 1, "b2": 1},
                            n=400, bias=1.0, seed=7)
    # Both a1/a2 are guaranteed top-2 in a 2-team group, so R32 reach is
    # always 1.0 for either regardless of strength -- the strength/bias
    # signal only shows up once a KO match must actually be won. Final reach
    # (winning both KO rounds) is where "bias favors the strong override"
    # is observable.
    assert strong["reach"]["R32"] == weak["reach"]["R32"] == 1.0
    assert strong["reach"]["Final"] > weak["reach"]["Final"]


def test_use_current_picks_locks_final_reach_to_certainty():
    """Regression for the MC picks parity hole: forcing groups + KO winner
    onto a1's own path must make Final reach == 1.0 when use_current_picks
    is True, and a materially lower (random) Final reach when it's False --
    i.e. `picks` must actually be threaded into the trial, not ignored."""
    ctx = build_context(TEAMS, UNRESOLVED, BRACKET)
    picks = {
        "groups": {"A": {"first": "a1", "second": "a2"},
                   "B": {"first": "b1", "second": "b2"}},
        # M1 = 1st of A vs 2nd of B -> {a1, b2}; lock a1 to win M1 and
        # therefore reach the Final every trial.
        "ko": {"1": "a1"},
    }
    locked = run_montecarlo(team_id="a1", ctx=ctx, standings_list=UNRESOLVED,
                            ratings={}, n=200, bias=0.0, picks=picks,
                            use_current_picks=True, seed=3)
    unlocked = run_montecarlo(team_id="a1", ctx=ctx, standings_list=UNRESOLVED,
                              ratings={}, n=200, bias=0.0, picks=picks,
                              use_current_picks=False, seed=3)
    assert locked["reach"]["Final"] == 1.0
    # Unforced: a1 must still win two coin-flip-ish KO rounds, so reach is
    # materially below certainty -- nowhere near the locked 1.0.
    assert unlocked["reach"]["Final"] < 0.75
