from unittest.mock import patch
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from macro_components import (CPI_GROUPS,CPI_DETAIL,GDP_ROWS,GDP_STACK,MacroData,
    cpi_effects,calendar_change,parse_gdp,contribution_chart)


def cpi_fixture():
    dates = pd.date_range('2024-12-01',periods=25,freq='MS')
    data = pd.DataFrame({series:100*1.01**np.arange(25) for series in {**CPI_GROUPS,**CPI_DETAIL}},index=dates)
    return data


def test_calendar_comparison_does_not_skip_missing_months():
    data = cpi_fixture().drop(pd.Timestamp('2025-12-01'))
    rates = calendar_change(data)
    assert rates.loc['2026-12-01'].isna().all()
    assert rates.loc['2025-12-01'].isna().all()


def test_monthly_and_yearly_effects_reconcile_and_expire():
    data = cpi_fixture()
    weights = {2024:{s:12.5 for s in CPI_GROUPS},2025:{s:12.5 for s in CPI_GROUPS}}
    monthly = cpi_effects(data,1,weights)
    assert monthly.index.min() == pd.Timestamp('2025-01-01')
    assert monthly.iloc[-1]['Headline CPI'] == pytest.approx(1)
    assert monthly.iloc[-1]['Unallocated difference'] == pytest.approx(0)
    annual = cpi_effects(data,12,weights)
    assert annual.index.min() == pd.Timestamp('2025-12-01')
    assert annual.iloc[-1]['Headline CPI'] == pytest.approx((1.01**12-1)*100)
    assert annual.iloc[-1]['Unallocated difference'] == pytest.approx(0,abs=1e-10)
    expired = cpi_effects(data,1,{2024:weights[2024]})
    assert expired.index.max() == pd.Timestamp('2025-12-01')


def test_weight_changes_use_each_year_and_gaps_withhold_stack():
    data = cpi_fixture()
    data.loc[:,'CPIFABNS'] = 100*1.02**np.arange(25)
    weights = {2024:{s:12.5 for s in CPI_GROUPS},2025:{s:10 if s=='CPIFABNS' else 90/7 for s in CPI_GROUPS}}
    effects = cpi_effects(data,1,weights)
    # January resets to the new dated basket, not last year's share.
    assert effects.loc['2026-01-01','Food & beverages'] == pytest.approx(.2)
    assert effects.loc['2025-01-01','Food & beverages'] == pytest.approx(.25)
    data.loc['2025-08-01','CPIAPPNS'] = np.nan
    missing = cpi_effects(data,12,weights)
    assert pd.Timestamp('2026-08-01') not in missing.index
    assert pd.Timestamp('2026-07-01') in missing.index
    data.loc['2025-12-01','CPIAPPNS'] = np.nan
    assert cpi_effects(data,12,weights).empty
    # Differences remain visible rather than forced into category weights.
    assert effects.iloc[-1]['Unallocated difference'] != pytest.approx(0)


def test_bea_import_sign_and_missing_values_preserved():
    rows = [{'LineNumber':str(n),'TimePeriod':period,'DataValue':str(value)}
            for period in ['2026Q1','2026Q2'] for n,value in [(1,3),(2,1.9),(8,.42),(14,1.05),(15,-.9),(19,-1.1),(22,.52)]]
    rows += [{'LineNumber':'13','TimePeriod':'2026Q2','DataValue':'---'}]
    frame = parse_gdp({'BEAAPI':{'Results':{'Data':rows}}})
    assert frame.iloc[-1][19] == -1.1
    assert pd.isna(frame.iloc[-1][13])
    assert frame.iloc[-1][list(GDP_STACK)].sum() == pytest.approx(2.99)
    fig = contribution_chart(frame.rename(columns={**GDP_STACK,1:'Real GDP'}),list(GDP_STACK.values()),'Real GDP','GDP','pp')
    assert fig.layout.barmode == 'relative'
    assert list(fig.data[3].y) == [-.9,-.9]
    assert fig.data[-1].line.color == '#ffffff'
    with pytest.raises(ValueError):
        parse_gdp({'BEAAPI':{'Results':{'Error':{'APIErrorDescription':'invalid key'}}}})


def test_component_pages_populated_and_missing():
    from tests.test_app import empty_fetch
    now = pd.Timestamp.now().to_period('M').to_timestamp()
    cpi = cpi_fixture()
    cpi = cpi.loc[cpi.index <= now]
    gdp_dates = pd.date_range('2024-01-01',periods=10,freq='QS')
    gdp = pd.DataFrame({n:[.25]*10 for n in GDP_ROWS},index=gdp_dates)
    gdp[1]=1.25
    path = str(Path(__file__).resolve().parents[1]/'app.py')
    with patch('risk_data.RiskDataService.fetch',empty_fetch), patch('macro_pages.load_cpi',return_value=MacroData(cpi)), patch('macro_pages.load_gdp',return_value=MacroData(gdp)):
        app = AppTest.from_file(path,default_timeout=30).run()
        for view in ['CPI & components','GDP & components']:
            app.sidebar.radio[0].set_value(view).run()
            assert not app.exception
            assert app.get('plotly_chart')
            assert app.dataframe
        app.sidebar.radio[0].set_value('CPI & components').run()
        next(r for r in app.radio if r.label=='Inflation comparison').set_value('1-month').run()
        assert not app.exception
    with patch('risk_data.RiskDataService.fetch',empty_fetch),patch('macro_pages.load_cpi',return_value=MacroData(errors=['CPI unavailable'])),patch('macro_pages.load_gdp',return_value=MacroData(errors=['BEA unavailable'])):
        app = AppTest.from_file(path,default_timeout=30).run()
        for view in ['CPI & components','GDP & components']:
            app.sidebar.radio[0].set_value(view).run()
            assert not app.exception
            assert not app.get('plotly_chart')
            assert app.warning


def test_gdp_works_with_only_fred_key_and_sanitizes_source_errors():
    from macro_components import fetch_gdp,GDP_FRED
    def fixture(self,series,**kwargs):
        if series == GDP_FRED[19]:
            raise RuntimeError('URL containing secret must not reach UI')
        return pd.DataFrame({'date':pd.to_datetime(['2026-01-01','2026-07-01']),series:[1.,2.]})
    with patch('config.BEA_API_KEY',''),patch('config.FRED_API_KEY','test-only'),patch('data_fetcher.FREDClient.get_series',fixture):
        result = fetch_gdp()
    assert result.source.startswith('BEA NIPA table 1.1.2 via FRED')
    assert len(result.frame) == 3
    assert result.frame.loc['2026-04-01'].isna().all()
    assert result.frame[19].isna().all()
    assert len(result.errors) == 1
    assert 'secret' not in str(result.errors)


def test_component_chart_and_table_default_to_entire_source_history():
    import json
    from tests.test_app import empty_fetch
    dates = pd.date_range('1913-01-01',pd.Timestamp.now().to_period('M').to_timestamp(),freq='MS')
    frame = pd.DataFrame({series:100*1.002**np.arange(len(dates)) for series in {**CPI_GROUPS,**CPI_DETAIL}},index=dates)
    frame.index.name = 'date'
    frame.loc['2025-10-01',:] = np.nan
    frame.loc[frame.index<'1957-01-01','CPILFENS'] = np.nan
    frame.loc[frame.index<'1960-01-01','CPIENGNS'] = np.nan
    path = str(Path(__file__).resolve().parents[1]/'app.py')
    with patch('risk_data.RiskDataService.fetch',empty_fetch),patch('macro_pages.load_cpi',return_value=MacroData(frame)):
        app = AppTest.from_file(path,default_timeout=30).run()
        # The sidebar stays on its short default; component history must not inherit it.
        assert app.sidebar.selectbox[0].value == 730
        app.sidebar.radio[0].set_value('CPI & components').run()
        assert not app.exception
        assert app.selectbox(key='cpi_component_history').value == 'All available'
        spec = json.loads(app.get('plotly_chart')[-1].proto.spec)
        headline = next(t for t in spec['data'] if t['name']=='Headline CPI')
        assert pd.Timestamp(headline['x'][0]) == pd.Timestamp('1914-01-01')
        assert spec['layout']['xaxis']['rangeslider']['visible']
        # An internal missing month must survive rendering; connectgaps=False
        # cannot help if the empty calendar row was removed before plotting.
        missing_position = next(i for i,date in enumerate(headline['x']) if pd.Timestamp(date)==pd.Timestamp('2025-10-01'))
        values = headline['y']
        if isinstance(values,dict):
            import base64
            values = np.frombuffer(base64.b64decode(values['bdata']),dtype=values['dtype'])
        assert pd.isna(values[missing_position])
        assert headline.get('connectgaps') is False
        full_tables = [d.value for d in app.dataframe if 'Headline CPI' in d.value.columns and len(d.value)>1000]
        assert len(full_tables)==1
        assert full_tables[0].index[-1]=='Jan 1914'
        # A later-starting component retains its own source boundary in the table.
        assert pd.isna(full_tables[0].loc['Jan 1914','Energy'])
        for label,days in [('5 years',1825),('10 years',3650),('20 years',7300)]:
            app.selectbox(key='cpi_component_history').set_value(label).run()
            assert not app.exception
            spec = json.loads(app.get('plotly_chart')[-1].proto.spec)
            headline = next(t for t in spec['data'] if t['name']=='Headline CPI')
            earliest = pd.Timestamp(headline['x'][0])
            cutoff = pd.Timestamp.now().normalize()-pd.Timedelta(days=days)
            assert cutoff <= earliest < cutoff+pd.Timedelta(days=32)
        app.selectbox(key='cpi_component_history').set_value('All available').run()
        spec = json.loads(app.get('plotly_chart')[-1].proto.spec)
        assert pd.Timestamp(next(t for t in spec['data'] if t['name']=='Headline CPI')['x'][0]) == pd.Timestamp('1914-01-01')


def test_cpi_fetch_preserves_long_and_differing_source_histories():
    from macro_components import fetch_cpi
    calls=[]
    def source(self,series,**kwargs):
        calls.append(kwargs.get('start_date'))
        start = '1913-01-01' if series=='CPIAUCNS' else '1960-01-01'
        return pd.DataFrame({'date':pd.to_datetime([start,'2026-09-01']),series:[100.,200.]})
    with patch('config.FRED_API_KEY','test-only'),patch('data_fetcher.FREDClient.get_series',source):
        data=fetch_cpi()
    assert not data.errors
    assert data.frame['CPIAUCNS'].first_valid_index()==pd.Timestamp('1913-01-01')
    assert data.frame['CPIENGNS'].first_valid_index()==pd.Timestamp('1960-01-01')
    assert len(calls)==len({**CPI_GROUPS,**CPI_DETAIL})
    assert all(date=='1913-01-01' for date in calls)
