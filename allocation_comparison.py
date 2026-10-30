"""Comparable, annually rebalanced stock/Treasury histories."""
import pandas as pd
from portfolio_stress import simulate, SCENARIOS

PRESETS = {f'{s}/{100-s}': dict(stocks=s, treasuries=100-s, cash=0) for s in range(90, 0, -10)}

def compare_allocations(data, start, end, balance=100_000, real=False):
    paths, rows = {}, []
    for label, weights in PRESETS.items():
        result = simulate(data, weights, start, end, balance, real)
        returns = result['returns'].loc[start:end]
        paths[label] = result['wealth'].loc[:end]
        recovery = ('No year-end decline' if result['trough'] is None else
                    f'Not by {data.index.max()}' if result['recovery'] is None else
                    f'{result["recovery"]} ({result["recovery"]-result["peak"]} years from peak)')
        rows.append({'Allocation': label, 'Annualized return (%)': 100*((result['ending_value']/balance)**(1/len(returns))-1),
                     'Annual volatility (%)': 100*returns.std(ddof=1),
                     'Worst year (%)': 100*result['worst_year'], 'Worst year': result['worst_year_date'],
                     'Year-end drawdown (%)': 100*result['drawdown'],
                     'Peak year': str(result['peak']) if result['peak'] is not None else '—',
                     'Trough year': str(result['trough']) if result['trough'] is not None else '—',
                     'Recovery': recovery, 'Ending value ($)': result['ending_value']})
    return pd.DataFrame(rows).set_index('Allocation'), pd.DataFrame(paths)

def stress_matrix(data, real=False):
    return pd.DataFrame({name: {label: 100*simulate(data, weights, start, end, real=real)['period_return']
                               for label, weights in PRESETS.items()}
                         for name, (start, end, _) in SCENARIOS.items()})

def render_comparison(data, metadata):
    import streamlit as st
    import plotly.graph_objects as go
    from portfolio_page import style
    from brand import readable_chart
    st.markdown('### One history. Nine ways to experience it.')
    st.write('Compare stock / 10-year Treasury mixes from 90/10 to 10/90. Select an allocation to highlight its path and see the trade-offs in dollars.')
    chosen = st.select_slider('Highlight an allocation · stocks / Treasuries', options=list(PRESETS), value='60/40')
    c1, c2 = st.columns(2)
    balance = c1.number_input('Comparison starting balance ($)', min_value=100., value=100000., step=10000.)
    real = c2.toggle('Show purchasing power after inflation', value=False)
    start, end = st.slider('Comparison years', min_value=int(data.index.min()), max_value=int(data.index.max()),
                           value=(int(data.index.min()), int(data.index.max())))
    if start == end:
        st.info('Select at least two calendar years to compare annual volatility.')
        return
    basis = 'Inflation-adjusted' if real else 'Nominal'
    table, paths = compare_allocations(data, start, end, balance, real)
    row = table.loc[chosen]
    st.caption(f'{basis} · {start}–{end} · Annual rebalancing · Dividends and interest reinvested · No withdrawals, taxes or fees')
    cols = st.columns(3)
    cols[0].metric(f'{chosen} annualized return', f'{row["Annualized return (%)"]:.2f}%')
    cols[1].metric('Ending portfolio value', f'${row["Ending value ($)"]:,.0f}')
    cols[2].metric('Largest year-end decline', f'{row["Year-end drawdown (%)"]:.1f}%')
    st.caption(f'Peak: {row["Peak year"]} · Trough: {row["Trough year"]} · Recovery: {row["Recovery"]}. Recovery follows the same allocation through {data.index.max()}, even when the selected window ends earlier.')
    log_scale = st.checkbox('Use a logarithmic wealth scale', value=True, help='Equal vertical distances represent equal percentage changes.')
    fig = go.Figure()
    palette = ['#48dff5','#61cfee','#79bfe7','#a9a1ff','#b8b4ed','#cad0cf','#cdddb4','#e6cf92','#ffbd69']
    for label, color in zip(PRESETS, palette):
        fig.add_scatter(x=paths.index, y=paths[label], name=label, mode='lines',
                        line=dict(color=color, width=4 if label==chosen else 1.5),
                        opacity=1 if label==chosen else .5,
                        hovertemplate='%{x}: $%{y:,.0f}<extra>'+label+'</extra>')
    fig.update_layout(title=f'{basis} wealth · starting with ${balance:,.0f}', xaxis_title='Year end', yaxis_title='Dollars', yaxis_type='log' if log_scale else 'linear')
    readable_chart(style(fig, 420))
    dd = 100*(paths[chosen]/paths[chosen].cummax()-1)
    fig = go.Figure(go.Scatter(x=dd.index, y=dd, fill='tozeroy', line=dict(color='#ff839b'), name=chosen,
                              hovertemplate='%{x}: %{y:.1f}%<extra></extra>'))
    fig.update_layout(title=f'{chosen} · distance below its prior year-end high', yaxis_title='Drawdown (%)', xaxis_title='Year end')
    readable_chart(style(fig, 270))
    st.markdown('#### Compare all nine allocations')
    st.dataframe(table.round(2), use_container_width=True)
    st.caption('Volatility is the sample standard deviation of annual returns. Drawdowns include the starting balance. Annual data miss intrayear crashes. These are historical outcomes, not forecasts or allocation recommendations.')
    st.markdown('#### Different shocks, different outcomes')
    st.write('Treasuries cushioned the 2008 equity decline, but stocks and Treasuries both lost value in 2022. More bonds does not remove inflation or interest-rate risk.')
    matrix = stress_matrix(data, real)
    # Every cell is a compounded period return, never an annualized return or drawdown.
    fig = go.Figure(go.Heatmap(z=matrix.values, x=list(matrix.columns), y=list(matrix.index),
                             colorscale=[[0,'#cf526f'],[.5,'#152738'],[1,'#48dff5']], zmid=0,
                             text=matrix.apply(lambda col: col.map(lambda v:f'{v:+.1f}%')).values, texttemplate='%{text}',
                             hovertemplate='%{y} · %{x}<br>Period return: %{z:.1f}%<extra></extra>', colorbar=dict(title='Return %')))
    fig.update_layout(title=f'{basis} total return across each complete stress period', xaxis_tickangle=-35, yaxis_title='Stocks / Treasuries')
    readable_chart(style(fig, 490))
    st.caption('Stress periods are fixed and independent of the comparison-year slider. 2020 uses the full calendar year and conceals the intrayear crash.')
    st.download_button('Download allocation comparison', table.assign(start_year=start,end_year=end,basis=basis,starting_balance=balance).to_csv(), 'allocation-comparison.csv', 'text/csv')
    st.download_button('Download annual wealth paths', paths.rename_axis('year_end').assign(basis=basis).to_csv(), 'allocation-wealth.csv', 'text/csv')
    st.download_button('Download annual portfolio returns', paths.pct_change().iloc[1:].rename_axis('year').assign(basis=basis).to_csv(), 'allocation-annual-returns.csv', 'text/csv')
    st.download_button('Download historical stress comparison', matrix.rename_axis('allocation').assign(basis=basis).to_csv(), 'allocation-stresses.csv', 'text/csv')
    with st.expander('Verified sources and interpretation'):
        st.markdown(f'[Aswath Damodaran, NYU Stern]({metadata["source_notes"]}) · [Original workbook]({metadata["source_url"]})')
        st.write('The 1928–2025 stock, 10-year Treasury and CPI series were checked across all 98 years against the January 2026 NYU workbook. Stocks include dividends and predecessor large-cap indexes before 1957. Treasuries are a modeled constant-maturity exposure, not a broad bond fund or a held-to-maturity ladder. CPI is December-over-December.')
        st.write('Real annual return = (1 + nominal return) / (1 + inflation) − 1. Purchasing-power dollars are measured at the start of the selected window. Recovery is the first year-end regaining the peak before the largest drawdown; it is not necessarily sustained or the longest underwater period. Missing recovery remains explicitly unrecovered.')
        st.caption('Snapshot workbook SHA-256: '+metadata['workbook_sha256'])
