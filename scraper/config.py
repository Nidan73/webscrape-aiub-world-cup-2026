"""Static configuration for the scraper."""

BASE_URL = "https://ofsportsaiub.org"

# Logical entity name -> tab-api.php `tab` value.
TABS = {
    "teams": "teams",
    "fixtures": "fixtures",
    "standings": "groups",
    "scorers": "scorers",
    "bracket": "bracket",
}

USER_AGENT = (
    "aiub-worldcup-scraper/1.0 (personal tournament dataset; "
    "contact: idublinfourir@gmail.com)"
)

DEFAULT_DELAY = 0.5          # seconds between requests
DEFAULT_TIMEOUT = 20         # seconds
DEFAULT_RETRIES = 3

# Files written under data/latest/
ENTITY_FILES = ("teams", "rosters", "fixtures", "standings", "scorers", "bracket")
