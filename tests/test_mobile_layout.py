"""Keep compact controls and readable summaries tied to the selected data."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


def test_compact_stress_picker_stays_in_sync_with_buttons_and_year_details():
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params['view'] = 'Portfolio Stress Lab'
    app.run()
    app.selectbox(key='portfolio:picker').set_value('Volcker tightening · 1980–1982').run()
    assert not app.exception
    assert any(m.value == '### Volcker tightening · 1980–1982' for m in app.markdown)
    app.selectbox(key='portfolio:annual:Volcker tightening · 1980–1982').set_value(1981).run()
    assert any('**December 31, 1981**' in m.value and 'Annual return: **+1.0%**' in m.value for m in app.markdown)
    next(b for b in app.button if b.label == 'Pandemic · 2020').click().run()
    assert not app.exception
    assert app.selectbox(key='portfolio:picker').value == 'Pandemic · 2020'
    assert any('**December 31, 2020**' in m.value for m in app.markdown)


def test_compact_regime_picker_updates_selected_case():
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params['view'] = 'Market history'
    app.run()
    picker = app.selectbox(key='history:picker')
    keys = list(picker.options)
    assert len(keys) == 12
    # The session-state value is the stable regime ID, not its display label.
    from market_history_catalog import REGIMES
    chosen = next(r for r in REGIMES if r.id != app.session_state.history_regime)
    picker.set_value(chosen.id).run()
    assert not app.exception
    assert app.session_state.history_regime == chosen.id
    assert any(m.value == '### ' + chosen.title for m in app.markdown)


def test_latest_component_summary_preserves_missingness_and_full_history():
    def sample():
        import pandas as pd
        from macro_pages import heatmap
        frame = pd.DataFrame({'Housing': [1., 2.], 'Energy': [3., float('nan')]},
                             index=pd.to_datetime(['2020-01-01', '2020-02-01']))
        heatmap(frame, 'Test components', periods=None, transpose=False)
    app = AppTest.from_function(sample).run()
    assert not app.exception
    latest, history = [table.value for table in app.dataframe]
    assert latest.columns.tolist() == ['Feb 2020']
    assert latest.loc['Housing'].iloc[0] == 2.
    assert latest.loc['Energy'].isna().all()
    assert history.index.tolist() == ['Feb 2020', 'Jan 2020']
