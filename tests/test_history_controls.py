"""Cross-section acceptance checks for cache serialization and time-window controls."""
import io
import json
import pickle
from dataclasses import make_dataclass
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from history_window import HISTORY_OPTIONS, history_start, clip_history
from risk_catalog import DOMAINS, BY_ID, INDICATORS
from risk_data import FetchResult, RiskDataService
from macro_components import MacroData, CPI_GROUPS, CPI_DETAIL, GDP_ROWS

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


def test_calendar_years_leap_day_and_all_available():
    assert history_start(365, '2024-02-29T23:00:00Z') == pd.Timestamp('2023-02-28')
    assert history_start(1825, '2026-10-23') == pd.Timestamp('2021-10-23')
    assert history_start(3650, '2026-10-23') == pd.Timestamp('2016-10-23')
    assert history_start(7300, '2026-10-23') == pd.Timestamp('2006-10-23')
    frame = pd.DataFrame({'value': [1, 2, 3]}, index=pd.to_datetime(['1900-01-01','2026-10-23','2026-10-24']))
    assert clip_history(frame, 0, now='2026-10-23').value.tolist() == [1, 2]
    assert clip_history(frame, 365, now='2026-10-23').value.tolist() == [2]


def test_indicator_cache_survives_result_class_replacement(monkeypatch):
    import risk_data
    import app_cache
    app_cache.fetch.clear()
    old = FetchResult(pd.DataFrame({'date': pd.to_datetime(['2026-10-01']), 'DGS10': [4.]}), 'fixture', 'now')
    # Reproduce the PicklingError that a stale class identity causes on reload.
    replacement = make_dataclass('FetchResult', ['frame','provenance','fetched_at','error'])
    monkeypatch.setattr(risk_data, 'FetchResult', replacement)
    with pytest.raises(pickle.PicklingError):
        pickle.dumps(old)
    with patch.object(RiskDataService, 'fetch', return_value=old) as source:
        first = app_cache.fetch('DGS10', 730)
        first.frame.iloc[0, 1] = -999  # Session copy cannot mutate another cache read.
        second = app_cache.fetch('DGS10', 730)
        assert second.frame.iloc[0, 1] == 4
        assert source.call_count == 1
        app_cache.fetch('DGS10', 7300)
        assert source.call_count == 2
    app_cache.fetch.clear()


@pytest.mark.parametrize('kind', ['cpi','gdp','history'])
def test_other_cached_pages_store_plain_payloads_on_cold_and_warm_reads(kind, monkeypatch):
    import macro_components
    import macro_pages
    import market_history_data
    import market_history_page
    if kind == 'history':
        old = market_history_data.load_history()
        module, name = market_history_data, 'HistoryData'
        fields = ['market','macro','vintages','manifest']
        cached, wrapper = market_history_page.snapshot_payload, market_history_page.snapshot
        patch_target = 'market_history_page.load_history'
    else:
        old = MacroData(pd.DataFrame({'a': [1.]}), source='fixture')
        module, name = macro_components, 'MacroData'
        fields = ['frame','errors','retrieved','source']
        cached = macro_pages.cpi_payload if kind == 'cpi' else macro_pages.gdp_payload
        wrapper = macro_pages.load_cpi if kind == 'cpi' else macro_pages.load_gdp
        patch_target = 'macro_pages.fetch_' + kind
    cached.clear()
    monkeypatch.setattr(module, name, make_dataclass(name, fields))
    with pytest.raises(pickle.PicklingError):
        pickle.dumps(old)
    with patch(patch_target, return_value=old) as source:
        wrapper()
        wrapper()
        assert source.call_count == 1
    cached.clear()


def test_all_indicator_sources_request_selected_window_and_yoy_buffer():
    from unittest.mock import Mock
    for indicator in INDICATORS:
        for days in HISTORY_OPTIONS:
            fred, eia = Mock(), Mock()
            fred.get_series.return_value = eia.get_series.return_value = pd.DataFrame()
            result = RiskDataService(fred=fred, eia=eia).fetch(indicator, days, '2026-10-23T12:00:00Z')
            assert result.frame.empty
            start = history_start(days, '2026-10-23')
            if indicator.source == 'fred':
                requested = pd.Timestamp(fred.get_series.call_args.kwargs['start_date'])
                assert requested == start if days == 0 or indicator.transform == 'level' else requested < start - pd.DateOffset(years=1)
                eia.get_series.assert_not_called()
            else:
                assert eia.get_series.call_args.kwargs['days'] == (pd.Timestamp('2026-10-23') - start).days
                fred.get_series.assert_not_called()


def fixtures():
    dates = pd.date_range('1990-01-01', pd.Timestamp.now(tz='UTC').tz_localize(None).normalize(), freq='MS')
    cpi = pd.DataFrame({sid: 100 * 1.002 ** np.arange(len(dates)) for sid in {**CPI_GROUPS, **CPI_DETAIL}}, index=dates)
    gdp_dates = pd.date_range('1990-01-01', dates[-1], freq='QS')
    gdp = pd.DataFrame({line: np.ones(len(gdp_dates)) * .25 for line in GDP_ROWS}, index=gdp_dates)
    gdp[1] = 1.25
    def source(self, indicator, *args, **kwargs):
        return FetchResult(pd.DataFrame({'date': dates, indicator.series_id: 100 * 1.002 ** np.arange(len(dates))}), 'fixture', 'now')
    return cpi, gdp, source


def first_date(chart):
    spec = json.loads(chart.proto.spec)
    return min(pd.Timestamp(d) for trace in spec['data'] for d in trace.get('x', []))


def test_every_live_section_respects_all_six_windows_and_keeps_selection():
    cpi, gdp, source = fixtures()
    st.cache_data.clear()
    original = st.dataframe
    def select_first(*args, **kwargs):
        original(*args, **kwargs)
        return {'selection': {'rows': [0]}}
    with patch.object(RiskDataService, 'fetch', source), patch('macro_pages.load_cpi', return_value=MacroData(cpi)), patch('macro_pages.load_gdp', return_value=MacroData(gdp)), patch('streamlit.dataframe', side_effect=select_first), patch('streamlit.download_button', wraps=st.download_button) as downloads:
        app = AppTest.from_file(APP, default_timeout=30).run()
        views = ['Overview'] + [d[0] for d in DOMAINS.values()] + ['Data catalog','CPI & components','GDP & components']
        for view in views:
            app.sidebar.radio[0].set_value(view).run()
            assert not app.exception, view
            assert app.sidebar.selectbox[0].options == ['1 year','2 years','5 years','10 years','20 years','All available']
            for days in HISTORY_OPTIONS:
                downloads.reset_mock()
                app.sidebar.selectbox[0].set_value(days).run()
                assert not app.exception, (view, days)
                charts = app.get('plotly_chart')
                chart = charts[-1] if view == 'CPI & components' else charts[0]
                earliest = first_date(chart)
                if days:
                    cutoff = history_start(days)
                    assert cutoff <= earliest <= cutoff + pd.Timedelta(days=93), (view, days, earliest)
                else:
                    assert earliest.year <= 1991, (view, earliest)
                label = 'Download CPI inflation history' if view == 'CPI & components' else 'Download GDP contributions' if view == 'GDP & components' else 'Download selected indicator history'
                csv = next(call.args[1] for call in downloads.call_args_list if call.args[0] == label)
                exported = pd.read_csv(io.StringIO(csv))
                assert pd.to_datetime(exported.iloc[:, 0]).min() == earliest
                if view == 'GDP & components':
                    table = next(d.value for d in app.dataframe if 'Real GDP' in d.value.columns)
                    assert len(table) == len(exported)
                    assert table.index[-1] == f'{earliest.year} Q{earliest.quarter}'
                if view == 'CPI & components':
                    table = next(d.value for d in app.dataframe if 'Headline CPI' in d.value.columns)
                    assert len(table) == len(exported)
                    assert pd.to_datetime(table.index[-1], format='%b %Y') == earliest
            # Leaving the section does not reset All available.
            assert app.sidebar.selectbox[0].value == 0
        app.sidebar.selectbox[0].set_value(3650).run()
        for view in ['Market history','Portfolio Stress Lab','Overview']:
            app.sidebar.radio[0].set_value(view).run()
            assert not app.exception
            if view == 'Overview':
                assert app.sidebar.selectbox[0].value == 3650
            else:
                assert not app.sidebar.selectbox
        assert not [c for c in app.checkbox if c.label == 'Show all available GDP history']
    st.cache_data.clear()
