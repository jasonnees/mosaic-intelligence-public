"""Portfolio Stress Lab: observable historical outcomes for a chosen allocation."""
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from portfolio_stress import ASSETS, SCENARIOS, load_history, simulate
from market_history_page import style as history_style

def style(fig, height):
    history_style(fig, height)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-.25, x=0), margin=dict(l=25, r=25, t=45, b=100))
    return fig

COLORS = {'stocks': '#48dff5', 'treasuries': '#a9a1ff', 'cash': '#ffbd69'}

def render_portfolio():
    st.subheader('Portfolio Stress Lab')
    st.write('See how an illustrative stock, Treasury and cash allocation weathered past stresses. Change the weights to see what cushioned losses and what amplified them.')
    try:
        data, metadata = load_history()
    except (OSError, ValueError, KeyError):
        st.error('Historical portfolio data is unavailable or incomplete. No stress result can be calculated.')
        return
    st.caption(f'Annual history: {data.index.min()}–{data.index.max()} · Snapshot updated {metadata["source_updated"]} · No live market prices')
    st.info('Annual observations can hide severe losses within a year. Drawdowns and recovery dates below use year-end values only; they are not daily peak-to-trough losses.')
    with st.expander('Your illustrative allocation', expanded=True):
        columns = st.columns(3)
        weights = {a: col.number_input(label + ' (%)', min_value=0.0, max_value=100.0, value=default, step=5.0, key=f'portfolio:{a}')
                   for (a, label), col, default in zip(ASSETS.items(), columns, [60.0, 30.0, 10.0])}
        st.caption(f'Allocation total: {sum(weights.values()):g}% · Starting mix is an example, not a recommendation.')
        balance = st.number_input('Starting portfolio ($)', min_value=100.0, value=100000.0, step=10000.0)
        real = st.toggle('Adjust for inflation', value=False)
    if abs(sum(weights.values()) - 100) > 1e-8:
        st.warning('Set allocation weights to exactly 100% to calculate results.')
        return
    if 'portfolio:scenario' not in st.session_state:
        st.session_state['portfolio:scenario'] = 'Inflation & rate shock · 2022'
    st.markdown('#### Choose a historical stress')
    buttons = st.columns(3)
    for i, label in enumerate(SCENARIOS):
        if buttons[i % 3].button(label, key=f'choose:{label}', use_container_width=True,
                                  type='primary' if st.session_state['portfolio:scenario'] == label else 'secondary'):
            st.session_state['portfolio:scenario'] = label
            st.rerun()
    label = st.session_state['portfolio:scenario']
    start, end, context = SCENARIOS[label]
    st.markdown(f'### {label}')
    st.write(context)
    basis = 'Inflation-adjusted' if real else 'Nominal'
    st.caption(f'{basis} dollars · Reset to your allocation at the start of every calendar year · Income reinvested · No withdrawals, fees or taxes')
    try:
        result = simulate(data, weights, start, end, balance, real)
    except ValueError as error:
        st.error(str(error))
        return
    cols = st.columns(3)
    cols[0].metric('Return over stress years', f'{result["period_return"]:+.1%}', help=f'January {start} through December {end}.')
    cols[1].metric('Worst year-end drawdown', f'{result["drawdown"]:.1%}', help='Decline from a prior year-end high, including the starting balance. Intra-year losses are not measured.')
    if result['drawdown'] >= -1e-12:
        recovery_text = 'No year-end loss'
    elif result['recovery'] is None:
        recovery_text = f'Not by {data.index.max()}'
    else:
        recovery_text = f'{result["recovery"]} ({result["recovery"] - result["peak"]} years)'
    cols[2].metric('Recovery to prior year-end high', recovery_text,
                   help=f'Measured from the {result["peak"]} high before the worst stress-period year-end drawdown. Recovery may be after the stress years.')
    st.write(rf'Ending value: **\${balance * (1 + result["period_return"]):,.0f}** from \${balance:,.0f}. Worst calendar-year return during this stress: **{result["worst_year"]:+.1%}**.')
    display_end = max(end, result['recovery'] or end)
    path = result['wealth'].loc[:display_end]
    fig = go.Figure(go.Scatter(x=[f'{y}-12-31' for y in path.index], y=path.values, mode='lines+markers', name='Your allocation', line={'color': '#48dff5', 'width': 3}))
    tick_years = list(path.index[::max(1, (len(path) + 7) // 8)])
    if path.index[-1] not in tick_years:
        tick_years.append(path.index[-1])
    fig.update_xaxes(tickmode='array', tickvals=[f'{y}-12-31' for y in tick_years], ticktext=[str(y) for y in tick_years])
    fig.add_hline(y=balance, line_dash='dot', line_color='#ffbd69', annotation_text='Starting balance')
    fig.add_vrect(x0=f'{start}-01-01', x1=f'{end}-12-31', fillcolor='#ff839b', opacity=.1, line_width=0)
    fig.update_layout(title=f'{basis} portfolio value at year ends', yaxis_title='Dollars', xaxis_title='Year end', xaxis_type='date')
    st.plotly_chart(style(fig, 350), use_container_width=True)
    if result['recovery'] is None and result['drawdown'] < -1e-12:
        st.caption(f'No recovery through {data.index.max()}; chart shows the selected stress years. Full follow-up is included in the download.')
    st.markdown('#### What drove each year’s return?')
    st.caption('Contributions are percentage points of nominal annual portfolio return. Inflation is applied to the combined portfolio separately.')
    contributions = result['contributions'].loc[start:end]
    fig = go.Figure()
    for asset, title in ASSETS.items():
        fig.add_bar(x=contributions.index.astype(str), y=100 * contributions[asset], name=title, marker_color=COLORS[asset])
    fig.add_scatter(x=contributions.index.astype(str), y=100 * contributions.sum(axis=1), name='Portfolio return', mode='lines+markers', line={'color': 'white'})
    fig.update_layout(barmode='relative', yaxis_title='Percentage points', xaxis_title='Calendar year')
    st.plotly_chart(style(fig, 390), use_container_width=True)
    st.markdown('#### Compare the same allocation across stresses')
    rows = []
    for name, (first, last, _) in SCENARIOS.items():
        trial = simulate(data, weights, first, last, balance, real)
        rows.append({'Stress': name, 'Period return (%)': 100 * trial['period_return'], 'Worst year-end drawdown (%)': 100 * trial['drawdown'], 'Ending value ($)': balance * (1 + trial['period_return'])})
    st.dataframe(pd.DataFrame(rows).round(2), hide_index=True, use_container_width=True)
    export = result['contributions'].rename(columns={a: a + '_contribution_decimal' for a in ASSETS}).copy()
    export['portfolio_return_decimal'] = result['returns']
    export['year_end_value'] = result['wealth']
    export['basis'] = basis
    export['stress_start'] = start
    export['stress_end'] = end
    export['starting_balance'] = balance
    for a, w in weights.items():
        export[a + '_weight_percent'] = w
    st.download_button('Download scenario and recovery history', export.to_csv(index_label='year'), 'portfolio-stress.csv', 'text/csv')
    with st.expander('Asset exposures, sources & calculation method'):
        st.markdown('**Stocks:** large-cap US equity exposure, including dividends. History before 1957 uses predecessor indexes. **Treasuries:** a modeled constant-maturity 10-year bond with coupon income and price changes; rising yields can cause losses. **Cash:** average 3-month Treasury bill rates, an approximation of annual cash earnings. These are research proxies, not specific funds or your holdings.')
        st.write('At each year’s start, each asset receives its chosen weight. Annual portfolio return is the sum of weight × asset return; wealth compounds those annual returns. Inflation-adjusted wealth divides by compounded annual CPI changes. Recovery is the first later year end that regains the high preceding the worst year-end drawdown within the stress window. It is not necessarily sustained.')
        st.markdown(f'[Aswath Damodaran, NYU Stern: historical returns]({metadata["source_notes"]}) · [Source workbook and definitions]({metadata["source_url"]})')
        st.caption(f'Retrieved {metadata["retrieved_utc"]}. CPI is December-over-December, not annual-average inflation. Foreign stocks, TIPS, other bond maturities, credit, real estate and individual securities are not modeled. These historical scenarios do not establish future outcomes or a suitable allocation.')
        st.download_button('Download annual source returns', data.to_csv(), 'historical-asset-returns.csv', 'text/csv')
        st.download_button('Download source manifest', json.dumps(metadata, indent=2), 'portfolio-source-manifest.json', 'application/json')
