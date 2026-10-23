"""Reviewed household risk catalog. No preset signals or proprietary-only feeds."""
from dataclasses import dataclass

DOMAINS = {
    'equity': ('Equity risk', 'Market prices and volatility help frame the risk of selling investments during a downturn. Price indexes exclude dividends.', 'Review near-term withdrawals and diversification against your own plan.'),
    'growth': ('Recession & growth risk', 'Employment, income and production describe the backdrop for household earnings. These releases lag and are revised.', 'Consider how an income interruption would affect planned spending and cash reserves.'),
    'inflation': ('Inflation risk', 'Consumer prices and energy costs affect purchasing power. Your spending mix may differ from the national basket.', 'Compare essential-spending assumptions with realized price changes.'),
    'rates': ('Interest-rate risk', 'Rates affect borrowing costs, savings income and bond prices. A higher yield helps savers but can reduce existing bond values.', 'Review debt reset dates, reinvestment needs and bond maturity exposure.'),
    'credit': ('Credit stress', 'Lending standards, spreads and delinquencies describe financing pressure. They are not forecasts of individual defaults.', 'Review liquidity needs and credit quality before relying on refinancing.'),
    'housing': ('Housing conditions', 'Mortgage costs, supply and prices shape affordability. National measures can differ substantially from local conditions.', 'Stress-test housing costs and the timing of a move against local prices.'),
}

# Maximum observation age includes the dated reference period and release lag.
# Operational budgets, not claims about official release deadlines.
AGE_BUDGET = {'daily': 10, 'weekly': 21, 'monthly': 100, 'quarterly': 210}

# Case-Shiller reference months are released two months later, on the last
# Tuesday. The next month's release plus a 7-day operational grace can reach
# 129 days from the dated reference month. Assessment uses that calendar
# deadline, not a blanket 130-day pass. Other monthly budgets stay at 100.
CASE_SHILLER_GRACE_DAYS = 7
CASE_SHILLER_SOURCE = 'https://www.spglobal.com/spdji/en/index-family/indicators/sp-cotality-case-shiller/'

@dataclass(frozen=True)
class Indicator:
    series_id: str
    name: str
    domain: str
    frequency: str
    raw_unit: str
    transform: str = 'level'
    source: str = 'fred'
    reliability: str = 'official'
    note: str = ''

    @property
    def unit(self):
        return '% year over year' if self.transform == 'yoy' else self.raw_unit

    @property
    def max_age_days(self):
        return 130 if self.series_id == 'CSUSHPINSA' else AGE_BUDGET[self.frequency]

    @property
    def source_url(self):
        if self.source == 'fred':
            return f'https://fred.stlouisfed.org/series/{self.series_id}'
        return 'https://www.eia.gov/electricity/data/browser/'

# series | readable name | domain | frequency | raw unit | transform | reliability
_ROWS = '''
SP500|S&P 500 price index|equity|daily|index|yoy|third-party
NASDAQCOM|Nasdaq Composite price index|equity|daily|index|yoy|third-party
DJIA|Dow Jones Industrial Average|equity|daily|index|yoy|third-party
VIXCLS|CBOE equity volatility index|equity|daily|index|level|third-party
A191RL1Q225SBEA|Real GDP growth (annualized quarter)|growth|quarterly|% annualized|level|official
PAYEMS|Nonfarm payroll employment|growth|monthly|thousands of jobs|yoy|official
UNRATE|Unemployment rate|growth|monthly|%|level|official
IC4WSA|Initial claims, four-week average|growth|weekly|people|level|official
CCSA|Continued unemployment claims|growth|weekly|people|level|official
INDPRO|Industrial production|growth|monthly|index|yoy|official
TCU|Total capacity utilization|growth|monthly|%|level|official
PCE|Nominal personal consumption|growth|monthly|billions of dollars, annual rate|yoy|official
RSXFS|Retail sales excluding food services|growth|monthly|millions of dollars|yoy|official
PI|Nominal personal income|growth|monthly|billions of dollars, annual rate|yoy|official
PSAVERT|Personal saving rate|growth|monthly|%|level|official
TOTALSA|Total vehicle sales|growth|monthly|millions, annual rate|level|official
CIVPART|Labor force participation|growth|monthly|%|level|official
JTSJOL|Job openings|growth|monthly|thousands|level|official
JTSQUR|Job quits rate|growth|monthly|%|level|official
TEMPHELPS|Temporary help employment|growth|monthly|thousands of jobs|yoy|official
MANEMP|Manufacturing employment|growth|monthly|thousands of jobs|yoy|official
DGORDER|Durable goods orders|growth|monthly|millions of dollars|yoy|official
AMTMNO|Manufacturers new orders|growth|monthly|millions of dollars|yoy|official
NEWORDER|Nondefense capital goods orders excluding aircraft|growth|monthly|millions of dollars|yoy|official
ISRATIO|Business inventory-to-sales ratio|growth|monthly|ratio|level|official
OPHPBS|Nonfarm business labor productivity|growth|quarterly|index|yoy|official
GACDFSA066MSFRBPHI|Philadelphia Fed manufacturing activity|growth|monthly|diffusion index|level|official
GACDISA066MSFRBNY|Empire State manufacturing activity|growth|monthly|diffusion index|level|official
MCUMFN|Manufacturing capacity utilization|growth|monthly|%|level|official
CPIAUCSL|Consumer price inflation|inflation|monthly|index|yoy|official
CPILFESL|Core consumer price inflation|inflation|monthly|index|yoy|official
PCEPI|PCE price inflation|inflation|monthly|index|yoy|official
PCEPILFE|Core PCE price inflation|inflation|monthly|index|yoy|official
CUSR0000SEHA|Rent of primary residence|inflation|monthly|index|yoy|official
CES0500000003|Average hourly earnings|inflation|monthly|dollars per hour|yoy|official
ULCNFB|Nonfarm business unit labor costs|inflation|quarterly|index|yoy|official
T5YIFR|Five-year forward inflation compensation|inflation|daily|%|level|official
T10YIE|Ten-year inflation compensation|inflation|daily|%|level|official
T5YIE|Five-year inflation compensation|inflation|daily|%|level|official
DCOILWTICO|WTI crude oil spot price|inflation|daily|dollars per barrel|level|official
DCOILBRENTEU|Brent crude oil spot price|inflation|daily|dollars per barrel|level|official
DHHNGSP|Henry Hub natural gas spot price|inflation|daily|dollars per million BTU|level|official
GASREGW|Regular gasoline retail price|inflation|weekly|dollars per gallon|level|official
DFF|Effective federal funds rate|rates|daily|%|level|official
SOFR|Secured overnight financing rate|rates|daily|%|level|official
DGS3MO|Three-month Treasury yield|rates|daily|%|level|official
DGS2|Two-year Treasury yield|rates|daily|%|level|official
DGS5|Five-year Treasury yield|rates|daily|%|level|official
DGS10|Ten-year Treasury yield|rates|daily|%|level|official
DGS30|Thirty-year Treasury yield|rates|daily|%|level|official
T10Y2Y|Ten-year minus two-year Treasury yield|rates|daily|percentage points|level|official
T10Y3M|Ten-year minus three-month Treasury yield|rates|daily|percentage points|level|official
DFII10|Ten-year inflation-protected Treasury real yield|rates|daily|%|level|official
WALCL|Federal Reserve total assets|rates|weekly|millions of dollars|yoy|official
BAMLC0A0CM|US investment-grade corporate option-adjusted spread|credit|daily|percentage points|level|third-party
BAMLH0A0HYM2|US high-yield corporate option-adjusted spread|credit|daily|percentage points|level|third-party
DRTSCILM|Banks tightening large-firm business lending standards|credit|quarterly|net % of banks|level|official
BUSLOANS|Commercial and industrial bank loans|credit|monthly|billions of dollars|yoy|official
DRCLACBS|Consumer loan delinquency rate|credit|quarterly|%|level|official
DRCCLACBS|Credit card delinquency rate|credit|quarterly|%|level|official
DRALACBS|All bank loan delinquency rate|credit|quarterly|%|level|official
DRSFRMACBS|Single-family mortgage delinquency rate|credit|quarterly|%|level|official
TOTALSL|Total consumer credit outstanding|credit|monthly|millions of dollars|yoy|official
STLFSI4|St. Louis financial stress index|credit|weekly|index|level|official
NFCI|Chicago Fed national financial conditions index|credit|weekly|index|level|official
TDSP|Household debt service share of disposable income|credit|quarterly|%|level|official
HSN1F|New single-family home sales|housing|monthly|thousands, annual rate|level|official
HOUST|Housing starts|housing|monthly|thousands, annual rate|level|official
PERMIT|Housing permits|housing|monthly|thousands, annual rate|level|official
CSUSHPINSA|Case-Shiller national home prices|housing|monthly|index|yoy|third-party
USSTHPI|FHFA all-transactions home prices|housing|quarterly|index|yoy|official
MORTGAGE30US|Thirty-year fixed mortgage rate|housing|weekly|%|level|third-party
MORTGAGE15US|Fifteen-year fixed mortgage rate|housing|weekly|%|level|third-party
MSACSR|Months supply of new homes|housing|monthly|months|level|official
RRVRUSQ156N|Rental vacancy rate|housing|quarterly|%|level|official
TTLCONS|Total construction spending|housing|monthly|millions of dollars, annual rate|yoy|official
'''

INDICATORS = tuple(Indicator(*row.split('|')[:5], transform=row.split('|')[5],
                             reliability=row.split('|')[6])
                   for row in _ROWS.strip().splitlines()) + (
    Indicator('ELEC.PRICE.US-RES.M', 'Residential electricity price', 'inflation',
              'monthly', 'cents per kWh', source='eia',
              note='US residential average; actual utility tariffs differ.'),
)
BY_ID = {i.series_id: i for i in INDICATORS}

# Small, explicit watch rules. Everything else is descriptive context.
# (operator, threshold, reason); no opaque composite or inferred buy/sell action.
WATCH_RULES = {
    'VIXCLS': ('gt', 30, 'Elevated implied equity volatility'),
    'T10Y2Y': ('lt', 0, 'Inverted Treasury curve'),
    'T10Y3M': ('lt', 0, 'Inverted Treasury curve'),
    'STLFSI4': ('gt', 0, 'Financial stress above the index historical average'),
    'NFCI': ('gt', 0, 'Financial conditions tighter than the index historical average'),
    'A191RL1Q225SBEA': ('lt', 0, 'Real output contracted this quarter'),
    'PCEPI': ('gt', 2, 'PCE inflation above the longer-run 2% benchmark'),
}


# References establish the series' meaning; VIX 30 remains an operational app rule.
RULE_SOURCES = {
    'VIXCLS': ('App watch threshold', 'https://www.cboe.com/tradable-products/volatility-trading/',
               'VIX measures expected volatility, not its direction; 30 is not an official crisis boundary.'),
    'T10Y2Y': ('Curve inversion', 'https://fred.stlouisfed.org/series/T10Y2Y',
               'An inverted curve has variable lead times; no recession date or probability is inferred.'),
    'T10Y3M': ('Curve inversion', 'https://fred.stlouisfed.org/series/T10Y3M',
               'An inverted curve is a risk context signal, not a trading instruction.'),
    'STLFSI4': ('Historical-average reference', 'https://fred.stlouisfed.org/series/STLFSI4',
               'Above zero means above-average measured stress, not a calibrated crisis classification.'),
    'NFCI': ('Historical-average reference', 'https://www.chicagofed.org/research/data/nfci/background',
               'Above zero means tighter-than-average financial conditions; below zero does not mean no risk.'),
    'A191RL1Q225SBEA': ('Real-output contraction', 'https://fred.stlouisfed.org/series/A191RL1Q225SBEA',
               'A single negative quarter does not establish a recession; estimates are revised.'),
    'PCEPI': ('Longer-run policy benchmark', 'https://www.federalreserve.gov/faqs/economy_14400.htm',
               'The 2% objective is for headline PCE inflation over the longer run, not a monthly policy trigger.'),
}
