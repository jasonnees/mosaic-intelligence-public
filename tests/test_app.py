from unittest.mock import patch
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest
from risk_data import FetchResult


def empty_fetch(self, indicator, *args, **kwargs):
    return FetchResult(pd.DataFrame(columns=['date',indicator.series_id]),'Unavailable','2026-10-08T00:00:00+00:00','Test: no data')


def test_navigation_missing_data_filters_and_catalog():
    with patch('risk_data.RiskDataService.fetch', empty_fetch):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'),default_timeout=30).run()
        assert not app.exception
        assert app.title[0].value == 'Market Risk Explorer'
        for view in ['Equity risk','Recession & growth risk','Inflation risk','Interest-rate risk','Credit stress','Housing conditions','Portfolio implications','Data catalog','Overview']:
            app.sidebar.radio[0].set_value(view).run()
            assert not app.exception, view
        next(r for r in app.radio if r.label == 'Filter observations').set_value('Needs attention').run()
        assert not app.exception
        assert any('0/' in metric.value for metric in app.metric)


def test_fresh_stale_and_watch_rendered_consistently():
    from datetime import datetime, timedelta
    import streamlit as st
    st.cache_data.clear()
    now = datetime.now()
    def fixture_fetch(self, indicator, *args, **kwargs):
        date = now - timedelta(days=500 if indicator.series_id == 'UNRATE' else 1)
        return FetchResult(pd.DataFrame({'date':[date],indicator.series_id:[40]}),'FRED API',now.isoformat())
    with patch('risk_data.RiskDataService.fetch', fixture_fetch):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'),default_timeout=30).run()
        assert not app.exception
        observations = app.dataframe[0].value
        assert observations.loc[observations.Series == 'VIXCLS','Watch condition'].iloc[0] == 'Watch'
        assert observations.loc[observations.Series == 'UNRATE','Data status'].iloc[0] == 'stale'
        assert observations.loc[observations.Series == 'SP500','Data status'].iloc[0] == 'insufficient history'
        next(r for r in app.radio if r.label == 'Filter observations').set_value('Watch').run()
        assert not app.exception
        assert set(app.dataframe[0].value['Watch condition']) == {'Watch'}
    st.cache_data.clear()


def test_every_catalog_row_opens_its_own_chart_and_only_fetches_that_series():
    import streamlit as st
    from risk_catalog import INDICATORS
    st.cache_data.clear()
    original_dataframe = st.dataframe
    selected_position = []
    def select_row(*args, **kwargs):
        original_dataframe(*args, **kwargs)
        return {'selection': {'rows': selected_position.copy()}}
    with patch('risk_data.RiskDataService.fetch', autospec=True, side_effect=empty_fetch) as fetcher, patch('streamlit.dataframe', side_effect=select_row):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'),default_timeout=30).run()
        app.sidebar.radio[0].set_value('Data catalog').run()
        fetcher.reset_mock()
        st.cache_data.clear()
        for position, indicator in enumerate(INDICATORS):
            selected_position[:] = [position]
            app.run()
            assert not app.exception, indicator.series_id
            assert indicator.name in [h.value for h in app.subheader]
            assert indicator.series_id in app.caption[-3].value or any(indicator.series_id in c.value for c in app.caption)
            assert fetcher.call_args.args[1].series_id == indicator.series_id
        assert fetcher.call_count == len(INDICATORS)
    st.cache_data.clear()


def test_filtered_row_positions_and_history_changes():
    import streamlit as st
    from datetime import datetime
    st.cache_data.clear()
    original_dataframe = st.dataframe
    position = [0]
    def select_row(*args, **kwargs):
        original_dataframe(*args, **kwargs)
        return {'selection': {'rows': position.copy()}}
    def fixture_fetch(self, indicator, *args, **kwargs):
        return FetchResult(pd.DataFrame({'date':[datetime.now()],indicator.series_id:[40]}),'FRED API','now')
    with patch('risk_data.RiskDataService.fetch', fixture_fetch), patch('streamlit.dataframe', side_effect=select_row):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'),default_timeout=30).run()
        next(r for r in app.radio if r.label == 'Filter observations').set_value('Watch').run()
        # First displayed row has original index 1; selecting it must show VIX, not SP500.
        assert app.dataframe[0].value.iloc[0]['Series'] == 'VIXCLS'
        assert 'CBOE equity volatility index' in [h.value for h in app.subheader]
        app.sidebar.selectbox[0].set_value(1825).run()
        assert 'CBOE equity volatility index' in [h.value for h in app.subheader]
        app.sidebar.radio[0].set_value('Housing conditions').run()
        assert not app.exception
        assert any('No indicators match' in info.value for info in app.info)
        assert not app.get('plotly_chart')
    st.cache_data.clear()


def test_all_indicators_render_populated_charts_with_specific_guidance():
    import streamlit as st
    from risk_catalog import INDICATORS
    from indicator_guidance import GUIDES
    st.cache_data.clear()
    original_dataframe = st.dataframe
    position = []
    def select_row(*args, **kwargs):
        original_dataframe(*args, **kwargs)
        return {'selection': {'rows': position.copy()}}
    def fixture_fetch(self, indicator, *args, **kwargs):
        dates = pd.date_range(end=pd.Timestamp.now(tz='UTC').tz_localize(None).normalize(), periods=1100)
        values = [100 + n / 20 for n in range(len(dates))]
        return FetchResult(pd.DataFrame({'date': dates, indicator.series_id: values}),
                           f'{indicator.source.upper()} API', 'fixture')
    with patch('risk_data.RiskDataService.fetch', fixture_fetch), patch('streamlit.dataframe', side_effect=select_row):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'),default_timeout=30).run()
        app.sidebar.radio[0].set_value('Data catalog').run()
        for index, indicator in enumerate(INDICATORS):
            position[:] = [index]
            app.run()
            assert not app.exception, indicator.series_id
            assert len(app.get('plotly_chart')) == 1, indicator.series_id
            assert any(GUIDES[indicator.series_id].caution in item.value for item in app.markdown), indicator.series_id
    st.cache_data.clear()
