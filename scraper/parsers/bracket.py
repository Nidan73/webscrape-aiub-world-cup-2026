"""Parse the knockout-bracket fragment (tab=bracket) into BracketStage records."""
import re

from bs4 import BeautifulSoup

from scraper.models import BracketStage, KnockoutMatch

_STAGE_MAP = {"r32": "R32", "r16": "R16", "qf": "QF", "sf": "SF", "final": "Final"}
_LABEL_RE = re.compile(r"(^\s*(1st|2nd|3rd)\b)|(of group)|(winner of)|(loser of)", re.I)


def _stage_of(section) -> str:
    for cls in section.get("class", []):
        if cls.startswith("stage-"):
            key = cls[len("stage-"):]
            return _STAGE_MAP.get(key, key.upper())
    return "?"


def _is_placeholder(text: str) -> bool:
    return bool(_LABEL_RE.search(text or ""))


def _int_or_none(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_bracket(html: str) -> list[BracketStage]:
    soup = BeautifulSoup(html, "lxml")
    stages: list[BracketStage] = []
    for section in soup.select("section.knockout-stage"):
        stage = _stage_of(section)
        matches: list[KnockoutMatch] = []
        for art in section.select("article.knockout-match"):
            link = art.select_one("a.knockout-match-link") or art.select_one(".match-meta a")
            sides = art.select(".ko-team")

            def side(i):
                if i >= len(sides):
                    return None, None
                span = sides[i].select_one("span")
                text = span.get_text(strip=True) if span else ""
                if _is_placeholder(text):
                    return text, None          # label
                return None, (text or None)     # resolved team

            home_label, home_team = side(0)
            away_label, away_team = side(1)
            matches.append(KnockoutMatch(
                match_no=_int_or_none(art.get("data-match-no")),
                next_match_no=_int_or_none(art.get("data-next-match")),
                match_url=link.get("href") if link else None,
                stage=stage,
                home_label=home_label, away_label=away_label,
                home_team=home_team, away_team=away_team,
                home_score=None, away_score=None, status="scheduled",
            ))
        stages.append(BracketStage(stage=stage, matches=matches))
    return stages
