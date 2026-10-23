"""Dedicated CPI/GDP pages with terminal charts and inspectable source tables."""
import pandas as pd
import streamlit as st
from macro_components import (fetch_cpi,fetch_gdp,calendar_change,cpi_effects,contribution_chart,
                              CPI_GROUPS,CPI_DETAIL,CPI_WEIGHTS,GDP_ROWS,GDP_STACK)

@st.cache_data(ttl=3600,show_spinner=False)
def load_cpi():
    return fetch_cpi()

@st.cache_data(ttl=3600,show_spinner=False)
def load_gdp():
    return fetch_gdp()


def refresh():
    load_cpi.clear()
    load_gdp.clear()


def heatmap(frame, label, quarterly=False, percent=False, periods=12, transpose=True):
    st.markdown(f'**{label}**')
    if frame.empty:
        st.info('No component observations in this window.')
        return
    selected_frame = frame.tail(periods) if periods is not None else frame
    if transpose:
        table = selected_frame.T
        table.columns = [f'{d.year} Q{d.quarter}' if quarterly else d.strftime('%b %Y') for d in table.columns]
        index_label = 'Component'
    else:
        table = selected_frame.sort_index(ascending=False).copy()
        table.index = table.index.strftime('%b %Y')
        index_label = 'Month'
    table.index.name = index_label
    def cell(value):
        if pd.isna(value):
            return 'color: #7f8790; background-color: #171b20'
        # Symmetric intensity describes sign/magnitude, not risk or severity.
        strength = min(abs(value)/3,1)
        rgb = (30,105,88) if value >= 0 else (138,54,57)
        base = (20,24,29)
        color = tuple(round(base[i]+(rgb[i]-base[i])*strength) for i in range(3))
        return f'background-color: rgb{color}; color: #f0f0f0'
    styled = table.style.map(cell).format('{:+.2f}%' if percent else '{:+.3f}',na_rep='—')
    st.dataframe(styled,use_container_width=True,height=min(850,38+36*len(table)),
                 column_config={'_index':st.column_config.TextColumn(index_label,width='medium')})
    scope = f'Table shows all {len(selected_frame):,} periods in the selected window, newest first. Scroll the rows to explore earlier readings.' if periods is None else f'Table shows the latest {min(periods,len(frame))} visible periods.'
    st.caption('Green = positive; rose = negative. Color shows arithmetic sign, not a risk rating. Missing values are blank. ' + scope)


def source_status(data,frame,budget):
    for error in data.errors:
        st.warning(error)
    if frame.empty:
        st.info('Data unavailable. Add the required key or refresh after the source recovers.')
        return False
    usable = frame.dropna(how='all')
    if usable.empty:
        st.warning('No usable source observations.')
        return False
    last = usable.index.max()
    age = (pd.Timestamp.now().normalize()-last).days
    if age < 0:
        st.error('Future-dated source observations; data withheld.')
        return False
    if age > budget:
        st.warning(f'Latest source period is {last:%b %Y}, {age} days old. Data exceeds the {budget}-day freshness budget.')
    st.caption(f'{data.source} · Retrieved {data.retrieved} · Latest source period {last:%b %Y} · Revised history, not real-time vintages')
    return True


def window(frame, days, all_history):
    if all_history or frame.empty:
        return frame
    return frame.loc[frame.index >= pd.Timestamp.now().normalize()-pd.Timedelta(days=days)]


def render_cpi(days):
    st.subheader('CPI & components')
    st.write('See which parts of the household basket are raising prices, and which are offsetting them.')
    period = st.radio('Inflation comparison',['12-month','1-month'],horizontal=True)
    months = 12 if period == '12-month' else 1
    all_history = st.checkbox('Show all available contribution history')
    with st.spinner('Loading CPI components…'):
        data = load_cpi()
    if not source_status(data,data.frame,100):
        return
    rates = calendar_change(data.frame,months).rename(columns={**CPI_GROUPS,**CPI_DETAIL})
    latest = rates.loc[:,[c for c in ['Headline CPI','Core CPI','Shelter','Energy'] if c in rates]].dropna(how='all')
    if not latest.empty:
        date = latest.index[-1]
        for col,name in zip(st.columns(len(latest.columns)),latest.columns):
            value = latest.loc[date,name]
            col.metric(name,f'{value:.2f}%' if pd.notna(value) else 'Unavailable')
        st.caption(f'Common reference period {date:%B %Y} · {period} change · not seasonally adjusted')
    for series in data.frame:
        observed = data.frame[series].dropna()
        if observed.empty or (pd.Timestamp.now().normalize()-observed.index.max()).days > 100:
            st.warning(f'{ {**CPI_GROUPS,**CPI_DETAIL}.get(series,series) }: missing or stale component data. Latest source readings may differ across components.')
    effects = window(cpi_effects(data.frame,months),days,all_history)
    st.markdown('**What contributed to headline inflation?**')
    st.caption('Basket coverage: monthly effects in 2025–2026; 12-month effects from December 2025. Earlier inflation-rate history is below.')
    st.caption('Estimated effects in percentage points · eight non-overlapping expenditure groups · white line = headline inflation')
    if effects.empty:
        st.warning('No complete contribution estimates in this window. Monthly estimates require dated December basket weights; 12-month estimates require both endpoints and any annual weight pivot. Component inflation history remains below.')
    else:
        if effects.index[-1] < data.frame.dropna(how='all').index.max():
            st.warning(f'Latest complete effect estimate is {effects.index[-1]:%B %Y}; a comparison endpoint or dated basket is missing for newer periods.')
        st.plotly_chart(contribution_chart(effects,[*CPI_GROUPS.values(),'Unallocated difference'],'Headline CPI',
            f'US CPI · {period} estimated component effects','Percent / percentage points'),use_container_width=True)
        heatmap(effects,'Component effects · percentage points')
        last = effects.iloc[-1]
        ranked = last[list(CPI_GROUPS.values())].sort_values()
        st.write(f'In {effects.index[-1]:%B %Y}, {ranked.index[-1]} added the most ({ranked.iloc[-1]:+.2f} pp); {ranked.index[0]} had the smallest effect ({ranked.iloc[0]:+.2f} pp).')
        if abs(last['Unallocated difference']) > .1:
            st.warning('The latest unallocated difference exceeds 0.10 percentage point. Treat the decomposition as approximate; inspect the method below.')
        st.download_button('Download CPI component effects',effects.to_csv(index_label='Month'),'cpi-effects.csv','text/csv')
    st.subheader('Component inflation history')
    st.caption('Each series is its own inflation rate. Subcomponents overlap; these rates must not be added together.')
    history_options = {'All available': None, '20 years': 7300, '10 years': 3650, '5 years': 1825, '2 years': 730, '1 year': 365}
    history = st.selectbox('Component history range', list(history_options), key='cpi_component_history')
    st.caption('This range controls component inflation history below, independently of the sidebar and contribution chart.')
    available = rates.columns[rates.notna().any()].tolist()
    selected = st.multiselect('Compare CPI components',available,default=[c for c in ['Headline CPI','Core CPI','Shelter','Energy'] if c in available])
    visible = window(rates,history_options[history],history == 'All available')
    if visible.first_valid_index() is not None:
        visible = visible.loc[visible.first_valid_index():visible.last_valid_index()]
    if selected:
        import plotly.express as px
        comparison = visible[selected]
        if comparison.first_valid_index() is not None:
            comparison = comparison.loc[comparison.first_valid_index():comparison.last_valid_index()]
        fig = px.line(comparison,labels={'value':'Percent change','date':'Observation month','variable':'Component'})
        fig.update_layout(template='plotly_dark',paper_bgcolor='#090b0d',plot_bgcolor='#090b0d',height=400)
        fig.update_traces(connectgaps=False)
        fig.update_xaxes(rangeslider=dict(visible=True,thickness=.14,bgcolor='#111d2c',bordercolor='#405572',borderwidth=1), rangeselector=dict(buttons=[
            dict(count=1,label='1y',step='year',stepmode='backward'),
            dict(count=5,label='5y',step='year',stepmode='backward'),
            dict(count=10,label='10y',step='year',stepmode='backward'),
            dict(count=20,label='20y',step='year',stepmode='backward'),
            dict(label='All',step='all')]))
        fig.update_layout(height=490,legend=dict(orientation='h',y=1.18),margin=dict(l=65,r=30,t=105,b=55))
        st.plotly_chart(fig,use_container_width=True)
        if not comparison.empty:
            st.caption(f'History loaded: {comparison.index[0]:%b %Y} → {comparison.index[-1]:%b %Y}. Drag the handles below the chart to zoom. Each component begins when its own data becomes available; gaps remain gaps.')
    table_history = st.radio('Component table history',['Full selected history','Latest 12 periods'],horizontal=True)
    heatmap(visible,'Component inflation rates · percent',percent=True, periods=None if table_history == 'Full selected history' else 12, transpose=table_history != 'Full selected history')
    with st.expander('Component history coverage'):
        coverage = []
        for name in visible:
            observations = visible[name].dropna()
            coverage.append({'Component':name,'First inflation reading':observations.index[0].strftime('%b %Y') if not observations.empty else 'Unavailable',
                             'Latest inflation reading':observations.index[-1].strftime('%b %Y') if not observations.empty else 'Unavailable',
                             'Monthly readings':len(observations)})
        st.dataframe(pd.DataFrame(coverage),hide_index=True,use_container_width=True)
        st.caption('Twelve-month inflation needs an index reading exactly one year earlier. Components can have different start dates; no common start date is imposed.')
    st.download_button('Download CPI inflation history',visible.to_csv(index_label='Month'),'cpi-inflation-history.csv','text/csv')
    with st.expander('CPI method, weights & cautions'):
        st.write('The chart estimates BLS-style percentage-point effects from unadjusted indexes and dated December CPI-U relative-importance shares. Shares are price-updated through each preceding month. Intervals crossing a December basket pivot are split into segments and expressed against the same comparison-period base. These are Mosaic estimates, not the official BLS effects tables. Rounded inputs and basket changes can create differences; the unallocated difference is shown explicitly.')
        st.write('Weight coverage currently supports monthly effects during 2025–2026 and 12-month effects beginning December 2025. No later basket is projected backward, no missing comparison endpoint or weight pivot is filled, and weights expire after 12 months. Earlier index and inflation-rate histories remain available.')
        weights = pd.DataFrame(CPI_WEIGHTS).rename(index=CPI_GROUPS)
        weights.columns = [f'Dec {year} basket (%)' for year in weights.columns]
        st.dataframe(weights,use_container_width=True)
        st.markdown('[BLS effects methodology](https://www.bls.gov/cpi/factsheets/contributions-effects.htm) · [December 2024 basket](https://www.bls.gov/cpi/tables/relative-importance/2024.htm) · [December 2025 basket](https://www.bls.gov/cpi/tables/relative-importance/2025.htm)')
        st.write('Housing includes shelter, utilities and household operations; energy also sits inside housing and transportation. Energy and shelter are shown separately only in the rate comparisons. One-month unadjusted rates include seasonality and are not annualized. CPI is not the Federal Reserve’s PCE inflation target, and no 2% CPI warning is assigned.')
        st.dataframe(pd.DataFrame([{'Component':name,'FRED series':series,'Source':f'https://fred.stlouisfed.org/series/{series}'} for series,name in {**CPI_GROUPS,**CPI_DETAIL}.items()]),hide_index=True,use_container_width=True)


def render_gdp(days):
    st.subheader('GDP & components')
    st.write('Separate underlying domestic demand from inventory swings, trade and government spending.')
    all_history = st.checkbox('Show all available GDP history')
    with st.spinner('Loading official GDP contributions…'):
        data = load_gdp()
    if not source_status(data,data.frame,210):
        return
    visible = window(data.frame,days,all_history)
    if visible.empty:
        st.info('No GDP observations in this window.')
        return
    complete = visible.dropna(subset=[1,*GDP_STACK])
    if visible[[1,*GDP_STACK]].isna().any(axis=1).any():
        st.warning('Some quarters have incomplete contributions. Missing bars are unavailable, not zero.')
    if complete.empty:
        st.warning('No complete headline/component decomposition available; inspect source coverage.')
    else:
        last = complete.iloc[-1]
        cols = st.columns(3)
        cols[0].metric('Real GDP · annualized',f'{last[1]:+.1f}%')
        cols[1].metric('Consumer spending contribution',f'{last[2]:+.2f} pp')
        cols[2].metric('Inventories + trade',f'{last[14]+last[15]:+.2f} pp')
        st.caption(f'Common reference quarter {complete.index[-1].year} Q{complete.index[-1].quarter} · Seasonally adjusted annual rates')
        chart = visible.rename(columns={**GDP_STACK,1:'Real GDP'})
        st.plotly_chart(contribution_chart(chart,list(GDP_STACK.values()),'Real GDP','Contributions to US real GDP · QoQ annualized','Percent / percentage points'),use_container_width=True)
        residual = last[1]-last[list(GDP_STACK)].sum(min_count=5)
        if abs(residual) > .15:
            st.warning(f'Component sum differs from headline growth by {residual:+.2f} pp, beyond the rounding allowance. Verify the source before interpreting.')
        if last[1] < 0:
            st.warning('Real GDP contracted this quarter. One negative quarter does not establish an NBER recession.')
    heatmap(visible.rename(columns=GDP_ROWS),'GDP contribution table · pp; Real GDP row is % annualized',quarterly=True)
    st.subheader('The cyclical parts of GDP')
    st.write('Durable consumer goods, residential investment and business equipment can move sharply with the cycle. Compare their contributions alongside the broader economy.')
    cyclical = visible.reindex(columns=[4,13,11]).rename(columns={4:'Durable consumer goods',13:'Residential investment',11:'Business equipment'})
    heatmap(cyclical,'Selected cyclical contributions · percentage points',quarterly=True)
    st.caption('These are contributions to real GDP growth, not sector growth rates or GDP shares. This selection does not reproduce an EPB proprietary index or predict recession.')
    st.markdown('[Framework reference: Eric Basmajian, EPB Research — The 20% of the Economy That Drives 100% of Recessions](https://blog.epbresearch.com/p/the-20-of-the-economy-that-drives)')
    st.download_button('Download GDP contributions',visible.rename(columns=GDP_ROWS).to_csv(index_label='Quarter start'),'gdp-contributions.csv','text/csv')
    with st.expander('GDP method & interpretation'):
        st.markdown('[BEA NIPA table 1.1.2](https://apps.bea.gov/iTable/?reqid=19&step=3&isuri=1&1921=survey&1903=2) provides official contributions to quarterly real GDP growth at annual rates. The white line is the GDP growth rate; bars are percentage-point contributions.')
        st.write('The stack contains consumption, fixed investment, inventory change, net exports and government. Detail rows are nested and overlap with their parents; they are not stacked together. Imports already carry the BEA contribution sign. Annualization magnifies quarterly swings; releases and prior years are revised. Chained-dollar GDP component levels are not additive.')
        st.write('Inventory and trade contributions can dominate a quarter without matching the direction of final domestic demand. A positive growth reading is not an all-clear, and this page does not infer a trading signal.')
