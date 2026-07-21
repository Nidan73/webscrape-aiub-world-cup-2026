from dataclasses import asdict
from scraper.models import Team, Captain, Fixture, FixtureSide


def test_team_round_trips_to_dict():
    t = Team(id="42", slug="netherlands", profile_url="/teams/42-netherlands",
             flag_url="/f/nl.png", country="Netherlands", team_name="CS Backbencher",
             faculty="FST", group="A",
             captain=Captain(player_id="657", name="Zarif Arian", player_url="/players/657-x"))
    d = asdict(t)
    assert d["country"] == "Netherlands" and d["team_name"] == "CS Backbencher"
    assert d["captain"]["name"] == "Zarif Arian"


def test_fixture_defaults_unplayed():
    f = Fixture(match_id="1", slug="a-vs-b", match_url="/m/1", match_no=1, group="A",
                date="Jul 28", time="8:00 AM", datetime_iso=None,
                home=FixtureSide(country="Turkey/Turkiye", flag_code="tr"),
                away=FixtureSide(country="Netherlands", flag_code="nl"),
                home_score=None, away_score=None, status="scheduled", raw_score="VS")
    assert f.home.flag_code == "tr" and f.home_score is None
