from dataclasses import replace
from unittest.mock import Mock
import pandas as pd
import pytest
from risk_catalog import BY_ID, INDICATORS, DOMAINS
from risk_data import RiskDataService, assess, transform_frame, clean_frame


def frame(sid, dates, values):
    return pd.DataFrame({'date': dates, sid: values})


def test_catalog_is_unique_and_bounded():
    assert 75 <= len(INDICATORS) <= 125
    assert len(BY_ID) == len(INDICATORS)
    assert {i.domain for i in INDICATORS} == set(DOMAINS)
    assert not {'TEDRATE', 'MICH', 'FRBKCLMCILA'} & BY_ID.keys()
    for i in INDICATORS:
        assert i.raw_unit and i.source_url.startswith('https://')
        assert i.frequency in {'daily', 'weekly', 'monthly', 'quarterly'}
        assert i.transform in {'level', 'yoy'}


def test_mapping_meaning():
    assert 'All bank loan' in BY_ID['DRALACBS'].name
    assert 'four-week' in BY_ID['IC4WSA'].name
    assert 'option-adjusted' in BY_ID['BAMLC0A0CM'].name
    assert BY_ID['T10Y2Y'].unit == 'percentage points'


@pytest.mark.parametrize('sid,age,status', [('DGS10',10,'fresh'),('DGS10',11,'stale'),('IC4WSA',21,'fresh'),('IC4WSA',22,'stale'),('UNRATE',100,'fresh'),('UNRATE',101,'stale'),('DRALACBS',210,'fresh'),('DRALACBS',211,'stale')])
def test_frequency_specific_freshness(sid, age, status):
    now = pd.Timestamp('2026-10-08')
    result = assess(frame(sid,[now-pd.Timedelta(days=age)],[2]), BY_ID[sid], now)
    assert result.status == status
    if status == 'stale':
        assert result.watch == 'Unavailable'


@pytest.mark.parametrize('values', [[None], ['.'], [float('inf')], ['bad']])
def test_unusable_is_missing_not_neutral(values):
    result = assess(frame('VIXCLS',['2026-10-07'],values), BY_ID['VIXCLS'],'2026-10-08')
    assert result.status == 'missing'
    assert result.value is None
    assert result.watch == 'Unavailable'


def test_future_observation_is_invalid():
    result = assess(frame('VIXCLS',['2026-10-09'],[10]), BY_ID['VIXCLS'],'2026-10-08')
    assert result.status == 'invalid'
    assert result.value is None


@pytest.mark.parametrize('value,watch', [(29,'Not triggered'),(30,'Not triggered'),(31,'Watch')])
def test_watch_threshold(value, watch):
    result = assess(frame('VIXCLS',['2026-10-07'],[value]), BY_ID['VIXCLS'],'2026-10-08')
    assert result.watch == watch


def test_stale_watch_cannot_trigger():
    result = assess(frame('VIXCLS',['2020-01-01'],[80]), BY_ID['VIXCLS'],'2026-10-08')
    assert result.watch == 'Unavailable'


def test_zero_is_valid():
    result = assess(frame('T10Y2Y',['2026-10-07'],[0]), BY_ID['T10Y2Y'],'2026-10-08')
    assert result.value == 0
    assert result.status == 'fresh'


def test_yoy_leap_day_and_daily_holiday_tolerance():
    values = frame('SP500',['2023-02-28','2024-02-29'],[100,110])
    assert transform_frame(values,BY_ID['SP500']).iloc[-1]['SP500'] == pytest.approx(10)
    values = frame('SP500',['2025-10-03','2026-10-05'],[100,110])
    assert transform_frame(values,BY_ID['SP500']).iloc[-1]['SP500'] == pytest.approx(10)


@pytest.mark.parametrize('prior_date,prior', [('2025-08-01',100),('2025-09-01',0),('2025-09-01',-1)])
def test_yoy_missing_or_invalid_base(prior_date, prior):
    values = frame('CPIAUCSL',[prior_date,'2026-09-01'],[prior,110])
    result = assess(values,BY_ID['CPIAUCSL'],'2026-10-08')
    assert result.status == 'insufficient history'
    assert result.value is None


def test_quarterly_yoy():
    values = frame('USSTHPI',['2025-04-01','2026-04-01'],[200,210])
    assert transform_frame(values,BY_ID['USSTHPI']).iloc[-1]['USSTHPI'] == pytest.approx(5)


def test_no_old_transformed_value_substituted_for_missing_latest_base():
    values = frame('CPIAUCSL',['2025-08-01','2026-08-01','2026-09-01'],[100,105,106])
    assert assess(values,BY_ID['CPIAUCSL'],'2026-10-08').value is None


def test_clean_orders_deduplicates_and_discards_bad_dates():
    values = frame('DGS10',['2026-10-07','bad','2026-10-06','2026-10-07'],[1,4,2,3])
    assert clean_frame(values,'DGS10')['DGS10'].tolist() == [2,3]


def test_service_requests_extra_prior_year():
    client = Mock()
    client.get_series.return_value = pd.DataFrame()
    RiskDataService(fred=client).fetch(BY_ID['SP500'],365,'2026-10-08')
    assert pd.Timestamp(client.get_series.call_args.kwargs['start_date']) < pd.Timestamp('2024-10-08')


def test_eia_routed_to_eia_with_requested_history():
    fred, eia = Mock(), Mock()
    eia.get_series.return_value = pd.DataFrame()
    RiskDataService(fred=fred,eia=eia).fetch(BY_ID['ELEC.PRICE.US-RES.M'],7300,'2026-10-08')
    assert eia.get_series.call_args.kwargs['days'] == 7300
    fred.get_series.assert_not_called()


def test_api_revisions_override_archive_and_history_preserved():
    archive, fred = Mock(), Mock()
    archive.get_fred_series.return_value = frame('DGS10',['2026-10-01','2026-10-06'],[2,3])
    fred.get_series.return_value = frame('DGS10',['2026-10-06','2026-10-07'],[4,5])
    result = RiskDataService(fred=fred,archive=archive).fetch(BY_ID['DGS10'],30,'2026-10-08')
    assert result.frame['DGS10'].tolist() == [2,4,5]
    assert result.provenance == 'FRED API + S3 history'


def test_failed_api_can_use_stale_archive_but_not_signal():
    archive, fred = Mock(), Mock()
    archive.get_fred_series.return_value = frame('VIXCLS',['2026-09-01'],[50])
    fred.get_series.side_effect = RuntimeError('api_key=secret')
    result = RiskDataService(fred=fred,archive=archive).fetch(BY_ID['VIXCLS'],365,'2026-10-08')
    assert result.provenance == 'S3 archive'
    assert 'secret' not in result.error
    assert assess(result.frame,BY_ID['VIXCLS'],'2026-10-08').watch == 'Unavailable'


def test_api_failure_without_archive_remains_missing():
    fred = Mock()
    fred.get_series.side_effect = RuntimeError('offline')
    result = RiskDataService(fred=fred).fetch(BY_ID['DGS10'],365,'2026-10-08')
    assert result.frame.empty
    assert result.provenance == 'Unavailable'


def test_config_defaults_without_aws(monkeypatch):
    import config
    monkeypatch.setattr(config,'DATA_SOURCE_MODE','api')
    from s3_reader import HybridDataManager
    manager = HybridDataManager()
    assert manager.s3_reader is None
