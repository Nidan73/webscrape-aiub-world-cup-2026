"""Write a minimal but complete data/latest set for dashboard tests."""
import json


def seed(dirpath):
    def w(name, obj):
        (dirpath / f"{name}.json").write_text(json.dumps(obj))

    w("teams", [
        {"id": "42", "slug": "netherlands", "flag_url": "/assets/flags/w40/nl.png",
         "country": "Netherlands", "team_name": "CS Backbencher", "faculty": "FST", "group": "A",
         "captain": {"player_id": "657", "name": "Zarif Arian", "player_url": "/players/657-x"}},
        {"id": "30", "slug": "turkey-turkiye", "flag_url": "/assets/flags/w40/tr.png",
         "country": "Turkey/Turkiye", "team_name": "CS Amigos", "faculty": "FST", "group": "A",
         "captain": None},
    ])
    w("rosters", [
        {"team_id": "42", "country": "Netherlands", "team_name": "CS Backbencher", "players": [
            {"player_id": "657", "jersey_number": "01", "name": "Zarif Arian", "role": "Player",
             "is_captain": True, "photo_url": "/assets/player_img/a.png", "goals": 0, "assists": 0, "cards": 0}]},
    ])
    w("fixtures", [
        {"match_id": "1", "match_no": 1, "group": "A", "date": "Jul 28", "time": "8:00 AM",
         "home": {"country": "Turkey/Turkiye", "flag_code": "tr"},
         "away": {"country": "Netherlands", "flag_code": "nl"},
         "home_score": None, "away_score": None, "status": "scheduled", "raw_score": "VS"},
    ])
    w("standings", [
        {"group": "A", "table": [
            {"position": 1, "team_id": "30", "country": "Turkey/Turkiye", "played": 0, "points": 0,
             "goal_diff": 0, "goals_for": 0, "fair_play": 0, "qualified": True},
            {"position": 2, "team_id": "42", "country": "Netherlands", "played": 0, "points": 0,
             "goal_diff": 0, "goals_for": 0, "fair_play": 0, "qualified": True}]},
    ])
    w("bracket", [
        {"stage": "R32", "matches": [
            {"match_no": 49, "next_match_no": 65, "home_label": "1st of Group A",
             "away_label": "2nd of Group I", "home_team": None, "away_team": None, "status": "scheduled"}]},
        {"stage": "Final", "matches": [
            {"match_no": 79, "next_match_no": None, "home_label": "Winner of M77",
             "away_label": "Winner of M78", "home_team": None, "away_team": None, "status": "scheduled"}]},
    ])
    w("scorers", [])
    w("projections", {
        "42": {"country": "Netherlands", "team_name": "CS Backbencher", "scenarios": {
            "group_winner": [
                {"round": "R32", "possible_opponents": [{"id": "99", "country": "Argentina", "team_name": "ECO Gladiators"}]},
                {"round": "Final", "possible_opponents": [{"id": "30", "country": "Turkey/Turkiye", "team_name": "CS Amigos"}]}],
            "runner_up": [
                {"round": "R32", "possible_opponents": [{"id": "99", "country": "Argentina", "team_name": "ECO Gladiators"}]}]}},
    })
    w("manifest", {"scraped_at": "2026-07-21T00-00-00Z", "source": "https://ofsportsaiub.org",
                   "entities": {"teams": {"count": 2, "ok": True, "error": None},
                                "fixtures": {"count": 1, "ok": True, "error": None}},
                   "snapshot_dir": "x"})
