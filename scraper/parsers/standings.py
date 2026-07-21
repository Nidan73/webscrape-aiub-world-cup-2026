"""Parse the standings fragment (tab=groups) into GroupStanding records."""
from bs4 import BeautifulSoup

from scraper.models import GroupStanding, StandingRow


def _to_int(text: str) -> int:
    text = (text or "").strip().replace("+", "")
    try:
        return int(text)
    except ValueError:
        return 0


def parse_standings(html: str) -> list[GroupStanding]:
    soup = BeautifulSoup(html, "lxml")
    groups: list[GroupStanding] = []
    for table in soup.select("table.data-table"):
        panel = table.find_parent(class_="panel")
        h3 = panel.select_one("h3") if panel else None
        group = h3.get_text(strip=True).replace("Group", "").strip() if h3 else "?"
        rows: list[StandingRow] = []
        for i, tr in enumerate(table.select("tbody tr"), start=1):
            tds = tr.select("td")
            if not tds:
                continue
            link = tds[0].select_one("a")
            country = (link or tds[0]).get_text(strip=True)
            href = link.get("href", "") if link else ""
            team_id = href.rsplit("/", 1)[-1].partition("-")[0] if href else None
            vals = [_to_int(td.get_text()) for td in tds[1:6]]
            vals += [0] * (5 - len(vals))
            played, points, gd, gf, fp = vals[:5]
            rows.append(StandingRow(
                position=i, team_id=team_id, country=country, team_url=href or None,
                played=played, points=points, goal_diff=gd, goals_for=gf, fair_play=fp,
                qualified="qualify" in tr.get("class", []),
            ))
        groups.append(GroupStanding(group=group, table=rows))
    return groups
