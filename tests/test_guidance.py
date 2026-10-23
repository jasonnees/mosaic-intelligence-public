import pandas as pd
import pytest
from risk_catalog import INDICATORS, BY_ID, WATCH_RULES, RULE_SOURCES
from risk_data import assess
from indicator_guidance import GUIDES, direction, data_warning


def frame(sid, dates, values):
    return pd.DataFrame({'date': dates, sid: values})


def test_entire_active_catalog_has_distinct_series_guidance_and_rule_references():
    assert set(GUIDES) == {i.series_id for i in INDICATORS}
    assert set(WATCH_RULES) == set(RULE_SOURCES)
    assert len({guide.caution for guide in GUIDES.values()}) == len(GUIDES)
    assert 'non-directional' in GUIDES['VIXCLS'].caution
    assert 'Nominal' in GUIDES['PCE'].rising
    assert 'Slower positive inflation' in GUIDES['CPIAUCSL'].caution
    assert 'less tightening' in GUIDES['DRTSCILM'].caution


@pytest.mark.parametrize('sid,date,value,status', [
    ('VIXCLS','2020-01-01',90,'stale'),
    ('VIXCLS','2026-10-09',90,'invalid'),
    ('SP500','2026-10-07',90,'insufficient history'),
])
def test_bad_data_cannot_support_direction_or_market_clearance(sid,date,value,status):
    values = frame(sid,[date],[value])
    observation = assess(values,BY_ID[sid],'2026-10-08')
    movement = direction(values,BY_ID[sid],'2026-10-08')
    assert observation.status == status
    assert observation.watch == 'Unavailable'
    assert movement.label == 'Not evaluated'
    assert movement.change is None
    assert data_warning(observation,BY_ID[sid])


def test_missing_data_has_action_and_no_fallback():
    sid='DGS10'
    values=frame(sid,[],[])
    observation=assess(values,BY_ID[sid],'2026-10-08')
    assert direction(values,BY_ID[sid],'2026-10-08').label == 'Not evaluated'
    assert 'API key' in data_warning(observation,BY_ID[sid])


def test_direction_uses_displayed_growth_not_raw_price_level():
    # Prices rise, but growth falls from 20% to 10%; direction must be falling.
    sid='CPIAUCSL'
    values=frame(sid,['2025-06-01','2025-09-01','2026-06-01','2026-09-01'],[100,120,120,132])
    result=direction(values,BY_ID[sid],'2026-10-08')
    assert result.label == 'Falling'
    assert result.change == pytest.approx(-10)
    assert result.prior_date == '2026-06-01'
    assert 'slowed' in result.explanation


def test_quarterly_comparison_uses_a_year_and_actual_dates():
    sid='A191RL1Q225SBEA'
    values=frame(sid,['2025-07-01','2026-04-01','2026-07-01'],[1,5,2])
    result=direction(values,BY_ID[sid],'2026-10-08')
    assert result.label == 'Rising'
    assert result.change == 1
    assert result.prior_date == '2025-07-01'


def test_gappy_or_invalid_comparison_is_not_replaced_with_an_older_value():
    sid='DGS10'
    values=frame(sid,['2025-01-01','2026-10-07'],[2,4])
    assert direction(values,BY_ID[sid],'2026-10-08').label == 'No comparison'
    sid='CPIAUCSL'
    values=frame(sid,['2025-09-01','2026-06-01','2026-09-01'],[100,110,120])
    assert direction(values,BY_ID[sid],'2026-10-08').label == 'No comparison'


def test_curve_direction_and_current_threshold_are_independent():
    sid='T10Y2Y'
    values=frame(sid,['2026-07-07','2026-10-07'],[-1,-.2])
    assert direction(values,BY_ID[sid],'2026-10-08').label == 'Rising'
    assert assess(values,BY_ID[sid],'2026-10-08').watch == 'Watch'


@pytest.mark.parametrize('latest,watch', [(102,'Not triggered'),(102.1,'Watch')])
def test_pce_benchmark_uses_headline_yoy_and_strict_greater_than(latest,watch):
    values=frame('PCEPI',['2025-09-01','2026-09-01'],[100,latest])
    assert assess(values,BY_ID['PCEPI'],'2026-10-08').watch == watch
    assert 'PCEPILFE' not in WATCH_RULES


def test_no_rule_breach_is_not_an_all_clear():
    result=assess(frame('VIXCLS',['2026-10-07'],[15]),BY_ID['VIXCLS'],'2026-10-08')
    assert result.detail.startswith('No rule breach')
    assert 'not an all-clear' in result.detail
