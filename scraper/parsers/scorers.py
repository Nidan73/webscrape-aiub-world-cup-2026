"""Parse the top-scorers fragment (tab=scorers). Empty until first goal."""
from bs4 import BeautifulSoup

from scraper.models import Scorer


def _digits(text: str) -> int:
    d = "".join(c for c in (text or "") if c.isdigit())
    return int(d) if d else 0


def parse_scorers(html: str) -> list[Scorer]:
    soup = BeautifulSoup(html, "lxml")
    if soup.select_one(".scorers-empty"):
        return []
    out: list[Scorer] = []
    for i, row in enumerate(soup.select(".scorers-row"), start=1):
        name_el = row.select_one("strong")
        team_el = row.select_one("small")
        goals_el = row.select_one("b")
        link = row.select_one("a[href*='/players/']")
        pid = link.get("href", "").rsplit("/", 1)[-1].partition("-")[0] if link else None
        out.append(Scorer(
            rank=i, player_id=pid,
            name=name_el.get_text(strip=True) if name_el else "",
            team=team_el.get_text(strip=True) if team_el else None,
            goals=_digits(goals_el.get_text()) if goals_el else 0,
        ))
    return out
