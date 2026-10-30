import pytest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from allocation_comparison import compare_allocations, stress_matrix, PRESETS
from portfolio_stress import load_history

def test_verified_comparison_and_censored_recovery():
    data, _ = load_history()
    table, paths = compare_allocations(data, 1928, 2025)
    assert list(table.index) == list(PRESETS)
    assert paths.shape == (99, 9)
    assert table.loc['60/40','Annualized return (%)'] == pytest.approx(8.3419078)
    assert table.loc['60/40','Year-end drawdown (%)'] == pytest.approx(-40.0572018)
    assert table.loc['10/90','Recovery'] == 'Not by 2025'
    real, realpaths = compare_allocations(data, 1928, 2025, real=True)
    assert real.loc['60/40','Annualized return (%)'] == pytest.approx(5.1447975)
    assert realpaths.iloc[-1,0] == pytest.approx(paths.iloc[-1,0]/(1+data.inflation).prod())
    doubled, dp = compare_allocations(data, 1928, 2025, balance=200000)
    assert dp.iloc[-1,0] == pytest.approx(paths.iloc[-1,0]*2)
    matrix = stress_matrix(data)
    assert matrix.loc['60/40','Inflation & rate shock · 2022'] == pytest.approx(-17.95377217)

def test_comparison_controls():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30)
    app.query_params['view']='Portfolio Stress Lab'
    app.run()
    next(r for r in app.radio if r.label=='Explore your portfolio').set_value('Compare nine allocations').run()
    assert not app.exception
    assert len(app.get('plotly_chart'))==3
    assert app.metric[0].value=='8.34%'
    app.select_slider[0].set_value('10/90').run()
    assert not app.exception
    assert any('Not by 2025' in c.value for c in app.caption)
    app.toggle[0].set_value(True).run()
    assert not app.exception
    assert app.metric[0].value=='2.17%'
    app.slider[0].set_range(2022,2022).run()
    assert not app.exception
    assert not app.metric
