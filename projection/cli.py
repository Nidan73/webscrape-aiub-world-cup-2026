"""CLI: print a team's path to the final, or write projections.json for all."""
import argparse

from projection.load import load_context
from projection.path import project_team
from projection.run import write_projections

_SCENARIO_LABEL = {"group_winner": "AS GROUP WINNER", "runner_up": "AS RUNNER-UP"}


def find_team_id(ctx, query):
    q = query.strip().lower()
    for tid, t in ctx.teams.items():
        if (t.get("country") or "").lower() == q or (t.get("team_name") or "").lower() == q:
            return tid
    for tid, t in ctx.teams.items():
        if q and (q in (t.get("country") or "").lower() or q in (t.get("team_name") or "").lower()):
            return tid
    return None


def _fmt_opponents(opps):
    if not opps:
        return "(none)"
    return ", ".join(
        o["country"] + (f" [{o['team_name']}]" if o.get("team_name") else "")
        for o in opps
    )


def render_team(ctx, team_id) -> str:
    t = ctx.teams[team_id]
    proj = project_team(team_id, ctx)
    title = t["country"] + (f" ({t['team_name']})" if t.get("team_name") else "")
    lines = [f"{title} — Group {t['group']} — path to the final", ""]
    for scen, rounds in proj["scenarios"].items():
        lines.append(_SCENARIO_LABEL.get(scen, scen))
        for r in rounds:
            lines.append(f"  {r['round']:6s} vs any of: {_fmt_opponents(r['possible_opponents'])}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Possible-opponents projection.")
    ap.add_argument("--data", default="./data/latest")
    ap.add_argument("--team", help="team by country or real name")
    ap.add_argument("--all", action="store_true", help="write projections.json for all teams")
    ap.add_argument("--json", default="./data/latest/projections.json")
    args = ap.parse_args(argv)

    ctx = load_context(args.data)
    if args.all:
        data = write_projections(ctx, args.json)
        print(f"projections for {len(data)} teams -> {args.json}")
        return
    if not args.team:
        ap.error("provide --team NAME or --all")
    tid = find_team_id(ctx, args.team)
    if not tid:
        ap.error(f"team not found: {args.team!r}")
    print(render_team(ctx, tid))


if __name__ == "__main__":
    main()
