from scraper.parsers.fixtures import parse_fixtures

HTML = """
<div class="fixture-board">
  <article class="fixture-row google-fixture" data-fixture-card
           data-fixture-search-text="turkey/turkiye netherlands">
    <a class="fixture-card-link" href="/matches/15968-turkey-turkiye-vs-netherlands"></a>
    <div class="fixture-card-head"><span>Group A</span><span>Jul 28, 8:00 AM</span></div>
    <div class="fixture-card-main">
      <div class="fixture-side home"><span class="fixture-team">
        <img class="flag-icon" src="/assets/flags/w40/tr.png"> Turkey/Turkiye</span></div>
      <strong class="fixture-score" data-live-fixture-score>VS</strong>
      <div class="fixture-side away"><span class="fixture-team">
        <img class="flag-icon" src="/assets/flags/w40/nl.png"> Netherlands</span></div>
    </div>
    <div class="fixture-card-foot"><span class="fixture-no">Match 1</span>
      <span class="fixture-status">Scheduled</span></div>
  </article>
  <article class="fixture-row google-fixture" data-fixture-card>
    <a class="fixture-card-link" href="/matches/15969-japan-vs-mexico"></a>
    <div class="fixture-card-head"><span>Group B</span><span>Jul 28, 10:00 AM</span></div>
    <div class="fixture-card-main">
      <div class="fixture-side home"><span class="fixture-team">
        <img class="flag-icon" src="/assets/flags/w40/jp.png"> Japan</span></div>
      <strong class="fixture-score" data-live-fixture-score>2:1</strong>
      <div class="fixture-side away"><span class="fixture-team">
        <img class="flag-icon" src="/assets/flags/w40/mx.png"> Mexico</span></div>
    </div>
    <div class="fixture-card-foot"><span class="fixture-no">Match 2</span>
      <span class="fixture-status">Full time</span></div>
  </article>
</div>
"""


def test_parse_fixtures_unplayed_and_played():
    fx = parse_fixtures(HTML)
    assert len(fx) == 2
    a = fx[0]
    assert a.match_id == "15968" and a.match_no == 1 and a.group == "A"
    assert a.date == "Jul 28" and a.time == "8:00 AM"
    assert a.home.country == "Turkey/Turkiye" and a.home.flag_code == "tr"
    assert a.away.country == "Netherlands" and a.away.flag_code == "nl"
    assert a.raw_score == "VS" and a.home_score is None and a.status == "scheduled"
    b = fx[1]
    assert b.home_score == 2 and b.away_score == 1 and b.status == "final"
