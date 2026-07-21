from scraper.models import Team
from scraper.parsers.profile import parse_profile

STUB = Team(id="42", slug="netherlands", profile_url="/teams/42-netherlands",
            flag_url="/f/nl.png", country="Netherlands", team_name=None,
            faculty="FST", group="A", captain=None)

HTML = """
<div class="profile-identity">
  <div><h1>Netherlands</h1>
    <div class="profile-meta">
      <span class="profile-team-name">Team · CS BACKBENCHER</span>
      <span>Group A</span><span>FST</span>
    </div>
  </div>
</div>
<a class="profile-captain-feature" href="/players/657-zarif-arian">
  <span class="profile-captain-copy"><em>Captain</em><strong>Zarif Arian</strong><span>#1</span></span>
</a>
<a class="profile-player profile-player-captain " href="/players/657-zarif-arian">
  <span class="profile-player-photo"><img src="/img/a.png"><b>01</b></span>
  <div><strong>Zarif Arian</strong><small>Player</small>
       <span class="roster-captain-mark"><b>C</b> Team captain</span></div>
  <div class="player-totals"><span><b>0</b> goals</span><span><b>0</b> assists</span><span><b>0</b> cards</span></div>
</a>
<a class="profile-player  " href="/players/658-rezuwanul-haque-rezu">
  <span class="profile-player-photo"><img src="/img/b.jpeg"><b>02</b></span>
  <div><strong>Rezuwanul Haque</strong><small>Player</small></div>
  <div class="player-totals"><span><b>1</b> goals</span><span><b>2</b> assists</span><span><b>3</b> cards</span></div>
</a>
"""


def test_profile_extracts_real_name_captain_and_roster():
    team, roster = parse_profile(HTML, STUB)
    assert team.country == "Netherlands"
    assert team.team_name == "CS BACKBENCHER"          # "Team · " prefix stripped
    assert team.captain.player_id == "657" and team.captain.name == "Zarif Arian"
    assert roster.team_id == "42" and roster.team_name == "CS BACKBENCHER"
    assert len(roster.players) == 2
    cap, other = roster.players
    assert cap.is_captain is True and cap.jersey_number == "01"
    assert other.is_captain is False
    assert (other.goals, other.assists, other.cards) == (1, 2, 3)
    assert other.player_id == "658"
