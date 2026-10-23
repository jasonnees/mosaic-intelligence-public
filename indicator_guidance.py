"""Series-specific interpretation. Direction describes change, never a forecast."""
from dataclasses import dataclass
import math
import pandas as pd
from risk_catalog import BY_ID
from risk_data import assess, transform_frame


@dataclass(frozen=True)
class Guide:
    rising: str
    falling: str
    caution: str


# Each active series has an explicit interpretation and limitation.
_ROWS = '''
SP500|Large-cap price growth strengthened|Large-cap price growth weakened|Price return excludes dividends; a rising index does not establish fair valuation.
NASDAQCOM|Nasdaq price growth strengthened|Nasdaq price growth weakened|Index concentration can dominate the move; price return excludes dividends.
DJIA|Dow price growth strengthened|Dow price growth weakened|A price-weighted 30-stock index is not the whole equity market; dividends are excluded.
VIXCLS|Options imply more near-term volatility|Options imply less near-term volatility|VIX is non-directional; 30 is an app watch threshold, not a Cboe crisis boundary.
A191RL1Q225SBEA|Annualized quarterly real growth improved|Annualized quarterly real growth weakened|One negative quarter does not by itself establish a recession; annualized growth is not year-over-year growth.
PAYEMS|Payroll job growth strengthened|Payroll job growth slowed|This is growth in jobs, not people; payrolls are revised and slowing growth may remain positive.
UNRATE|The unemployment share increased|The unemployment share decreased|Participation changes matter; a lower rate alone does not prove a stronger labor market.
IC4WSA|More initial jobless claims on the four-week average|Fewer initial jobless claims on the four-week average|Claims cover eligible insured workers; seasonal adjustments and revisions can move the series.
CCSA|More people remained on insured unemployment|Fewer people remained on insured unemployment|Benefit exhaustion and eligibility changes can reduce claims without an improvement in hiring.
INDPRO|Industrial output growth strengthened|Industrial output growth weakened|Industry is only part of the economy; this is year-over-year growth, not the output level.
TCU|More total industrial capacity was in use|Less total industrial capacity was in use|High utilization can reflect demand or supply constraints; there is no universal overheating cutoff.
PCE|Nominal consumption growth strengthened|Nominal consumption growth weakened|Nominal spending includes inflation; it does not establish growth in real consumption.
RSXFS|Retail sales growth strengthened|Retail sales growth weakened|Sales are nominal and exclude food services; this is not a measure of total consumption.
PI|Nominal personal-income growth strengthened|Nominal personal-income growth weakened|Inflation and transfers affect purchasing power; aggregate growth does not describe a typical household.
PSAVERT|A larger share of disposable income was saved|A smaller share of disposable income was saved|A falling aggregate saving rate can reflect spending strength or pressure; it is not a household cash balance.
TOTALSA|Vehicle sales increased|Vehicle sales decreased|Sales are an annualized rate; financing costs, inventories and incentives can alter demand.
CIVPART|More of the population participated in the labor force|Less of the population participated in the labor force|Aging and demographics affect participation; interpret alongside unemployment and employment.
JTSJOL|Reported job openings increased|Reported job openings decreased|Vacancies are not completed hires; survey estimates are revised and differ from online postings.
JTSQUR|Workers quit jobs at a higher rate|Workers quit jobs at a lower rate|Quits may reflect worker confidence but vary by industry; they do not directly measure wage growth.
TEMPHELPS|Temporary-help employment growth strengthened|Temporary-help employment growth weakened|Staffing-sector changes can be structural; this is an early-cycle clue, not a recession declaration.
MANEMP|Manufacturing job growth strengthened|Manufacturing job growth weakened|Manufacturing is one employment sector; productivity and automation also affect hiring.
DGORDER|Nominal durable-goods order growth strengthened|Nominal durable-goods order growth weakened|Aircraft and defense orders can be volatile; orders are not completed shipments or real investment.
AMTMNO|Nominal manufacturing-order growth strengthened|Nominal manufacturing-order growth weakened|Inflation changes nominal orders; broader orders should not be treated as a business-investment-only measure.
NEWORDER|Core capital-goods order growth strengthened|Core capital-goods order growth weakened|Orders exclude defense and aircraft but remain nominal; orders are not actual capital spending.
ISRATIO|Inventories increased relative to sales|Inventories decreased relative to sales|A rising ratio can reflect weak sales or intentional restocking; read both components.
OPHPBS|Labor-productivity growth strengthened|Labor-productivity growth weakened|Quarterly productivity is volatile and revised; it does not directly determine a household wage.
GACDFSA066MSFRBPHI|Philadelphia manufacturers reported a stronger activity balance|Philadelphia manufacturers reported a weaker activity balance|A regional diffusion index measures breadth, not the percent change in national output; zero is its neutral balance.
GACDISA066MSFRBNY|New York manufacturers reported a stronger activity balance|New York manufacturers reported a weaker activity balance|A regional survey can diverge from national production; zero is its neutral balance, not an output-growth rate.
MCUMFN|More manufacturing capacity was in use|Less manufacturing capacity was in use|Manufacturing utilization differs from total industry; supply disruptions can change capacity as well as output.
CPIAUCSL|Consumer-price inflation accelerated|Consumer-price inflation slowed|Slower positive inflation means prices still rose; CPI is not the Fed's PCE inflation target.
CPILFESL|Core CPI inflation accelerated|Core CPI inflation slowed|Core excludes food and energy, not shelter; slower inflation does not imply lower prices.
PCEPI|PCE inflation accelerated|PCE inflation slowed|The Fed's 2% objective is a longer-run headline PCE benchmark; one observation is not a policy forecast.
PCEPILFE|Core PCE inflation accelerated|Core PCE inflation slowed|Core excludes food and energy; the formal 2% objective refers to headline PCE over the longer run.
CUSR0000SEHA|Measured rent inflation accelerated|Measured rent inflation slowed|The rent index reflects the stock of occupied rentals and can lag asking rents for new leases.
CES0500000003|Nominal hourly-earnings growth strengthened|Nominal hourly-earnings growth weakened|Average pay is affected by workforce composition and excludes an inflation adjustment.
ULCNFB|Unit-labor-cost growth strengthened|Unit-labor-cost growth weakened|Costs depend on compensation and productivity; they do not translate one-for-one into consumer-price inflation.
T5YIFR|Forward inflation compensation increased|Forward inflation compensation decreased|Market compensation includes risk and liquidity premiums; this is not a pure inflation forecast.
T10YIE|Ten-year inflation compensation increased|Ten-year inflation compensation decreased|Breakevens contain risk and liquidity premiums; the horizon is ten years, not next month's inflation.
T5YIE|Five-year inflation compensation increased|Five-year inflation compensation decreased|Breakevens reflect market pricing as well as expected inflation; do not treat them as a survey forecast.
DCOILWTICO|WTI crude became more expensive|WTI crude became less expensive|Oil can move on demand or supply; a lower price can reflect economic weakness rather than benign inflation.
DCOILBRENTEU|Brent crude became more expensive|Brent crude became less expensive|Brent is a global crude benchmark; taxes, refining and distribution separate it from retail fuel costs.
DHHNGSP|US wholesale natural gas became more expensive|US wholesale natural gas became less expensive|Henry Hub is not a household utility tariff; weather and storage cause large seasonal moves.
GASREGW|Retail gasoline became more expensive|Retail gasoline became less expensive|The national average differs from local prices and does not include household differences in fuel use.
DFF|Overnight policy-linked borrowing costs increased|Overnight policy-linked borrowing costs decreased|This is the effective traded rate, not the upper or lower bound of the FOMC target range.
SOFR|Secured overnight funding costs increased|Secured overnight funding costs decreased|SOFR reflects Treasury-collateralized borrowing; it is not a consumer loan rate or unsecured credit spread.
DGS3MO|Three-month Treasury yields increased|Three-month Treasury yields decreased|Higher yields help new savers but can lower existing bond prices; maturity and reinvestment needs matter.
DGS2|Two-year Treasury yields increased|Two-year Treasury yields decreased|Yields reflect policy expectations and risk premiums; falling yields can also indicate weaker growth.
DGS5|Five-year Treasury yields increased|Five-year Treasury yields decreased|A yield move is not a total bond return; duration determines price sensitivity.
DGS10|Ten-year Treasury yields increased|Ten-year Treasury yields decreased|Nominal yields combine inflation, real rates and term premiums; they are not a pure growth forecast.
DGS30|Thirty-year Treasury yields increased|Thirty-year Treasury yields decreased|Long-maturity bond prices are sensitive to yield moves; higher nominal yields do not guarantee higher real returns.
T10Y2Y|The 10-year minus 2-year curve spread increased|The 10-year minus 2-year curve spread decreased|A rising spread can still be inverted; steepening after inversion does not establish that recession risk has passed.
T10Y3M|The 10-year minus 3-month curve spread increased|The 10-year minus 3-month curve spread decreased|Inversion has variable lead times; it does not date a recession or prescribe a trading action.
DFII10|Ten-year inflation-protected real yields increased|Ten-year inflation-protected real yields decreased|This is a market yield, not realized inflation-adjusted return; liquidity and term premiums matter.
WALCL|Year-over-year Fed balance-sheet growth strengthened|Year-over-year Fed balance-sheet growth weakened|Total assets are not a complete measure of market liquidity; Treasury cash and reverse repos also matter.
BAMLC0A0CM|Investment-grade corporate spreads widened|Investment-grade corporate spreads narrowed|Spreads are percentage points over the benchmark curve, not corporate yields or default probabilities.
BAMLH0A0HYM2|High-yield corporate spreads widened|High-yield corporate spreads narrowed|High yield is sensitive to credit composition; widening signals repricing, not a quantified default forecast.
DRTSCILM|The net share of banks tightening business-loan standards increased|The net share of banks tightening business-loan standards decreased|A positive reading means net tightening; a decline can mean less tightening rather than net easing.
BUSLOANS|Business-bank-loan growth strengthened|Business-bank-loan growth weakened|Borrowing can rise because of demand or liquidity stress; the series does not isolate new lending standards.
DRCLACBS|Consumer-loan delinquency increased|Consumer-loan delinquency decreased|This is a quarterly bank-loan measure; it is not an auto-loan-specific series or an individual default forecast.
DRCCLACBS|Credit-card delinquency increased|Credit-card delinquency decreased|Bank-reported delinquency differs from charge-offs; lending mix and revisions can affect the rate.
DRALACBS|Delinquency across bank loans increased|Delinquency across bank loans decreased|This covers multiple loan categories; it must not be labeled an auto-loan or household-only indicator.
DRSFRMACBS|Single-family mortgage delinquency increased|Single-family mortgage delinquency decreased|This covers mortgages on bank books and does not describe every lender or local housing market.
TOTALSL|Consumer-credit growth strengthened|Consumer-credit growth weakened|Outstanding consumer credit excludes mortgages; growth can reflect financing needs as well as spending.
STLFSI4|Measured financial stress increased|Measured financial stress decreased|Zero is the index's historical-average reference; below zero does not mean no financial risk.
NFCI|Financial conditions tightened relative to the index baseline|Financial conditions loosened relative to the index baseline|Zero represents historical-average conditions; the NFCI is not the growth-adjusted ANFCI.
TDSP|Debt payments absorbed more disposable income|Debt payments absorbed less disposable income|An aggregate debt-service ratio hides differences across households and loan terms.
HSN1F|New single-family home sales increased|New single-family home sales decreased|Monthly estimates are annualized, volatile and revised; they exclude existing-home sales.
HOUST|Housing starts increased|Housing starts decreased|Starts include multifamily construction and are annualized; regional supply conditions can differ.
PERMIT|Housing permits increased|Housing permits decreased|Permits indicate authorizations, not completed homes; not every permit becomes a start.
CSUSHPINSA|National home-price growth strengthened|National home-price growth weakened|This non-seasonally-adjusted repeat-sales index has a publication lag; national changes differ from local prices.
USSTHPI|FHFA home-price growth strengthened|FHFA home-price growth weakened|The all-transactions index includes appraisal-based information and differs from FHFA's purchase-only index.
MORTGAGE30US|Thirty-year mortgage financing became more expensive|Thirty-year mortgage financing became less expensive|A survey average is not a loan quote; borrower credit, points and down payment affect the offered rate.
MORTGAGE15US|Fifteen-year mortgage financing became more expensive|Fifteen-year mortgage financing became less expensive|A shorter maturity often raises monthly payments despite a lower rate; the series is a survey average.
MSACSR|New-home inventory rose relative to the sales pace|New-home inventory fell relative to the sales pace|Months supply can rise because sales fall; this is new-home supply, not the entire housing market.
RRVRUSQ156N|The rental vacancy rate increased|The rental vacancy rate decreased|Higher vacancy can ease rent pressure but weaken landlord income; national rates hide local differences.
TTLCONS|Nominal construction-spending growth strengthened|Nominal construction-spending growth weakened|Spending includes price changes and multiple sectors; it is not a count of housing starts.
ELEC.PRICE.US-RES.M|Average residential electricity became more expensive|Average residential electricity became less expensive|The monthly national average reflects usage and customer mix; it is not a fixed utility tariff.
'''
GUIDES = {sid: Guide(rising, falling, caution)
          for sid, rising, falling, caution in (row.split('|') for row in _ROWS.strip().splitlines())}


@dataclass(frozen=True)
class Direction:
    label: str
    change: float | None
    prior_date: str | None
    current_date: str | None
    explanation: str


def direction(frame, indicator, now=None):
    observation = assess(frame, indicator, now)
    if observation.status != 'fresh':
        return Direction('Not evaluated', None, None, observation.observed_at,
                         f'{observation.status.capitalize()}: {observation.detail}. Direction is withheld.')
    values = transform_frame(frame, indicator)
    latest = values.iloc[-1]
    offset = pd.DateOffset(years=1) if indicator.frequency == 'quarterly' else pd.DateOffset(months=3)
    target = latest['date'] - offset
    prior = values[values['date'] <= target]
    tolerance = {'daily': 10, 'weekly': 21, 'monthly': 40, 'quarterly': 100}[indicator.frequency]
    if prior.empty:
        return Direction('No comparison', None, None, observation.observed_at, 'Not enough history for the comparison window.')
    base = prior.iloc[-1]
    if (target - base['date']).days > tolerance or not pd.notna(base[indicator.series_id]) or not math.isfinite(base[indicator.series_id]):
        return Direction('No comparison', None, None, observation.observed_at, 'The comparison-period observation is missing or too far from the target date.')
    delta = float(latest[indicator.series_id] - base[indicator.series_id])
    guide = GUIDES[indicator.series_id]
    unchanged = math.isclose(delta, 0, rel_tol=0, abs_tol=1e-10)
    label = 'Unchanged' if unchanged else 'Rising' if delta > 0 else 'Falling'
    explanation = 'No measured change over the comparison window.' if unchanged else guide.rising if delta > 0 else guide.falling
    return Direction(label, 0.0 if unchanged else delta, base['date'].date().isoformat(), observation.observed_at, explanation)


def data_warning(observation, indicator):
    """An actionable data warning for every invalid state; no market inference."""
    if observation.status == 'stale':
        return (f'Last observation {observation.observed_at}: {observation.age_days} days old, '
                f'{observation.age_days - indicator.max_age_days} days beyond the {indicator.max_age_days}-day budget. '
                'Refresh or inspect the source release; market warnings and direction are withheld.')
    if observation.status == 'missing':
        return 'No usable observations. Check the API key, source availability and connection; no substitute signal is shown.'
    if observation.status == 'invalid':
        return 'The latest observation is future-dated. Check source dates; it cannot support a current signal.'
    if observation.status == 'insufficient history':
        return 'The latest period has no usable prior-year comparison. Load more history or inspect the source; an older growth value is not substituted.'
    return ''


assert set(GUIDES) == set(BY_ID), 'Every active indicator must have reviewed guidance'
