"""Market Risk Explorer — public data with visible reliability."""
import pandas as pd
import plotly.express as px
import streamlit as st
import config
from risk_catalog import INDICATORS, BY_ID, DOMAINS, WATCH_RULES, RULE_SOURCES
from indicator_guidance import GUIDES, direction, data_warning
from brand import masthead, style_chart
from risk_data import RiskDataService, assess, transform_frame
from macro_pages import render_cpi, render_gdp, refresh as refresh_macro
from market_history_page import render_market_history

st.set_page_config(page_title='Market Risk Explorer', page_icon='◉', layout='wide')

@st.cache_resource
def service():
    archive = None
    if config.DATA_SOURCE_MODE == 's3':
        try:
            from s3_reader import S3DataReader
            candidate = S3DataReader()
            if candidate.available:
                archive = candidate
        except Exception:
            pass
    return RiskDataService(archive=archive)

@st.cache_data(ttl=3600, show_spinner=False)
def fetch(series_id, days):
    return service().fetch(BY_ID[series_id], days)


def table_row(indicator, result):
    observation = assess(result.frame, indicator)
    movement = direction(result.frame, indicator)
    warning = data_warning(observation, indicator) or (observation.detail if indicator.series_id in WATCH_RULES else GUIDES[indicator.series_id].caution)
    return {
        'Indicator': indicator.name, 'Value': observation.value, 'Units': indicator.unit,
        'Observation date': observation.observed_at, 'Age (days)': observation.age_days,
        'Data status': observation.status, 'Watch condition': observation.watch,
        'Direction': movement.label, 'Interpretation': movement.explanation, 'Warning': warning,
        'Comparison date': movement.prior_date, 'Change': movement.change,
        'Frequency': indicator.frequency, 'Age budget (days)': indicator.max_age_days,
        'Source': result.provenance, 'Retrieved (UTC)': result.fetched_at,
        'Source class': indicator.reliability, 'Series': indicator.series_id,
        'Source link': indicator.source_url, 'Notes': result.error or observation.detail,
    }


def render_indicator_table(rows, key):
    """Use positions in the displayed frame, including after filtering/sorting."""
    st.caption('Select an indicator row to show its chart below.')
    # A changed row set gets fresh selection state, so a positional selection
    # cannot silently become a different series after filtering or refresh.
    identity = '|'.join(rows['Series'].tolist())
    detailed = st.checkbox('Show interpretation, warnings & source columns', key=f'details:{key}')
    primary = (['Indicator', 'Domain', 'Frequency', 'Display unit', 'Watch condition'] if key == 'catalog'
               else ['Indicator', 'Value', 'Units', 'Data status', 'Watch condition', 'Direction'])
    status_colors = {'fresh': '#8ce5bd', 'Watch': '#ffbd69', 'stale': '#ff839b',
                     'missing': '#ff839b', 'invalid': '#ff839b', 'insufficient history': '#ffbd69',
                     'Unavailable': '#ff839b', 'Not evaluated': '#ff839b',
                     'Rising': '#78b7ff', 'Falling': '#a9a1ff'}
    status_columns = [column for column in ['Data status', 'Watch condition', 'Direction'] if column in rows]
    display = rows.style.map(lambda value: f'color: {status_colors[value]}; font-weight: 600' if value in status_colors else '', subset=status_columns)
    event = st.dataframe(
        display, hide_index=True, use_container_width=True,
        column_order=list(rows.columns) if detailed else primary,
        key=f'{key}:{identity}', on_select='rerun', selection_mode='single-row',
        column_config={'Source link': st.column_config.LinkColumn('Source link'),
                       'Value': st.column_config.NumberColumn('Value', format='%.2f')})
    positions = event['selection']['rows']
    if positions and 0 <= positions[0] < len(rows):
        return BY_ID[rows.iloc[positions[0]]['Series']]
    return None


def render_indicator_chart(indicator, result, days):
    st.subheader(indicator.name)
    observation = assess(result.frame, indicator)
    st.markdown(f'**{indicator.name}** · [{indicator.source.upper()} source notes]({indicator.source_url})')
    st.caption(f'{indicator.series_id} · {indicator.frequency} · {indicator.reliability} · {observation.status} · {result.provenance}')
    guide = GUIDES[indicator.series_id]
    movement = direction(result.frame, indicator)
    warning = data_warning(observation, indicator)
    if warning:
        st.warning(warning)
    elif observation.watch == 'Watch':
        st.warning(observation.detail)
    elif observation.watch == 'Not triggered':
        st.info(observation.detail)
    else:
        st.info('Directional context: this indicator has no fixed warning threshold. It cannot produce an all-clear.')
    latest, trend = st.columns([1, 2])
    latest.metric('Latest reading', f'{observation.value:,.3g}' if observation.value is not None else 'Unavailable', help=indicator.unit)
    trend.metric('Direction over comparison window', movement.label,
                 help='Compare with roughly three months earlier, or one year earlier for quarterly series. This describes movement, not risk severity.')
    st.write(movement.explanation)
    if movement.change is not None:
        change_unit = 'percentage points' if '%' in indicator.unit or indicator.unit == 'percentage points' else indicator.unit
        st.caption(f'Change: {movement.change:+.3g} {change_unit} · {movement.prior_date} → {movement.current_date}. Direction compares displayed values, including year-over-year growth where selected.')
    st.caption(f'Observation period: {observation.observed_at or "unavailable"} · Age: {observation.age_days if observation.age_days is not None else "unknown"} days · Freshness budget: {indicator.max_age_days} days · Units: {indicator.unit}')
    st.caption(f'Retrieved: {result.fetched_at} · Transformation: {indicator.transform}')
    if result.error:
        st.warning(result.error)
    if indicator.note:
        st.write(indicator.note)
    frame = transform_frame(result.frame, indicator)
    if not frame.empty:
        cutoff = pd.Timestamp.now(tz='UTC').tz_localize(None) - pd.Timedelta(days=days)
        frame = frame[frame['date'] >= cutoff]
        if frame[indicator.series_id].notna().any():
            fig = px.line(frame, x='date', y=indicator.series_id, labels={indicator.series_id: indicator.unit, 'date': 'Observation period'})
            fig = style_chart(fig, indicator.domain)
            rule = WATCH_RULES.get(indicator.series_id)
            if rule:
                fig.add_hline(y=rule[1], line_dash='dot', line_color='#ffbd69',
                              annotation_text=f'Watch reference: {rule[1]} {indicator.unit}', annotation_position='top left')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info('No usable transformed values in this chart window. A valid prior-year base is required.')
    else:
        st.info('No observations available. Check the source key and availability; no substitute signal is shown.')

    with st.expander('Interpretation & warning method', expanded=True):
        st.markdown(f'**If rising:** {guide.rising}.')
        st.markdown(f'**If falling:** {guide.falling}.')
        st.markdown(f'**Use with care:** {guide.caution}')
        rule = WATCH_RULES.get(indicator.series_id)
        if rule:
            label, url, caveat = RULE_SOURCES[indicator.series_id]
            sign = '>' if rule[0] == 'gt' else '<'
            st.markdown(f'**Watch condition:** unrounded value {sign} {rule[1]} {indicator.unit}. [{label}]({url}).')
            st.caption(caveat + ' The rule uses unrounded data; displayed readings may be rounded.')
        else:
            st.caption('No fixed threshold is assigned. A direction is descriptive and is not a risk warning or investment instruction.')
        st.markdown(f'[Series definition and methodology]({indicator.source_url})')


def main():
    masthead()
    st.title('Market Risk Explorer')
    st.write('The macro picture, one piece at a time. Explore market conditions, follow the direction of change, and see where the evidence needs attention.')
    st.caption(f'{len(INDICATORS)} curated indicators · Free public feeds · Hourly session cache · Educational context')
    with st.sidebar:
        st.markdown('### MOSAIC INCOME')
        st.caption('MARKET RISK EXPLORER')
        st.header('Explore risks')
        views = ['Overview'] + [d[0] for d in DOMAINS.values()] + ['CPI & components', 'GDP & components', 'Market history', 'Portfolio implications', 'Data catalog']
        requested = st.query_params.get('view', 'Overview')
        view = st.radio('View', views, index=views.index(requested) if requested in views else 0)
        history_options = [0, 365, 730, 1825, 3650, 7300] if view == 'CPI & components' else [365, 730, 1825, 3650, 7300]
        days = st.selectbox('History', history_options, index=0 if view == 'CPI & components' else 1,
                            format_func=lambda n: {0:'All available', 365:'1 year', 730:'2 years', 1825:'5 years', 3650:'10 years', 7300:'20 years'}[n])
        if st.button('Refresh data'):
            fetch.clear()
            refresh_macro()
            st.rerun()
        st.caption('S3 history enabled; APIs refresh current data.' if service().archive else 'Direct public APIs; no AWS required.')
        if not config.FRED_API_KEY:
            st.warning('Add a free FRED_API_KEY to load FRED observations.')
        if not config.EIA_API_KEY:
            st.info('EIA_API_KEY enables the electricity price series. Other energy series use FRED.')
    if view == 'Market history':
        render_market_history()
        return
    if view == 'CPI & components':
        render_cpi(days)
        return
    if view == 'GDP & components':
        render_gdp(days)
        return
    if view == 'Data catalog':
        catalog = pd.DataFrame([{
            'Series': i.series_id, 'Indicator': i.name, 'Domain': DOMAINS[i.domain][0],
            'Source': i.source.upper(), 'Source link': i.source_url, 'Frequency': i.frequency,
            'Raw unit': i.raw_unit, 'Display unit': i.unit, 'Transformation': i.transform,
            'Age budget (days)': i.max_age_days, 'Source class': i.reliability,
            'Interpretation': GUIDES[i.series_id].rising + ' / ' + GUIDES[i.series_id].falling,
            'Warning': GUIDES[i.series_id].caution,
            'Watch condition': (f'{WATCH_RULES[i.series_id][0]} {WATCH_RULES[i.series_id][1]} {i.unit}' if i.series_id in WATCH_RULES else 'No fixed threshold'),
        } for i in INDICATORS])
        indicator = render_indicator_table(catalog, 'catalog')
        if indicator is not None:
            with st.spinner('Loading indicator history…'):
                result = fetch(indicator.series_id, days)
            render_indicator_chart(indicator, result, days)
        st.download_button('Download catalog', catalog.to_csv(index=False), 'market-risk-catalog.csv', 'text/csv')
        st.write('Official means produced by a public agency or Federal Reserve bank. Third-party series are freely accessible through FRED, but have source-specific licensing and history limits. Check the linked source notes before redistribution.')
        st.write('Freshness budgets include reporting lag and reference-period dating. They are operational heuristics, not official release deadlines. Fresh does not mean unrevised or real time.')
        return
    if view == 'Portfolio implications':
        st.subheader('Connect the evidence to your household plan')
        st.write('These are planning questions, not a model portfolio or trading recommendations. No allocation is inferred from the indicator count or watch conditions.')
        for title, explanation, implication in DOMAINS.values():
            st.markdown(f'**{title}**')
            st.write(implication)
        st.info('Use your time horizon, planned withdrawals, liabilities and capacity for loss when reviewing exposures. National indicators cannot establish the right allocation for an individual household.')
        return
    domain = next((key for key, value in DOMAINS.items() if value[0] == view), None)
    # Overview loads a small representative basket; details load only one domain.
    overview_ids = {'SP500','VIXCLS','UNRATE','IC4WSA','A191RL1Q225SBEA','CPIAUCSL','GASREGW',
                    'DGS10','T10Y2Y','STLFSI4','NFCI','MORTGAGE30US','HOUST'}
    selected = [i for i in INDICATORS if i.domain == domain] if domain else [i for i in INDICATORS if i.series_id in overview_ids]
    st.subheader(view if domain else 'Household risk overview')
    if domain:
        st.write(DOMAINS[domain][1])
        st.info(DOMAINS[domain][2])
    else:
        st.write('A representative basket across six risk domains. Open a domain for all its indicators and histories.')
    with st.spinner('Checking public observations…'):
        results = {i.series_id: fetch(i.series_id, days) for i in selected}
    rows = pd.DataFrame([table_row(i, results[i.series_id]) for i in selected])
    fresh = int((rows['Data status'] == 'fresh').sum())
    watches = int((rows['Watch condition'] == 'Watch').sum())
    left, middle, right = st.columns(3)
    left.metric('Fresh data', f'{fresh}/{len(selected)}')
    middle.metric('Watch flags', watches)
    right.metric('Needs attention', len(selected) - fresh)
    st.caption('Watch flags reflect explicit thresholds. Direction describes change. Data issues are separate. None of these is a calibrated risk score.')
    if fresh < len(selected):
        issues = rows.loc[rows['Data status'] != 'fresh', 'Data status'].value_counts()
        st.warning('Data needs attention: ' + ' · '.join(f'{count} {state}' for state, count in issues.items()) + '. Signals are withheld for these observations; open a row for the reason and next step.')
    status = st.radio('Filter observations', ['All', 'Fresh', 'Needs attention', 'Watch'], horizontal=True)
    filtered = rows
    if status == 'Fresh':
        filtered = rows[rows['Data status'] == 'fresh']
    elif status == 'Needs attention':
        filtered = rows[rows['Data status'] != 'fresh']
    elif status == 'Watch':
        filtered = rows[rows['Watch condition'] == 'Watch']
    indicator = render_indicator_table(filtered, f'observations:{view}:{status}')
    st.download_button('Download observations and reliability', rows.to_csv(index=False), 'market-risk-observations.csv', 'text/csv')
    if indicator is None and not filtered.empty:
        indicator = BY_ID[filtered.iloc[0]['Series']]
    if indicator is not None:
        render_indicator_chart(indicator, results[indicator.series_id], days)
    else:
        st.info('No indicators match this filter. Choose another filter to explore a chart.')
    with st.expander('How to interpret the data'):
        st.write('Observation date is the reported period, not the publication date. Age is measured from that date. Monthly and quarterly budgets allow for reporting lags. Year-over-year calculations require a matching prior-year period; absent comparisons remain gaps.')
        st.write('Watch rules are transparent descriptive heuristics, not recession probabilities or buy/sell advice. Other indicators are shown as context. Source data may be revised, and licensed market indexes may have shorter histories.')
        st.json({sid: {'operator': rule[0], 'threshold': rule[1], 'meaning': rule[2]} for sid, rule in WATCH_RULES.items()})
    st.caption('Mosaic Income · Market Risk Explorer · Research & education; not individualized investment advice.')

if __name__ == '__main__':
    main()
