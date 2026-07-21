"""Build projections.json for every team from the scraped data."""
import argparse
import json
import logging
import os

from projection.load import load_context
from projection.path import project_team

log = logging.getLogger(__name__)


def build_projections(ctx) -> dict:
    return {tid: project_team(tid, ctx) for tid in ctx.teams}


def write_projections(ctx, out_path) -> dict:
    data = build_projections(ctx)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build possible-opponents projections.")
    ap.add_argument("--data", default="./data/latest", help="input dir with the scraped *.json")
    ap.add_argument("--out", default="./data/latest/projections.json")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ctx = load_context(args.data)
    data = write_projections(ctx, args.out)
    print(f"projections for {len(data)} teams -> {args.out}")


if __name__ == "__main__":
    main()
