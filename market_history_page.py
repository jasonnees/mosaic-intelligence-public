"""Interactive historical stress atlas inside the Boldin app."""
import io
import json
import zipfile
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from market_history_catalog import REGIMES,BY_REGIME,DEFAULT_REGIME,SERIES
from market_history_data import load_history,slice_market,indicator_window,evidence_rows,archived_rows

@st.cache_data(show_spinner=False)
def snapshot_payload():
    data = load_history()
    return dict(market=data.market, macro=data.macro, vintages=data.vintages, manifest=data.manifest)

def snapshot():
    from market_history_data import HistoryData
    return HistoryData(**snapshot_payload())


def style(fig,height=350):
    fig.update_layout(template='plotly_white',paper_bgcolor='#f6f6f4',plot_bgcolor='#f6f6f4',
                      font=dict(color='#111921',size=14),height=height,margin=dict(l=25,r=25,t=40,b=35),
                      hovermode='x unified',showlegend=False)
    fig.update_xaxes(showgrid=True,gridcolor='#e1e5ea')
    fig.update_yaxes(gridcolor='#e1e5ea',zerolinecolor='#526277')
    return fig


def shade(fig,regime,pre_only=False):
    if not pre_only:
        fig.add_vrect(x0=regime.start,x1=regime.end,fillcolor='#b64060',opacity=.11,line_width=0)
    return fig


def market_chart(frame,regime,pre_only=False):
    fig=make_subplots(rows=2,cols=1,shared_xaxes=True,vertical_spacing=.08,row_heights=[.65,.35])
    fig.add_trace(go.Scatter(x=frame.index,y=frame.index_100,name='Broad U.S. total return',
        line=dict(color='#087e8b',width=2),connectgaps=False,
        hovertemplate='%{x|%d %b %Y}<br>Index %{y:.2f}<extra></extra>'),row=1,col=1)
    fig.add_trace(go.Scatter(x=frame.index,y=frame.drawdown_pct,name='Drawdown',fill='tozeroy',
        line=dict(color='#b64060',width=1.5),connectgaps=False,
        hovertemplate='%{x|%d %b %Y}<br>Drawdown %{y:.2f}%<extra></extra>'),row=2,col=1)
    style(fig,470)
    fig.update_yaxes(title_text='Total return · 100 at start',row=1,col=1)
    fig.update_yaxes(title_text='Drawdown · %',row=2,col=1,rangemode='tozero')
    if not pre_only:
        fig.add_vrect(x0=regime.start,x1=regime.end,fillcolor='#b64060',opacity=.11,line_width=0,row='all',col=1)
    return fig


def export_evidence(data,regime,market,macro_rows,archives,pre_only=False):
    """Export precisely the selected charts' raw/transformed rows and scope."""
    end=pd.Timestamp(regime.start)-pd.Timedelta(days=1) if pre_only else pd.Timestamp(regime.view_end)
    macro=[]
    for series in regime.indicators:
        frame=indicator_window(data,series,regime,pre_only).copy()
        frame['Series']=series
        frame['Unit']=SERIES[series].unit
        macro.append(frame.reset_index())
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('market.csv',market.drop(columns=['wealth'],errors='ignore').to_csv(index_label='date'))
        archive.writestr('indicators.csv',pd.concat(macro,ignore_index=True).to_csv(index=False))
        archive.writestr('period-readings.csv',macro_rows.to_csv(index=False))
        archive.writestr('archived-spot-checks.csv',archives.to_csv(index=False))
        archive.writestr('sources-and-scope.json',json.dumps({
            'regime':regime.id,'view_start':regime.view_start,'view_end':str(end.date()),
            'stress_start':regime.start,'stress_end':regime.end,'pre_stress_only':pre_only,
            'historical_context_source':regime.source_url,
            'sources':{key:val for key,val in data.manifest['sources'].items() if key in [*regime.indicators,'market','vintages']},
            'snapshot_cutoff':data.manifest['snapshot_cutoff'],
            'definitions':{'index_100':'100 * wealth / wealth at first displayed daily close',
                           'drawdown_pct':'100 * (wealth / running maximum within displayed window - 1)',
                           'Before stress':'Last nonmissing revised value whose reference period ended strictly before stress start, with a bounded age budget. Not a publication-date filter.',
                           'stress_extrema':'Minimum/maximum of revised reference-period values inside the highlighted stress interval.',
                           'yoy':'100 * (index / index at exact prior calendar-year month - 1); no filling.',
                           'pre_stress_only':'Truncates to completed reference periods before stress; revised histories retain hindsight.'}},indent=2))
    return buffer.getvalue()


def render_market_history():
    st.markdown('<style>button[kind="primary"] {color: #08111d !important; font-weight: 700;}</style>',unsafe_allow_html=True)
    st.subheader('Market history')
    st.write('Explore how different stresses reached markets—and which indicators helped explain them.')
    st.caption('Historical case studies · The selected case sets the history window · Saved evidence, not today’s regime classification')
    if 'history_regime' not in st.session_state:
        requested=st.query_params.get('regime',DEFAULT_REGIME)
        st.session_state.history_regime=requested if requested in BY_REGIME else DEFAULT_REGIME
    current=st.session_state.history_regime
    def pick_regime():
        st.session_state.history_regime = st.session_state['history:picker']
    st.session_state['history:picker'] = current
    with st.container(key='regime-picker'):
        st.selectbox('Historical period', list(BY_REGIME), key='history:picker',
                     format_func=lambda key: BY_REGIME[key].button, on_change=pick_regime)
    with st.container(key='regime-buttons'):
        for offset in range(0,len(REGIMES),3):
            for column,regime in zip(st.columns(3),REGIMES[offset:offset+3]):
                if column.button(regime.button,key='regime:'+regime.id,
                                 type='primary' if current==regime.id else 'secondary',use_container_width=True):
                    st.session_state.history_regime=regime.id
                    st.rerun()
    regime=BY_REGIME[st.session_state.history_regime]
    st.markdown(f'### {regime.title}')
    st.caption(f'{regime.kind} · Highlighted stress: {regime.start} → {regime.end}')
    st.write(regime.context)
    st.markdown(f'[Historical context: {regime.source_title}]({regime.source_url})')
    left,right=st.columns([1,1])
    with left:
        st.markdown('**Stresses to be aware of**')
        for stress in regime.stresses:
            st.markdown('- '+stress)
    with right:
        st.markdown('**What to investigate**')
        st.write(regime.investigate)
        st.markdown('**What could mislead you**')
        st.write(regime.blind_spot)
    pre_only=st.toggle('Show pre-stress reference periods only',key='history_pre_only',
                       help='Truncate charts before the highlighted interval. Revised data still contains hindsight; this is not a real-time backtest.')
    try:
        data=snapshot()
    except Exception:
        st.error('The saved historical evidence is unavailable or failed its integrity check. No substitute market history is shown.')
        return
    st.caption(f'Saved study built {data.manifest["built_at"][:10]} · Snapshot cutoff {data.manifest["snapshot_cutoff"]} · Broad-market daily total returns from July 1926')
    st.info('Macro charts use revised data dated to the observation period, not when the release became public. Archived as-of spot checks appear separately below. This page does not establish predictive thresholds.')
    market=slice_market(data,regime,pre_only)
    rows=evidence_rows(data,regime,pre_only)
    archives=archived_rows(data,regime)
    st.markdown('#### Market path & drawdown')
    if market.empty:
        st.warning('No benchmark observations cover this selected window.')
    else:
        if not pre_only:
            stressed=market.loc[regime.start:regime.end]
            if not stressed.empty:
                worst=stressed.drawdown_pct.idxmin()
                st.metric('Worst broad-market drawdown in highlighted interval',f'{stressed.at[worst,"drawdown_pct"]:.1f}%',help='Loss from the highest daily close since the beginning of the displayed window. This is not necessarily a sector or S&P 500 peak-to-trough decline.')
                st.caption(f'Worst reading {worst:%d %b %Y} · Chart window {market.index[0]:%d %b %Y} → {market.index[-1]:%d %b %Y}')
        st.plotly_chart(market_chart(market,regime,pre_only),use_container_width=True,key='history_market:'+regime.id)
        st.caption('Kenneth French U.S. market factor + risk-free return; value-weighted total return, including distributions. Rebased to 100 at the first displayed close. Drawdown uses the running high within this window. Pink shading marks the selected study interval, not NBER recession dates.')
    st.markdown('#### Indicators for this period')
    st.caption('Each chart keeps its own labeled units. Zero reference lines describe arithmetic boundaries, not calibrated sell signals.')
    end=pd.Timestamp(regime.start)-pd.Timedelta(days=1) if pre_only else pd.Timestamp(regime.view_end)
    for offset in range(0,len(regime.indicators),2):
        for column,series in zip(st.columns(2),regime.indicators[offset:offset+2]):
            with column:
                definition=SERIES[series]
                st.markdown(f'**{definition.name}**')
                st.caption(definition.role+' · '+definition.unit)
                frame=indicator_window(data,series,regime,pre_only)
                if frame.empty or not frame.value.notna().any():
                    st.warning('No usable observations for this period. This series may begin later; no backfill or substitute is shown.')
                    continue
                fig=go.Figure(go.Scatter(x=frame.index,y=frame.value,name=definition.name,
                    line=dict(color='#6652ad' if definition.transform=='yoy' else '#087e8b',width=2),
                    connectgaps=False,hovertemplate='%{x|%d %b %Y}<br>%{y:.3f}<extra></extra>'))
                style(fig,285)
                shade(fig,regime,pre_only)
                axis_unit=('Index' if series in ['NFCI','STLFSI4'] else '% YoY' if definition.transform=='yoy' else 'pp' if series in ['T10Y2Y','T10Y3M'] else 'Net % of banks' if series=='DRTSCILM' else definition.unit)
                fig.update_yaxes(title=axis_unit)
                if definition.transform=='yoy' or series in ['T10Y2Y','T10Y3M','NFCI','STLFSI4','DRTSCILM']:
                    fig.add_hline(y=0,line_dash='dot',line_color='#8997ab')
                st.plotly_chart(fig,use_container_width=True,key='history:'+regime.id+':'+series)
                st.caption(f'{frame.dropna().index[0]:%b %Y} → {frame.dropna().index[-1]:%b %Y} · [{series} source]({data.manifest["sources"][series]["url"]})')
    st.markdown('#### Before stress versus during stress')
    st.caption('“Before” uses the last completed reference period before stress, not a claim that it was public then. Dates identify the start of that reference period. Minimum and maximum describe the highlighted interval only.')
    st.dataframe(rows,hide_index=True,use_container_width=True,
                 column_order=['Indicator','Unit','Before stress','Before reference date','Stress minimum','Stress maximum','Coverage'],
                 column_config={name:st.column_config.NumberColumn(name,format='%.2f') for name in ['Before stress','Stress minimum','Stress maximum']})
    st.markdown('#### What was visible in the archive?')
    if archives.empty:
        st.info('No archived as-of spot checks are included for this case. The revised charts above do not establish an advance warning.')
    else:
        st.write('These saved FRED/ALFRED checks requested the vintage available on each “As of” date. They cover selected indicators, not the full information set or every chart.')
        st.dataframe(archives.drop(columns=['series_id']),hide_index=True,use_container_width=True,
                     column_config={'Archived value':st.column_config.NumberColumn(format='%.3f')})
        st.caption('Missing archived observations do not prove the original statistic was unpublished or unknowable. Raw units are retained unless an archived growth calculation is explicitly labeled.')
    st.download_button('Download this period’s data & sources',export_evidence(data,regime,market,rows,archives,pre_only),
                       f'mosaic-history-{regime.id}{"-pre-stress" if pre_only else ""}.zip','application/zip')
    with st.expander('Sources, selection & calculation notes'):
        st.write('These are deliberately selected case studies, not all market corrections or independent statistical trials. Stress intervals are study windows; some are broad historical regimes, others are daily benchmark peak-to-trough windows. They are not comparable recession labels. No trading rule, causal estimate or calibrated warning probability is inferred.')
        st.markdown('[Market data library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) · [Benchmark construction](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_factors.html) · [Archived vintages](https://alfred.stlouisfed.org/)')
        st.write('Charts do not splice S&P 500, Dow, Nasdaq or monthly price-only series into the academic total-return benchmark. Monthly growth uses the exact prior-year calendar month; missing bases stay missing. The saved snapshot is intentionally historical and is not subject to current-feed freshness alerts. Financial-conditions histories can be reconstructed or revised after the period shown.')
        st.dataframe(pd.DataFrame([{'Series':s,'Definition':SERIES[s].name,'Raw unit':data.manifest['sources'][s]['raw_units'],
            'Displayed unit':SERIES[s].unit,'Transform':SERIES[s].transform,'Source':data.manifest['sources'][s]['url']} for s in regime.indicators]),hide_index=True,use_container_width=True)
