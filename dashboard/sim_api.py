"""JSON API blueprint for the team simulator (ratings, what-if, Monte Carlo, history)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from projection.load import build_context
from simulation.montecarlo import run_montecarlo
from simulation.whatif import preview as whatif_preview_project


def ok(data, code=200):
    return jsonify({"ok": True, **data}), code


def err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code


def make_sim_blueprint(store, sim_store, data_dir=None):
    """`store` is the dashboard DataStore (teams/standings/bracket reads),
    `sim_store` is the SimStore (ratings/current/history persistence),
    `data_dir` is retained for parity with the on-disk layout but the live
    Context is always built from `store`'s cached lists so it reflects the
    latest scrape without a second file read."""
    bp = Blueprint("sim_api", __name__, url_prefix="/api/sim")

    def _ctx():
        return build_context(store.teams(), store.standings(), store.bracket())

    @bp.route("/ratings", methods=["GET"])
    def get_ratings():
        return ok({"ratings": sim_store.get_ratings()})

    @bp.route("/ratings", methods=["PUT"])
    def put_ratings():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return err("ratings must be an object of team_id -> number")
        try:
            clean = sim_store.put_ratings(body)
        except (TypeError, ValueError):
            return err("ratings values must be numeric")
        return ok({"ratings": clean})

    @bp.route("/current", methods=["GET"])
    def get_current():
        return ok({"current": sim_store.get_current()})

    @bp.route("/current", methods=["PUT"])
    def put_current():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return err("current must be an object")
        cur = sim_store.put_current(body)
        if body.get("autosave", True):
            sim_store.save_history(
                type="auto",
                title="auto",
                payload={"ratings": sim_store.get_ratings(), "whatif": cur["whatif"], "mc": cur["mc"]},
                team_id=body.get("team_id"),
            )
        return ok({"current": cur})

    @bp.route("/whatif/preview", methods=["POST"])
    def whatif_preview():
        body = request.get_json(silent=True) or {}
        team_id = body.get("team_id")
        if not team_id:
            return err("team_id required")
        try:
            result = whatif_preview_project(team_id, _ctx(), body.get("picks"))
        except ValueError as exc:
            return err(str(exc))
        return ok(result)

    @bp.route("/montecarlo/run", methods=["POST"])
    def montecarlo_run():
        body = request.get_json(silent=True) or {}
        team_id = body.get("team_id")
        if not team_id:
            return err("team_id required")
        try:
            n = int(body.get("n", 1000))
            bias = float(body.get("bias", 0.0))
        except (TypeError, ValueError):
            return err("n and bias must be numeric")
        use_current_picks = bool(body.get("use_current_picks", True))
        current = sim_store.get_current()
        picks = body["picks"] if "picks" in body else current.get("whatif")
        try:
            result = run_montecarlo(
                team_id=team_id,
                ctx=_ctx(),
                standings_list=store.standings(),
                ratings=sim_store.get_ratings(),
                n=n,
                bias=bias,
                picks=picks,
                use_current_picks=use_current_picks,
                seed=body.get("seed"),
            )
        except ValueError as exc:
            return err(str(exc))
        return ok(result)

    @bp.route("/history", methods=["GET"])
    def list_history():
        return ok({"history": sim_store.list_history()})

    @bp.route("/history", methods=["POST"])
    def create_history():
        body = request.get_json(silent=True) or {}
        htype = body.get("type", "named")
        if htype not in ("auto", "named"):
            return err("type must be auto or named")
        current = sim_store.get_current()
        payload = {
            "ratings": sim_store.get_ratings(),
            "whatif": current["whatif"],
            "mc": current["mc"],
        }
        if "mc_summary" in body:
            payload["mc_summary"] = body["mc_summary"]
        entry = sim_store.save_history(type=htype, title=body.get("title"), payload=payload,
                                        team_id=body.get("team_id"))
        return ok({"entry": entry}, 201)

    @bp.route("/history/<hid>/restore", methods=["POST"])
    def restore_history(hid):
        try:
            data = sim_store.restore(hid)
        except ValueError as exc:
            return err(str(exc))
        except KeyError:
            return err(f"History {hid} not found", 404)
        return ok({"current": sim_store.get_current(), "entry": data})

    @bp.route("/history/<hid>", methods=["PATCH"])
    def rename_history(hid):
        body = request.get_json(silent=True) or {}
        title = body.get("title")
        if not title:
            return err("title required")
        try:
            data = sim_store.rename(hid, title)
        except ValueError as exc:
            return err(str(exc))
        except KeyError:
            return err(f"History {hid} not found", 404)
        return ok({"entry": data})

    @bp.route("/history/<hid>", methods=["DELETE"])
    def delete_history(hid):
        if not sim_store.delete(hid):
            return err(f"History {hid} not found", 404)
        return ok({"deleted": True})

    return bp
