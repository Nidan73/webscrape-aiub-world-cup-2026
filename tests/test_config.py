from scraper import config


def test_base_url_and_tabs():
    assert config.BASE_URL == "https://ofsportsaiub.org"
    assert config.TABS["standings"] == "groups"          # standings tab is served as tab=groups
    assert set(config.TABS) >= {"teams", "fixtures", "standings", "scorers", "bracket"}
    assert config.DEFAULT_DELAY > 0
    assert "teams" in config.ENTITY_FILES
