"""CPI and GDP decomposition: dated weights, exact calendar comparisons, no fill."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests
import config
from risk_data import clean_frame

CPI_GROUPS = {
    'CPIFABNS': 'Food & beverages', 'CPIHOSNS': 'Housing', 'CPIAPPNS': 'Apparel',
    'CPITRNNS': 'Transportation', 'CPIMEDNS': 'Medical care', 'CPIRECNS': 'Recreation',
    'CPIEDUNS': 'Education & communication', 'CPIOGSNS': 'Other goods & services',
}
CPI_DETAIL = {
    'CPIAUCNS': 'Headline CPI', 'CPILFENS': 'Core CPI', 'CUUR0000SAH1': 'Shelter',
    'CPIENGNS': 'Energy', 'CUUR0000SAF11': 'Food at home',
    'CUUR0000SEFV': 'Food away from home', 'CUUR0000SACL1E': 'Core goods',
    'CUUR0000SASLE': 'Services less energy',
}
# CPI-U, December relative importance (percent). Never carry weights into another year.
# Source: BLS relative-importance/{year}.htm, Table 1; retrieved 2026-10-23.
CPI_WEIGHTS = {
    2024: dict(zip(CPI_GROUPS, [14.526,44.201,2.480,16.571,8.273,5.292,5.732,2.925])),
    2025: dict(zip(CPI_GROUPS, [14.539,44.469,2.368,16.316,8.423,5.137,5.846,2.902])),
}
GDP_ROWS = {
    1:'Real GDP', 2:'Consumer spending', 3:'  Goods', 4:'    Durable goods',
    5:'    Nondurable goods', 6:'  Services', 7:'Private investment',
    8:'  Fixed investment', 9:'    Business investment', 10:'      Structures',
    11:'      Equipment', 12:'      Intellectual property', 13:'    Residential investment',
    14:'  Inventories', 15:'Net exports', 16:'  Exports', 19:'  Imports',
    22:'Government', 23:'  Federal', 24:'    Defense', 25:'    Nondefense', 26:'  State & local',
}
GDP_STACK = {2:'Consumer spending',8:'Fixed investment',14:'Inventories',15:'Net exports',22:'Government'}
COLORS = ['#087bf5','#bf68e5','#e5ce00','#e44d26','#00becb','#89df9b','#f49a42','#9798ff']

@dataclass
class MacroData:
    frame: pd.DataFrame = field(default_factory=pd.DataFrame)
    errors: list = field(default_factory=list)
    retrieved: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec='seconds'))
    source: str = ''


def calendar_change(frame, periods=12):
    """Monthly frequency is explicit; gaps stay gaps instead of shifting comparisons."""
    frame = frame.sort_index().asfreq('MS')
    prior = frame.shift(periods).where(lambda x: x > 0)
    return (frame / prior - 1) * 100


def fetch_cpi():
    from data_fetcher import FREDClient
    if not config.FRED_API_KEY:
        return MacroData(errors=['Add FRED_API_KEY to Streamlit secrets to load CPI components.'])
    def one(series):
        try:
            raw = FREDClient().get_series(series, start_date='1913-01-01')
            return series, clean_frame(raw, series).set_index('date')[series], None
        except Exception:
            return series, pd.Series(dtype=float), f'{series}: source unavailable; no substitute data.'
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(one, {**CPI_GROUPS, **CPI_DETAIL}))
    frame = pd.concat([values.rename(series) for series, values, _ in results],axis=1,sort=True).sort_index()
    return MacroData(frame, [error for _,_,error in results if error], source='BLS CPI-U via FRED · unadjusted monthly indexes')


def cpi_effects(indexes, months=1, weights=None):
    """Estimate monthly effects using December shares, chained to the interval base.

    Relative-importance weights and rounded indexes do not reproduce official BLS
    effects exactly. Unexplained differences are returned, never normalized away.
    No estimate outside dated weight coverage or with missing endpoints/pivots.
    """
    weights = CPI_WEIGHTS if weights is None else weights
    columns = ['CPIAUCNS', *CPI_GROUPS]
    if not set(columns) <= set(indexes):
        return pd.DataFrame()
    idx = indexes[columns].sort_index().asfreq('MS').where(lambda x: x > 0)
    effects = pd.DataFrame(np.nan,index=idx.index,columns=list(CPI_GROUPS))
    for end in idx.index:
        base = end - pd.DateOffset(months=months)
        if base not in idx.index or idx.loc[base].isna().any() or idx.loc[end].isna().any():
            continue
        start = base
        total = pd.Series(0.0,index=list(CPI_GROUPS))
        valid = True
        while start < end:
            year = start.year if start.month == 12 else start.year-1
            pivot = pd.Timestamp(year=year,month=12,day=1)
            boundary = min(end,pivot+pd.DateOffset(years=1))
            if year not in weights or pivot not in idx.index or boundary not in idx.index:
                valid = False
                break
            if idx.loc[pivot].isna().any() or idx.loc[boundary].isna().any():
                valid = False
                break
            # Segment effects share the same interval-base denominator. Only
            # endpoints and annual weight pivots are required, not intervening months.
            total += (pd.Series(weights[year])/100 *
                      (idx.loc[boundary,list(CPI_GROUPS)]-idx.loc[start,list(CPI_GROUPS)]) /
                      idx.loc[pivot,list(CPI_GROUPS)] *
                      idx.at[pivot,'CPIAUCNS']/idx.at[base,'CPIAUCNS'] * 100)
            start = boundary
        if valid:
            effects.loc[end] = total
    headline = calendar_change(idx[['CPIAUCNS']],months).CPIAUCNS
    effects['Headline CPI'] = headline
    effects['Unallocated difference'] = headline - effects[list(CPI_GROUPS)].sum(axis=1,min_count=len(CPI_GROUPS))
    return effects.rename(columns=CPI_GROUPS).dropna(subset=[*CPI_GROUPS.values()])


def parse_gdp(payload):
    results = payload.get('BEAAPI',{}).get('Results',{})
    rows = results.get('Data',[])
    if not rows:
        raise ValueError('BEA returned no GDP contribution observations.')
    raw = pd.DataFrame(rows)
    raw['value'] = pd.to_numeric(raw.DataValue.str.replace(',','',regex=False),errors='coerce')
    raw['line'] = pd.to_numeric(raw.LineNumber,errors='coerce')
    raw = raw[raw.TimePeriod.str.fullmatch(r'\d{4}Q[1-4]')]
    frame = raw.pivot_table(index='TimePeriod',columns='line',values='value',aggfunc='last')
    frame.index = pd.PeriodIndex(frame.index,freq='Q').to_timestamp()
    return frame.reindex(columns=GDP_ROWS).sort_index().asfreq('QS').replace([np.inf,-np.inf],np.nan)


GDP_FRED = {1:'A191RL1Q225SBEA', **{line:code+'2Q224SBEA' for line,code in {
    2:'DPCERY',3:'DGDSRY',4:'DDURRY',5:'DNDGRY',6:'DSERRY',7:'A006RY',8:'A007RY',
    9:'A008RY',10:'A009RY',11:'Y033RY',12:'Y001RY',13:'A011RY',14:'A014RY',
    15:'A019RY',16:'A020RY',19:'A021RY',22:'A822RY',23:'A823RY',24:'A824RY',
    25:'A825RY',26:'A829RY'}.items()}}


def fetch_gdp():
    errors = []
    if config.BEA_API_KEY:
        try:
            response = requests.get('https://apps.bea.gov/api/data/',params={
                'UserID':config.BEA_API_KEY,'method':'GetData','datasetname':'NIPA',
                'TableName':'T10102','Frequency':'Q','Year':'ALL','ResultFormat':'JSON'},timeout=45)
            response.raise_for_status()
            return MacroData(parse_gdp(response.json()),source='BEA NIPA table 1.1.2 · real GDP · seasonally adjusted annual rates')
        except Exception:
            errors.append('Direct BEA service unavailable; trying official BEA contributions delivered by FRED.')
    if not config.FRED_API_KEY:
        return MacroData(errors=errors+['Add FRED_API_KEY or BEA_API_KEY to Streamlit secrets to load official GDP contributions.'])
    from data_fetcher import FREDClient
    def one(item):
        line, series = item
        try:
            raw = FREDClient().get_series(series,start_date='1947-01-01')
            values = clean_frame(raw,series).set_index('date')[series]
            return line, values, None
        except Exception:
            return line, pd.Series(dtype=float), f'GDP {GDP_ROWS[line].strip()}: FRED source unavailable.'
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(one,GDP_FRED.items()))
    frame = pd.concat([values.rename(line) for line,values,_ in results],axis=1).sort_index()
    if not frame.empty:
        frame = frame.asfreq('QS')
    return MacroData(frame,errors+[e for _,_,e in results if e],
                     source='BEA NIPA table 1.1.2 via FRED · real GDP · seasonally adjusted annual rates')


def contribution_chart(frame, components, headline, title, unit):
    import plotly.graph_objects as go
    fig = go.Figure()
    for n, name in enumerate(components):
        fig.add_bar(x=frame.index,y=frame[name],name=name,marker_color='#7c858e' if name == 'Unallocated difference' else COLORS[n % len(COLORS)],
                    hovertemplate='%{x|%b %Y}<br>'+name+': %{y:+.3f} pp<extra></extra>')
    fig.add_scatter(x=frame.index,y=frame[headline],name=headline,mode='lines+markers',
                    line=dict(color='#ffffff',width=2.5),marker=dict(size=4),connectgaps=False,
                    hovertemplate='%{x|%b %Y}<br>'+headline+': %{y:.2f}%<extra></extra>')
    fig.update_layout(title=dict(text=title,font=dict(color='#ffbd69',size=16),x=.02,y=.98,yanchor='top'),barmode='relative',
        paper_bgcolor='#090b0d',plot_bgcolor='#090b0d',font=dict(family='monospace',color='#ddd',size=12),
        height=490,margin=dict(l=20,r=25,t=140,b=35),hovermode='x unified',
        legend=dict(orientation='h',y=1.02,yanchor='bottom',x=0,font=dict(size=11)),
        yaxis=dict(title=unit,side='right',gridcolor='#292d31',zerolinecolor='#777'),
        xaxis=dict(title=None,gridcolor='#202427',showgrid=True))
    if headline == 'Real GDP':
        ticks = frame.index[::max(1,(len(frame)+11)//12)]
        fig.update_xaxes(tickmode='array',tickvals=ticks,ticktext=[f'Q{d.quarter} {d.year}' for d in ticks])
    return fig
