import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from market_history_catalog import REGIMES,BY_REGIME,SERIES
from market_history_data import HistoryData,load_history,indicator_history,slice_market,evidence_rows,archived_rows
from market_history_page import market_chart,export_evidence


def test_bundled_history_integrity_coverage_and_regimes():
    data=load_history()
    assert len(REGIMES)==12
    assert len(BY_REGIME)==len(REGIMES)
    assert set(data.macro.series_id)==set(SERIES)
    assert data.market.index.min()==pd.Timestamp('1926-07-01')
    assert data.market.index.max()==pd.Timestamp('2024-12-31')
    for regime in REGIMES:
        assert pd.Timestamp(regime.view_start)<pd.Timestamp(regime.start)<=pd.Timestamp(regime.end)<pd.Timestamp(regime.view_end)
        assert set(regime.indicators)<=set(SERIES)
        assert regime.source_url.startswith('https://')
        market=slice_market(data,regime)
        assert not market.empty
        assert market.index_100.iloc[0]==pytest.approx(100)
        # Independent daily recurrence from source returns; first displayed close is baseline.
        expected=100*(1+market.return_pct.iloc[1:]/100).prod()
        assert market.index_100.iloc[-1]==pytest.approx(expected,rel=1e-12)
        assert market.drawdown_pct.min()<=0
        rows=evidence_rows(data,regime)
        assert len(rows)==len(regime.indicators)
        assert rows['Before reference end'].dropna().map(pd.Timestamp).lt(pd.Timestamp(regime.start)).all()
        fig=market_chart(market,regime)
        assert len(fig.data)==2
        assert len(fig.layout.shapes)==2


def test_named_crises_match_prior_research_and_not_price_only_benchmarks():
    data=load_history()
    for ident,expected in [('depression',-84.0739947686),('gfc',-54.5655359339),('pandemic',-34.2162809349),('inflation2022',-25.5559428744)]:
        regime=BY_REGIME[ident]
        market=slice_market(data,regime)
        assert market.loc[regime.start:regime.end,'drawdown_pct'].min()==pytest.approx(expected,abs=1e-8)
    assert not {'SP500','VIXCLS','BAA','AAA','BAMLH0A0HYM2'} & set(data.macro.series_id)


def test_yoy_uses_exact_calendar_base_and_retains_missing_values():
    frame=pd.DataFrame({'date':pd.to_datetime(['2019-01-01','2020-01-01','2021-02-01']),
                        'series_id':['PERMIT']*3,'value':[100,120,150]})
    data=HistoryData(pd.DataFrame(),frame,pd.DataFrame(),{})
    values=indicator_history(data,'PERMIT')
    assert values.loc['2020-01-01','value']==pytest.approx(20)
    assert pd.isna(values.loc['2021-02-01','value'])
    data.macro.loc[0,'value']=0
    assert pd.isna(indicator_history(data,'PERMIT').loc['2020-01-01','value'])


def test_pre_stress_mode_scopes_market_macro_table_and_export():
    data=load_history()
    regime=BY_REGIME['gfc']
    market=slice_market(data,regime,True)
    rows=evidence_rows(data,regime,True)
    assert market.index.max()<pd.Timestamp(regime.start)
    assert rows[['Stress minimum','Stress maximum']].isna().all().all()
    permit=rows.loc[rows.Series=='PERMIT'].iloc[0]
    assert permit['Before reference date']=='2007-09-01'
    assert permit['Before reference end']=='2007-09-30'
    archives=archived_rows(data,regime)
    payload=export_evidence(data,regime,market,rows,archives,True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        meta=json.loads(archive.read('sources-and-scope.json'))
        assert meta['pre_stress_only']
        for file in ['market.csv','indicators.csv']:
            frame=pd.read_csv(archive.open(file),parse_dates=['date'])
            assert frame.date.max()<pd.Timestamp(regime.start)
        raw=pd.read_csv(archive.open('period-readings.csv'))
        assert raw['Stress maximum'].isna().all()
    assert not market_chart(market,regime,True).layout.shapes


def test_archives_remain_separate_and_missing_is_not_zero():
    data=load_history()
    assert archived_rows(data,BY_REGIME['depression']).empty
    archive=archived_rows(data,BY_REGIME['pandemic'])
    unemployment=archive.loc[archive.series_id=='UNRATE']
    row=unemployment.loc[unemployment['As of']=='2020-02-18'].iloc[0]
    assert row['Archived value']==pytest.approx(3.6)
    assert row['Reference period']=='2020-01-01'
    old=archived_rows(data,BY_REGIME['crash1987'])
    assert 'No usable archived observation' in set(old['Archive result'])
    assert old.loc[old['Archive result']!='Available','Archived value'].isna().all()
    # Early-case coverage is honest rather than backfilled from later series.
    rows=evidence_rows(data,BY_REGIME['depression'])
    assert rows.loc[rows.Series=='UNRATE','Before stress'].isna().all()


def test_corrupted_snapshot_is_rejected(tmp_path):
    from market_history_data import DATA_DIR
    manifest=json.loads((DATA_DIR/'manifest.json').read_text())
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    (tmp_path/'macro.csv.gz').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='integrity'):
        load_history(tmp_path)


def test_every_regime_button_renders_and_pre_stress_switches():
    from tests.test_app import empty_fetch
    with patch('risk_data.RiskDataService.fetch',empty_fetch):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
        app.sidebar.radio[0].set_value('Market history').run()
        assert not app.exception
        for regime in REGIMES:
            app.button(key='regime:'+regime.id).click().run()
            assert not app.exception,regime.id
            assert app.session_state['history_regime']==regime.id
            assert len(app.get('plotly_chart'))>=3
            assert any(regime.title in heading.value for heading in app.markdown)
        app.toggle(key='history_pre_only').set_value(True).run()
        assert not app.exception
        assert not app.metric
        assert app.dataframe[0].value['Stress maximum'].isna().all()


def test_missing_snapshot_shows_error_without_fake_charts():
    from tests.test_app import empty_fetch
    with patch('risk_data.RiskDataService.fetch',empty_fetch),patch('market_history_page.snapshot',side_effect=ValueError('bad data')):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
        app.sidebar.radio[0].set_value('Market history').run()
        assert not app.exception
        assert app.error
        assert not app.get('plotly_chart')
