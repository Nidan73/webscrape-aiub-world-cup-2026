from scraper.parsers.standings import parse_standings

HTML = """
<div class="panel"><h3>Group A</h3>
  <table class="data-table">
    <thead><tr><th>Nation</th><th>P</th><th>Pts</th><th>GD</th><th>GF</th><th>FP</th></tr></thead>
    <tbody>
      <tr class="qualify"><td><a href="/teams/30-turkey-turkiye">Turkey/Turkiye</a></td>
        <td>2</td><td>6</td><td>3</td><td>4</td><td>0</td></tr>
      <tr class="qualify"><td><a href="/teams/42-netherlands">Netherlands</a></td>
        <td>2</td><td>3</td><td>0</td><td>2</td><td>1</td></tr>
      <tr><td><a href="/teams/99-foo">Foo</a></td>
        <td>2</td><td>0</td><td>-3</td><td>1</td><td>2</td></tr>
    </tbody>
  </table>
</div>
"""


def test_parse_standings():
    groups = parse_standings(HTML)
    assert len(groups) == 1
    g = groups[0]
    assert g.group == "A" and len(g.table) == 3
    top = g.table[0]
    assert top.position == 1 and top.country == "Turkey/Turkiye"
    assert top.team_id == "30" and top.played == 2 and top.points == 6
    assert top.goal_diff == 3 and top.goals_for == 4 and top.qualified is True
    assert g.table[2].qualified is False and g.table[2].goal_diff == -3
