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
