from scraper.parsers.teams import parse_teams

HTML = """
<div class="teams-directory-grid">
  <a class="team-directory-card" href="/teams/38-algeria" data-search="algeria bba blackout fba group a">
    <span class="team-directory-flag"><img class="flag-icon" src="/assets/flags/w40/dz.png"></span>
    <span class="team-directory-names"><strong>Algeria</strong><small>FBA</small></span>
    <span class="team-directory-group">Group A</span>
  </a>
  <a class="team-directory-card" href="/teams/42-netherlands">
    <span class="team-directory-names"><strong>Netherlands</strong><small>FST</small></span>
    <span class="team-directory-group">Group A</span>
  </a>
</div>
"""


def test_parse_teams_extracts_directory_fields():
    teams = parse_teams(HTML)
    assert len(teams) == 2
    algeria = teams[0]
    assert algeria.id == "38" and algeria.slug == "algeria"
    assert algeria.country == "Algeria" and algeria.faculty == "FBA"
    assert algeria.group == "A"
    assert algeria.profile_url == "/teams/38-algeria"
    assert algeria.flag_url == "/assets/flags/w40/dz.png"
    assert algeria.team_name is None and algeria.captain is None
    assert teams[1].flag_url is None   # missing flag -> None, no crash
