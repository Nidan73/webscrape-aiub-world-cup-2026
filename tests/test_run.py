import json

from scraper.run import scrape

TEAMS_FRAG = """
<div class="teams-directory-grid">
  <a class="team-directory-card" href="/teams/42-netherlands">
    <span class="team-directory-names"><strong>Netherlands</strong><small>FST</small></span>
    <span class="team-directory-group">Group A</span></a>
</div>"""
PROFILE = """
<h1>Netherlands</h1><span class="profile-team-name">Team · CS BACKBENCHER</span>
<a class="profile-player" href="/players/658-rezu">
  <span class="profile-player-photo"><img src="/i.png"><b>02</b></span>
  <div><strong>Rezu</strong><small>Player</small></div>
  <div class="player-totals"><span><b>0</b> goals</span><span><b>0</b> assists</span><span><b>0</b> cards</span></div>
</a>"""
FIXTURES = '<article class="fixture-row"><a class="fixture-card-link" href="/matches/1-a-vs-b"></a>' \
           '<div class="fixture-card-head"><span>Group A</span><span>Jul 28, 8:00 AM</span></div>' \
           '<div class="fixture-card-main"><div class="fixture-side home"><span class="fixture-team">A</span></div>' \
           '<strong class="fixture-score">VS</strong>' \
           '<div class="fixture-side away"><span class="fixture-team">B</span></div></div>' \
           '<div class="fixture-card-foot"><span class="fixture-no">Match 1</span></div></article>'
GROUPS = '<div class="panel"><h3>Group A</h3><table class="data-table"><tbody>' \
         '<tr class="qualify"><td><a href="/teams/42-netherlands">Netherlands</a></td>' \
         '<td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr></tbody></table></div>'
SCORERS = '<div class="scorers-empty"></div>'
BRACKET = '<section class="knockout-stage stage-r32"><article class="knockout-match" data-match-no="49">' \
          '<div class="ko-team "><span>1st of Group A</span></div>' \
          '<div class="ko-team "><span>2nd of Group I</span></div></article></section>'


class FakeClient:
    def fetch_tab(self, name):
        return {"teams": TEAMS_FRAG, "fixtures": FIXTURES, "groups": GROUPS,
                "scorers": SCORERS, "bracket": BRACKET}[name]

    def fetch_page(self, path):
        return PROFILE


def test_scrape_writes_all_entities(tmp_path):
    manifest = scrape(FakeClient(), str(tmp_path))
    latest = tmp_path / "latest"
    for name in ("teams", "rosters", "fixtures", "standings", "scorers", "bracket"):
        assert (latest / f"{name}.json").exists(), name
        assert manifest["entities"][name]["ok"] is True

    teams = json.loads((latest / "teams.json").read_text())
    assert teams[0]["team_name"] == "CS BACKBENCHER"       # enriched from profile
    rosters = json.loads((latest / "rosters.json").read_text())
    assert rosters[0]["players"][0]["name"] == "Rezu"
    assert json.loads((latest / "scorers.json").read_text()) == []


def test_scrape_only_subset(tmp_path):
    manifest = scrape(FakeClient(), str(tmp_path), only=["fixtures"], no_rosters=True)
    assert (tmp_path / "latest" / "fixtures.json").exists()
    assert "teams" not in manifest["entities"]
