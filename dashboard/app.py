"""Flask dashboard for the AIUB World Cup dataset."""
from pathlib import Path

from flask import Flask, render_template, abort, jsonify

from dashboard.data_access import DataStore
from dashboard.jobs import RefreshJob
from dashboard.sim_api import make_sim_blueprint
from dashboard.timefmt import format_dhaka
from projection.load import build_context
from projection.resolver import _side_set
from simulation.store import SimStore
from simulation.strength import standings_have_signal

SITE = "https://ofsportsaiub.org"


def _asset(path):
    if not path:
        return ""
    return f"{SITE}{path}" if path.startswith("/") else path


def _group_teams(teams_list):
    """group -> [{id, country, team_name}] for what-if group 1st/2nd selects."""
    groups: dict[str, list] = {}
    for t in teams_list:
        groups.setdefault(t.get("group") or "?", []).append(
            {"id": t.get("id"), "country": t.get("country"), "team_name": t.get("team_name")})
    for g in groups.values():
        g.sort(key=lambda t: t.get("country") or "")
    return dict(sorted(groups.items()))


def _ko_slots(ctx):
    """Bracket matches with >=2 live candidates, for what-if KO winner selects."""
    slots = []
    for match_no in sorted(ctx.matches):
        m = ctx.matches[match_no]
        candidates = sorted(_side_set(m, "home", ctx) | _side_set(m, "away", ctx))
        if len(candidates) < 2:
            continue
        slots.append({
            "match_no": match_no,
            "stage": m.get("stage"),
            "home_label": m.get("home_label"),
            "away_label": m.get("away_label"),
            "candidates": [ctx.team_brief(tid) for tid in candidates],
        })
    return slots


def create_app(data_dir="./data/latest", sim_dir=None, job=None):
    app = Flask(__name__)
    store = DataStore(data_dir)
    refresh_job = job or RefreshJob()
    app.jinja_env.filters["dhaka"] = format_dhaka

    if sim_dir is None:
        p = Path(data_dir)
        sim_dir = str(p.parent / "simulations") if p.name == "latest" else str(p / "simulations")
    sim_store = SimStore(sim_dir)
    app.register_blueprint(make_sim_blueprint(store, sim_store, data_dir))

    @app.context_processor
    def _globals():
        return {"asset": _asset, "manifest": store.manifest(),
                "nav": [("overview", "/"), ("teams", "/teams"), ("fixtures", "/fixtures"),
                        ("standings", "/standings"), ("bracket", "/bracket"), ("scorers", "/scorers")]}

    @app.route("/")
    def overview():
        fixtures = store.fixtures()
        upcoming = [f for f in fixtures if f.get("status") == "scheduled"][:6]
        played = [f for f in fixtures if f.get("status") in ("final", "live")]
        stats = {"teams": len(store.teams()), "fixtures": len(fixtures),
                 "played": len(played), "groups": len(store.standings())}
        return render_template("overview.html", title="Overview", stats=stats, upcoming=upcoming)

    @app.route("/teams")
    def teams_page():
        teams = sorted(store.teams(), key=lambda t: (t.get("group") or "", t.get("country") or ""))
        return render_template("teams.html", title="Teams", teams=teams)

    @app.route("/teams/<tid>")
    def team_detail(tid):
        team = store.team(tid)
        if not team:
            abort(404)
        roster = store.roster(tid) or {"players": []}
        projection = store.projections().get(tid, {"scenarios": {}})
        standings_signal = standings_have_signal(store.standings())
        group_teams = _group_teams(store.teams())
        ko_slots = _ko_slots(build_context(store.teams(), store.standings(), store.bracket()))
        return render_template("team_detail.html", title=team.get("country"),
                               team=team, roster=roster, projection=projection,
                               standings_signal=standings_signal, group_teams=group_teams,
                               ko_slots=ko_slots)

    @app.route("/fixtures")
    def fixtures_page():
        days = {}
        for f in store.fixtures():
            days.setdefault(f.get("date") or "TBD", []).append(f)
        return render_template("fixtures.html", title="Fixtures", days=days)

    @app.route("/standings")
    def standings_page():
        return render_template("standings.html", title="Standings", groups=store.standings())

    @app.route("/bracket")
    def bracket_page():
        return render_template("bracket.html", title="Bracket", stages=store.bracket())

    @app.route("/scorers")
    def scorers_page():
        return render_template("scorers.html", title="Top Scorers", scorers=store.scorers())

    @app.route("/refresh", methods=["POST"])
    def refresh():
        started = refresh_job.start()
        return jsonify(started=started, **refresh_job.status())

    @app.route("/refresh/status")
    def refresh_status():
        return jsonify(refresh_job.status())

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
