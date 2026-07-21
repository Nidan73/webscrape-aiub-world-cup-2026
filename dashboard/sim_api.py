"""JSON API blueprint for the team simulator (ratings, what-if, Monte Carlo, history)."""
from __future__ import annotations

import math

from flask import Blueprint, jsonify, request

from projection.load import build_context
from simulation.montecarlo import run_montecarlo
from simulation.whatif import preview as whatif_preview_project


def ok(data, code=200):
    return jsonify({"ok": True, **data}), code


def err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code


def _json_object():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return None, err("request body must be a JSON object")
    return body, None


def _parse_int_param(value, name, *, default=None, min_val=1, max_val=10000):
    if value is None:
        if default is None:
            return None, err(f"{name} required")
        return default, None
    if isinstance(value, bool):
        return None, err(f"{name} must be an integer")
    if isinstance(value, float):
        if not value.is_integer():
            return None, err(f"{name} must be an integer")
        value = int(value)
    elif not isinstance(value, int):
        return None, err(f"{name} must be an integer")
    if value < min_val or value > max_val:
        return None, err(f"{name} must be between {min_val} and {max_val}")
    return value, None


def _parse_bias(value, *, default=0.0):
    if value is None:
        return default, None
    try:
        bias = float(value)
    except (TypeError, ValueError):
        return None, err("bias must be numeric")
    if not math.isfinite(bias):
        return None, err("bias must be finite")
    if bias < 0.0 or bias > 1.0:
        return None, err("bias must be between 0 and 1")
    return bias, None


def _normalize_team_id(value, *, field: str):
    if isinstance(value, str):
        return value, None
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value), None
    return None, err(f"{field} must be a team id string")


def _normalize_group_slot(slot, group_name: str):
    if not isinstance(slot, dict):
        return None, err(f"whatif.groups[{group_name!r}] must be an object with first and second")
    first, first_err = _normalize_team_id(slot.get("first"), field=f"whatif.groups[{group_name!r}].first")
    if first_err:
        return None, first_err
    second, second_err = _normalize_team_id(slot.get("second"), field=f"whatif.groups[{group_name!r}].second")
    if second_err:
        return None, second_err
    return {"first": first, "second": second}, None


def _normalize_whatif(raw):
    if raw is None:
        return {"groups": {}, "ko": {}}, None
    if not isinstance(raw, dict):
        return None, err("whatif must be an object")
    groups_raw = raw.get("groups", {})
    ko_raw = raw.get("ko", {})
    if not isinstance(groups_raw, dict):
        return None, err("whatif.groups must be an object")
    if not isinstance(ko_raw, dict):
        return None, err("whatif.ko must be an object")
    groups = {}
    for group_name, slot in groups_raw.items():
        normalized, slot_err = _normalize_group_slot(slot, str(group_name))
        if slot_err:
            return None, slot_err
        groups[str(group_name)] = normalized
    ko = {}
    for match_no, winner in ko_raw.items():
        team_id, winner_err = _normalize_team_id(winner, field=f"whatif.ko[{match_no!r}]")
        if winner_err:
            return None, winner_err
        ko[str(match_no)] = team_id
    return {"groups": groups, "ko": ko}, None


def _normalize_mc(raw, defaults=None):
    defaults = defaults or {"n": 1000, "bias": 0.0, "use_current_picks": True}
    if raw is None:
        return dict(defaults), None
    if not isinstance(raw, dict):
        return None, err("mc must be an object")
    n, n_err = _parse_int_param(raw.get("n"), "n", default=defaults["n"])
    if n_err:
        return None, n_err
    bias, bias_err = _parse_bias(raw.get("bias"), default=defaults["bias"])
    if bias_err:
        return None, bias_err
    use_current_picks = raw.get("use_current_picks", defaults["use_current_picks"])
    if not isinstance(use_current_picks, bool):
        return None, err("mc.use_current_picks must be a boolean")
    return {"n": n, "bias": bias, "use_current_picks": use_current_picks}, None


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
        body, body_err = _json_object()
        if body_err:
            return body_err
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
        body, body_err = _json_object()
        if body_err:
            return body_err
        whatif, whatif_err = _normalize_whatif(body.get("whatif"))
        if whatif_err:
            return whatif_err
        mc, mc_err = _normalize_mc(body.get("mc"))
        if mc_err:
            return mc_err
        cur = sim_store.put_current({"whatif": whatif, "mc": mc})
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
        body, body_err = _json_object()
        if body_err:
            return body_err
        team_id = body.get("team_id")
        if not team_id:
            return err("team_id required")
        picks, picks_err = _normalize_whatif(body.get("picks"))
        if picks_err:
            return picks_err
        try:
            result = whatif_preview_project(team_id, _ctx(), picks)
        except ValueError as exc:
            return err(str(exc))
        return ok(result)

    @bp.route("/montecarlo/run", methods=["POST"])
    def montecarlo_run():
        body, body_err = _json_object()
        if body_err:
            return body_err
        team_id = body.get("team_id")
        if not team_id:
            return err("team_id required")
        n, n_err = _parse_int_param(body.get("n"), "n", default=1000)
        if n_err:
            return n_err
        bias, bias_err = _parse_bias(body.get("bias"), default=0.0)
        if bias_err:
            return bias_err
        use_current_picks = body.get("use_current_picks", True)
        if not isinstance(use_current_picks, bool):
            return err("use_current_picks must be a boolean")
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
        body, body_err = _json_object()
        if body_err:
            return body_err
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
        body, body_err = _json_object()
        if body_err:
            return body_err
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
