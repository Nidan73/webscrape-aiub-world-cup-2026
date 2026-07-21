from scraper.parsers.bracket import parse_bracket

HTML = """
<section class="knockout-stage stage-r32" data-bracket-stage>
  <header><span>R32</span><h3>Round of 32</h3></header>
  <article class="knockout-match" data-match-no="49" data-next-match="65">
    <a class="knockout-match-link" href="/matches/16016-home-vs-away"></a>
    <div class="match-meta"><a href="/matches/16016-home-vs-away">Match 49</a><span>R32</span></div>
    <div class="ko-team "><span>1st of Group A</span><b>-</b></div>
    <div class="ko-team "><span>2nd of Group I</span><b>-</b></div>
  </article>
</section>
<section class="knockout-stage stage-r16" data-bracket-stage>
  <header><span>R16</span><h3>Round of 16</h3></header>
  <article class="knockout-match" data-match-no="65" data-next-match="73">
    <div class="match-meta"><a href="/matches/16032-x">Match 65</a><span>R16</span></div>
    <div class="ko-team "><span>Winner of M49</span><b>-</b></div>
    <div class="ko-team "><span>Winner of M50</span><b>-</b></div>
  </article>
</section>
"""


def test_parse_bracket_tree_and_labels():
    stages = parse_bracket(HTML)
    assert [s.stage for s in stages] == ["R32", "R16"]
    m49 = stages[0].matches[0]
    assert m49.match_no == 49 and m49.next_match_no == 65
    assert m49.home_label == "1st of Group A" and m49.away_label == "2nd of Group I"
    assert m49.home_team is None and m49.away_team is None
    assert m49.match_url == "/matches/16016-home-vs-away"
    m65 = stages[1].matches[0]
    assert m65.home_label == "Winner of M49" and m65.next_match_no == 73
