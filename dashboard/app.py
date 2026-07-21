"""Flask dashboard for the AIUB World Cup dataset."""
from pathlib import Path

from flask import Flask, render_template, abort, jsonify

from dashboard.data_access import DataStore
from dashboard.jobs import RefreshJob
from dashboard.sim_api import make_sim_blueprint
from simulation.store import SimStore

SITE = "https://ofsportsaiub.org"


def _asset(path):
    if not path:
        return ""
    return f"{SITE}{path}" if path.startswith("/") else path


def create_app(data_dir="./data/latest", sim_dir=None, job=None):
    app = Flask(__name__)
    store = DataStore(data_dir)
    refresh_job = job or RefreshJob()

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
        return render_template("team_detail.html", title=team.get("country"),
                               team=team, roster=roster, projection=projection)

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
