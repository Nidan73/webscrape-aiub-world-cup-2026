"""Orchestrate a full scrape: fetch -> parse -> write, with per-entity isolation."""
import argparse
import logging

from scraper import config
from scraper.client import Client
from scraper.parsers.teams import parse_teams
from scraper.parsers.profile import parse_profile
from scraper.parsers.fixtures import parse_fixtures
from scraper.parsers.standings import parse_standings
from scraper.parsers.scorers import parse_scorers
from scraper.parsers.bracket import parse_bracket
from scraper.writer import write_all

log = logging.getLogger(__name__)

# entity name -> (tab value, parser). "teams"/"rosters" are handled specially.
_TAB_ENTITIES = {
    "fixtures": ("fixtures", parse_fixtures),
    "standings": ("groups", parse_standings),
    "scorers": ("scorers", parse_scorers),
    "bracket": ("bracket", parse_bracket),
}


def _ok(data, url):
    return {"ok": True, "data": data, "count": len(data), "source_url": url, "error": None}


def _fail(url, exc):
    return {"ok": False, "data": [], "count": 0, "source_url": url, "error": str(exc)}


def scrape(client, out_root, only=None, no_rosters=False) -> dict:
    wanted = set(only) if only else set(config.ENTITY_FILES)
    entities: dict[str, dict] = {}

    # teams (+ rosters) come from the teams directory + per-team profiles
    if wanted & {"teams", "rosters"}:
        turl = f"{config.BASE_URL}/tab-api.php?tab=teams"
        try:
            team_stubs = parse_teams(client.fetch_tab("teams"))
            teams, rosters = [], []
            if no_rosters:
                teams = team_stubs
            else:
                for stub in team_stubs:
                    try:
                        enriched, roster = parse_profile(client.fetch_page(stub.profile_url), stub)
                        teams.append(enriched)
                        rosters.append(roster)
                    except Exception as exc:                       # per-team isolation
                        log.warning("profile %s failed: %s", stub.profile_url, exc)
                        teams.append(stub)
            if "teams" in wanted:
                entities["teams"] = _ok(teams, turl)
            if "rosters" in wanted and not no_rosters:
                entities["rosters"] = _ok(rosters, turl)
        except Exception as exc:
            if "teams" in wanted:
                entities["teams"] = _fail(turl, exc)
            if "rosters" in wanted:
                entities["rosters"] = _fail(turl, exc)

    for name, (tab, parser) in _TAB_ENTITIES.items():
        if name not in wanted:
            continue
        url = f"{config.BASE_URL}/tab-api.php?tab={tab}"
        try:
            entities[name] = _ok(parser(client.fetch_tab(tab)), url)
        except Exception as exc:                                    # per-entity isolation
            log.warning("entity %s failed: %s", name, exc)
            entities[name] = _fail(url, exc)

    return write_all(entities, out_root, source=config.BASE_URL)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scrape the AIUB World Cup 2026 site.")
    ap.add_argument("--only", nargs="+", metavar="ENTITY",
                    help="subset of: " + ", ".join(config.ENTITY_FILES))
    ap.add_argument("--no-rosters", action="store_true", help="skip per-team profile fetches")
    ap.add_argument("--delay", type=float, default=config.DEFAULT_DELAY)
    ap.add_argument("--out", default="./data", help="output root (default ./data)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    client = Client(delay=args.delay)
    manifest = scrape(client, args.out, only=args.only, no_rosters=args.no_rosters)
    for name, info in manifest["entities"].items():
        flag = "ok" if info["ok"] else f"FAIL ({info['error']})"
        count = info["count"] if info["count"] is not None else "-"
        print(f"  {name:10s} {count:>4} {flag}")
    print(f"snapshot: {manifest['snapshot_dir']}")


if __name__ == "__main__":
    main()
