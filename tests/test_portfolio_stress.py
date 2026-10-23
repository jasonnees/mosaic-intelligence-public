from pathlib import Path
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from portfolio_stress import ASSETS, DATA, SCENARIOS, load_history, simulate


def test_snapshot_coverage_and_known_stress_returns():
    data, manifest = load_history()
    assert data.index.tolist() == list(range(1928, 2026))
    assert manifest['frequency'] == 'calendar year'
    assert data.loc[2008, 'stocks'] == pytest.approx(-.3655234, abs=.000001)
    assert data.loc[2008, 'treasuries'] == pytest.approx(.201013, abs=.000001)
    assert data.loc[2022, 'stocks'] < -.17
    assert data.loc[2022, 'treasuries'] < -.17
    assert data.loc[2022, 'cash'] > 0
    # The source includes bond price losses; these are not yields.
    assert simulate(data, dict(stocks=0, treasuries=100, cash=0), 2022, 2022)['period_return'] < -.17
    for first, last, _ in SCENARIOS.values():
        result = simulate(data, dict(stocks=60, treasuries=30, cash=10), first, last)
        assert result['wealth'].notna().all()


def test_independent_rebalance_inflation_drawdown_and_recovery():
    data = pd.DataFrame({'stocks': [-.4, .5, .4], 'treasuries': [.2, -.1, .1], 'cash': [0., 0., 0.], 'inflation': [.1, .1, 0.]}, index=[2000, 2001, 2002])
    weights = dict(stocks=50, treasuries=50, cash=0)
    result = simulate(data, weights, 2000, 2000, 100)
    # Rebalance at each year start: 50*(-40%)+50*20%=-10%, then +20%, then +25%.
    assert result['wealth'].tolist() == pytest.approx([100, 90, 108, 135])
    assert result['drawdown'] == pytest.approx(-.1)
    assert result['trough'] == 2000 and result['peak'] == 1999 and result['recovery'] == 2001
    assert result['contributions'].sum(axis=1).tolist() == pytest.approx([-.1, .2, .25])
    real = simulate(data, weights, 2000, 2001, 100, True)
    assert real['wealth'].loc[2001] == pytest.approx(108 / 1.21)
    assert real['recovery'] == 2002
    assert real['period_return'] == pytest.approx(108 / 121 - 1)
    # Losses never recovered within available data are censored, not zero years.
    assert simulate(data.iloc[:1], weights, 2000, 2000)['recovery'] is None
    assert simulate(data, dict(stocks=0, treasuries=0, cash=100), 2000, 2001)['drawdown'] == 0


@pytest.mark.parametrize('weights', [dict(stocks=50, treasuries=30, cash=10), dict(stocks=-10, treasuries=100, cash=10), dict(stocks=float('nan'), treasuries=0, cash=0), dict(stocks=100)])
def test_invalid_allocations_rejected(weights):
    with pytest.raises(ValueError, match='Allocation'):
        simulate(load_history()[0], weights, 2022, 2022)


def test_missing_data_rejected_and_zero_weight_not_required(tmp_path):
    data = load_history()[0].loc[2022:].copy()
    data.loc[2023, 'stocks'] = float('nan')
    with pytest.raises(ValueError, match='Missing'):
        simulate(data, dict(stocks=60, treasuries=30, cash=10), 2022, 2022)
    assert simulate(data, dict(stocks=0, treasuries=0, cash=100), 2022, 2022)['wealth'].notna().all()
    with pytest.raises(ValueError):
        simulate(data.drop(index=2023), dict(stocks=0, treasuries=0, cash=100), 2022, 2022)
    (tmp_path / 'manifest.json').write_bytes((DATA / 'manifest.json').read_bytes())
    (tmp_path / 'returns.csv').write_bytes((DATA / 'returns.csv').read_bytes() + b'bad')
    with pytest.raises(ValueError, match='integrity'):
        load_history(tmp_path)


def test_lab_controls_scenarios_and_invalid_allocation():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30)
    app.query_params['view'] = 'Portfolio implications'  # Legacy URLs still resolve.
    app.run()
    assert not app.exception
    assert app.sidebar.radio[0].value == 'Portfolio Stress Lab'
    assert not app.sidebar.selectbox  # Scenario years are the only time filter.
    default = app.metric[0].value
    for name in SCENARIOS:
        next(b for b in app.button if b.label == name).click().run()
        assert not app.exception
        assert any(h.value == '### ' + name for h in app.markdown)
        assert len(app.get('plotly_chart')) == 2
    app.number_input(key='portfolio:stocks').set_value(100.)
    app.number_input(key='portfolio:treasuries').set_value(0.)
    app.number_input(key='portfolio:cash').set_value(0.).run()
    assert not app.exception and app.metric[0].value != default
    app.toggle[0].set_value(True).run()
    assert not app.exception
    assert any('Inflation-adjusted dollars' in c.value for c in app.caption)
    app.number_input(key='portfolio:cash').set_value(10.).run()
    assert not app.exception and not app.metric
    assert any('exactly 100%' in w.value for w in app.warning)
