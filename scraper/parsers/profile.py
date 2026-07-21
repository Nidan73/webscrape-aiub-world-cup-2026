"""Parse a team profile page into (enriched Team, Roster)."""
from dataclasses import replace

from bs4 import BeautifulSoup

from scraper.models import Team, Roster, Player, Captain


def _digits(text: str) -> int:
    d = "".join(c for c in (text or "") if c.isdigit())
    return int(d) if d else 0


def _strip_team_prefix(text: str) -> str:
    text = (text or "").strip()
    if "·" in text:
        return text.split("·", 1)[1].strip()
    if text.lower().startswith("team"):
        return text[4:].strip()
    return text


def parse_profile(html: str, team: Team) -> tuple[Team, Roster]:
    soup = BeautifulSoup(html, "lxml")

    h1 = soup.select_one("h1")
    country = h1.get_text(strip=True) if h1 else team.country

    tn = soup.select_one(".profile-team-name")
    team_name = _strip_team_prefix(tn.get_text(strip=True)) if tn else None

    captain = None
    cap = soup.select_one("a.profile-captain-feature")
    if cap:
        href = cap.get("href", "")
        cap_id = href.rsplit("/", 1)[-1].partition("-")[0]
        name_el = cap.select_one(".profile-captain-copy strong") or cap.select_one("strong")
        captain = Captain(player_id=cap_id,
                          name=name_el.get_text(strip=True) if name_el else "",
                          player_url=href)

    players: list[Player] = []
    for p in soup.select("a.profile-player"):
        href = p.get("href", "")
        last = href.rsplit("/", 1)[-1]
        pid, _, slug = last.partition("-")
        photo = p.select_one(".profile-player-photo img")
        num = p.select_one(".profile-player-photo b")
        name_el = p.select_one("strong")
        role_el = p.select_one("small")
        classes = p.get("class", [])
        is_captain = "profile-player-captain" in classes or bool(p.select_one(".roster-captain-mark"))
        totals = p.select(".player-totals span")
        goals = _digits(totals[0].get_text()) if len(totals) > 0 else 0
        assists = _digits(totals[1].get_text()) if len(totals) > 1 else 0
        cards = _digits(totals[2].get_text()) if len(totals) > 2 else 0
        players.append(Player(
            player_id=pid, slug=slug, player_url=href,
            jersey_number=num.get_text(strip=True) if num else None,
            name=name_el.get_text(strip=True) if name_el else "",
            role=role_el.get_text(strip=True) if role_el else None,
            is_captain=is_captain,
            photo_url=photo.get("src") if photo else None,
            goals=goals, assists=assists, cards=cards,
        ))

    enriched = replace(team, country=country or team.country, team_name=team_name, captain=captain)
    roster = Roster(team_id=team.id, country=country or team.country,
                    team_name=team_name, players=players)
    return enriched, roster
