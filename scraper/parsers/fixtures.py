"""Parse the fixtures fragment (tab=fixtures) into Fixture records."""
import re

from bs4 import BeautifulSoup

from scraper.models import Fixture, FixtureSide

_MATCH_NO = re.compile(r"Match\s*(\d+)", re.I)
_FLAG = re.compile(r"/([a-z]{2})\.png")


def _flag_code(team_el):
    img = team_el.select_one("img") if team_el else None
    if not img:
        return None
    m = _FLAG.search(img.get("src", ""))
    return m.group(1) if m else None


def _split_score(raw):
    raw = (raw or "").strip()
    if raw and raw.upper() != "VS" and ":" in raw:
        h, _, a = raw.partition(":")
        try:
            return int(h), int(a)
        except ValueError:
            return None, None
    return None, None


def parse_fixtures(html: str) -> list[Fixture]:
    soup = BeautifulSoup(html, "lxml")
    out: list[Fixture] = []
    for card in soup.select("article.fixture-row"):
        link = card.select_one("a.fixture-card-link")
        href = link.get("href", "") if link else ""
        last = href.rsplit("/", 1)[-1]
        match_id = last.partition("-")[0]

        head = card.select(".fixture-card-head span")
        group = head[0].get_text(strip=True).replace("Group", "").strip() if len(head) > 0 else None
        dt = head[1].get_text(strip=True) if len(head) > 1 else None
        date = time = None
        if dt:
            parts = dt.split(",", 1)
            date = parts[0].strip()
            time = parts[1].strip() if len(parts) > 1 else None

        home_el = card.select_one(".fixture-side.home .fixture-team")
        away_el = card.select_one(".fixture-side.away .fixture-team")
        home_country = home_el.get_text(strip=True) if home_el else ""
        away_country = away_el.get_text(strip=True) if away_el else ""

        score_el = card.select_one(".fixture-score")
        raw_score = score_el.get_text(strip=True) if score_el else "VS"
        hs, as_ = _split_score(raw_score)

        no_el = card.select_one(".fixture-no")
        if no_el and _MATCH_NO.search(no_el.get_text()):
            match_no = int(_MATCH_NO.search(no_el.get_text()).group(1))
        else:
            match_no = None

        status_el = card.select_one(".fixture-status")
        status_txt = status_el.get_text(strip=True).lower() if status_el else ""
        if raw_score.upper() == "VS":
            status = "scheduled"
        elif "live" in status_txt or "'" in status_txt:
            status = "live"
        else:
            status = "final"

        out.append(Fixture(
            match_id=match_id, slug=last.partition("-")[2], match_url=href,
            match_no=match_no, group=group, date=date, time=time, datetime_iso=None,
            home=FixtureSide(country=home_country, flag_code=_flag_code(home_el)),
            away=FixtureSide(country=away_country, flag_code=_flag_code(away_el)),
            home_score=hs, away_score=as_, status=status, raw_score=raw_score,
        ))
    return out
