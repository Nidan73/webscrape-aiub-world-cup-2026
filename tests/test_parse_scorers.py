from scraper.parsers.scorers import parse_scorers

EMPTY = '<div class="scorers-shell"><div class="scorers-empty"><h3>The race starts</h3></div></div>'

POPULATED = """
<div class="scorers-shell">
  <ol class="scorers-list">
    <li class="scorers-row"><a href="/players/658-rezu"><strong>Rezuwanul Haque</strong></a>
        <small>Netherlands</small><b>3</b></li>
  </ol>
</div>
"""


def test_scorers_empty_state_returns_empty_list():
    assert parse_scorers(EMPTY) == []


def test_scorers_populated_best_effort():
    rows = parse_scorers(POPULATED)
    assert len(rows) == 1
    assert rows[0].rank == 1 and rows[0].name == "Rezuwanul Haque"
    assert rows[0].goals == 3 and rows[0].player_id == "658"
