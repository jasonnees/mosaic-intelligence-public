"""Mosaic Income's original wordmark with a dark dashboard palette."""
import base64
from html import escape
import re
from pathlib import Path
import streamlit as st

ASSETS = Path(__file__).resolve().parent / 'assets'
COLORS = {'equity': '#48dff5', 'growth': '#a9a1ff', 'inflation': '#ffbd69',
          'rates': '#78b7ff', 'credit': '#ff839b', 'housing': '#8ce5bd'}

CSS = '''
<style>
:root {color-scheme:dark; --mosaic-cyan:#48dff5;}
[data-testid="stAppViewContainer"] {background:radial-gradient(ellipse at 90% 0%,#142d46 0%,#08111d 48%); color:#e8f0fa;}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stSidebar"] {background:#0d1a2a; border-right:1px solid #253c53;}
[data-testid="stMainBlockContainer"] {padding-top:2.1rem; max-width:1600px;}
h1,h2,h3 {letter-spacing:-.035em; color:#eff7ff;}
h1 {font-weight:700 !important;}
a {color:#69dff5;}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {color:#a9bbcf;}
[data-testid="stAlert"] p {color:#e8f0fa;}
[data-testid="stMetric"] {padding:1.1rem 1.3rem; border:1px solid #2a415b; border-radius:14px; background:linear-gradient(135deg,#13263b,#101c2c);}
[data-testid="stMetricValue"] {color:#60e2f5; font-variant-numeric:tabular-nums;}
[data-testid="stDataFrame"] {border:1px solid #2a415b; border-radius:12px; overflow:hidden;}
[data-testid="stPlotlyChart"] {border:1px solid #263b52; border-radius:14px; overflow:hidden;}
.mosaic-masthead {display:flex; align-items:center; justify-content:space-between; gap:24px; padding:0 0 20px; margin:0 0 14px; border-bottom:1px solid #294057;}
.mosaic-masthead img {width:min(430px,65vw); height:auto; filter:brightness(1.9);}
.mosaic-masthead a {font-size:12px; text-transform:uppercase; letter-spacing:.16em; text-decoration:none; color:#94d5e8;}
.mosaic-eyebrow {font-size:11px; letter-spacing:.23em; color:#8db9d2; text-transform:uppercase; margin:6px 0 0;}
.mosaic-guide {border-left:3px solid #48dff5; padding:12px 18px; background:#101f31; border-radius:0 10px 10px 0; margin:12px 0;}
.mosaic-guide p {margin:0; color:#c7d8e9;}
.mosaic-chart-key {display:flex; flex-wrap:wrap; gap:10px 18px; margin:8px 0 20px; font-size:14px; color:#dce8f5;}
.mosaic-chart-key span {display:inline-flex; align-items:center; gap:8px;}
.mosaic-chart-key i {display:inline-block; width:12px; height:12px; flex-shrink:0; border:1px solid #a9bbcf;}
.st-key-stress-picker, .st-key-regime-picker, .st-key-annual-summary {display:none;}
@media(max-width:700px) {
 .mosaic-masthead {flex-direction:column;align-items:flex-start;gap:8px;padding-bottom:10px;margin-bottom:8px;}
 .mosaic-masthead img {width:min(240px,80vw);}
 .mosaic-eyebrow,.mosaic-intro {display:none;}
 [data-testid="stMainBlockContainer"] {padding:3.5rem 1rem 2rem;}
 h1 {font-size:2rem !important;} h2 {font-size:1.6rem !important;} h3 {font-size:1.35rem !important;}
 [data-testid="stMetric"] {padding:.65rem 1rem;}
 [data-testid="stMetricValue"] {font-size:1.7rem;}
 [data-testid="stButton"] button, [data-testid="stDownloadButton"] button {min-height:44px;}
 input, [role="combobox"] {font-size:16px !important;}
 .st-key-stress-picker,.st-key-regime-picker,.st-key-annual-summary {display:block;}
 .st-key-stress-buttons,.st-key-regime-buttons,.st-key-annual-table {display:none;}
 .mosaic-chart-key {gap:10px 14px;font-size:14px;}
}
</style>
'''


def masthead():
    st.markdown(CSS, unsafe_allow_html=True)
    logo = base64.b64encode((ASSETS / 'mosaic-income-wordmark.png').read_bytes()).decode()
    st.markdown(f'<div class="mosaic-masthead"><img src="data:image/png;base64,{logo}" alt="Mosaic Income">'
                '<a href="https://mosaicincome.substack.com/" target="_blank" rel="noopener noreferrer">Research &amp; perspectives ↗</a></div>'
                '<p class="mosaic-eyebrow">Macro intelligence · Public data · Clear context</p>', unsafe_allow_html=True)


def style_chart(fig, domain):
    fig.update_traces(line={'color': COLORS[domain], 'width': 2.8}, connectgaps=False)
    fig.update_layout(template='plotly_dark', paper_bgcolor='#101f31', plot_bgcolor='#101f31',
                      font={'color': '#c5d7e9'}, margin={'l': 24, 'r': 24, 't': 30, 'b': 30},
                      hovermode='x unified', height=390)
    fig.update_xaxes(gridcolor='#25394e', zerolinecolor='#3b5065')
    fig.update_yaxes(gridcolor='#25394e', zerolinecolor='#3b5065')
    return fig


def readable_chart(fig, **kwargs):
    """Let titles and series keys wrap outside Plotly's fixed drawing area."""
    title = fig.layout.title.text
    if title:
        st.markdown(f'**{title}**')
    legend = []
    seen = set()
    if fig.layout.showlegend is not False:
        for trace in fig.data:
            if trace.showlegend is False or not trace.name or trace.name in seen:
                continue
            seen.add(trace.name)
            color = getattr(getattr(trace, 'line', None), 'color', None) or getattr(getattr(trace, 'marker', None), 'color', None)
            # Only scalar CSS colors from chart definitions enter the HTML key.
            if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{3,8}|[a-zA-Z]+|rgba?\([0-9., %]+\)', color):
                color = '#a9bbcf'
            legend.append(f'<span><i style="background:{escape(color)}"></i>{escape(str(trace.name))}</span>')
    fig.update_layout(title=None, showlegend=False, font_size=14,
                      margin=dict(l=35, r=20, t=55 if fig.layout.xaxis.rangeselector.buttons else 25, b=45))
    fig.update_xaxes(automargin=True, nticks=5, tickfont_size=13)
    fig.update_yaxes(automargin=True, tickfont_size=13)
    st.plotly_chart(fig, use_container_width=True, **kwargs)
    if legend:
        st.markdown('<div class="mosaic-chart-key" aria-label="Chart series">' + ''.join(legend) + '</div>', unsafe_allow_html=True)
