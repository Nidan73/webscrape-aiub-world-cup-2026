"""Parse the teams-directory fragment (tab=teams) into Team stubs."""
from bs4 import BeautifulSoup

from scraper.models import Team


def parse_teams(html: str) -> list[Team]:
    soup = BeautifulSoup(html, "lxml")
    teams: list[Team] = []
    for card in soup.select("a.team-directory-card"):
        href = card.get("href", "")
        last = href.rsplit("/", 1)[-1]              # "38-algeria"
        team_id, _, slug = last.partition("-")
        strong = card.select_one("strong")
        country = strong.get_text(strip=True) if strong else ""
        small = card.select_one("small")
        faculty = small.get_text(strip=True) if small else None
        group_el = card.select_one(".team-directory-group")
        group = group_el.get_text(strip=True).replace("Group", "").strip() if group_el else ""
        flag = card.select_one("img.flag-icon")
        flag_url = flag.get("src") if flag else None
        teams.append(Team(
            id=team_id, slug=slug, profile_url=href, flag_url=flag_url,
            country=country, team_name=None, faculty=faculty, group=group, captain=None,
        ))
    return teams
