"""
Market Risk Explorer — Configuration
Legacy integration metadata retained for optional ingestion tools
API Keys stored as environment variables for security
"""
import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# API KEYS — Use environment variables in production
# =============================================================================

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
BLS_API_KEY = os.environ.get("BLS_API_KEY", "")
EIA_API_KEY = os.environ.get("EIA_API_KEY", "")
BEA_API_KEY = os.environ.get("BEA_API_KEY", "")
# Treasury API does not require a key

# =============================================================================
# AWS CONFIGURATION
# =============================================================================

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "mosaic-intelligence-datalake")
LAMBDA_FUNCTION_NAME = os.environ.get("LAMBDA_FUNCTION_NAME", "mosaic-orchestrator-prod")
S3_RAW_PREFIX = os.environ.get("S3_RAW_PREFIX", "raw")

# Data source mode: "s3" reads from datalake, "api" calls APIs directly
DATA_SOURCE_MODE = os.environ.get("DATA_SOURCE_MODE", "api")

# AWS Data Exchange (Rearc FRED products)
DATA_EXCHANGE_ENABLED = os.environ.get("DATA_EXCHANGE_ENABLED", "false").lower() == "true"
DATA_EXCHANGE_PROVIDER = "rearc"
DATA_EXCHANGE_S3_PREFIX = "raw/source=data_exchange"

# =============================================================================
# FRED INDICATORS — 108 series across 6 dashboard tabs
# =============================================================================

FRED_INDICATORS = {
    "consumer": {  # 16 indicators
        "ICSA": {"name": "Initial Jobless Claims", "frequency": "weekly", "unit": "thousands"},
        "CCSA": {"name": "Continuing Claims", "frequency": "weekly", "unit": "thousands"},
        "RSXFS": {"name": "Retail Sales (ex Food Services)", "frequency": "monthly", "unit": "millions USD"},
        "UMCSENT": {"name": "Consumer Sentiment", "frequency": "monthly", "unit": "index"},
        "PSAVERT": {"name": "Personal Savings Rate", "frequency": "monthly", "unit": "percent"},
        "TOTALSL": {"name": "Consumer Credit", "frequency": "monthly", "unit": "billions USD"},
        "PCE": {"name": "Personal Consumption Expenditures", "frequency": "monthly", "unit": "billions USD"},
        "DSPIC96": {"name": "Real Disposable Personal Income", "frequency": "monthly", "unit": "billions USD"},
        "CCLACBW027SBOG": {"name": "CC & Revolving Balances", "frequency": "monthly", "unit": "billions USD"},
        "RCCCBSHRMIN": {"name": "CC Accounts: Min Payment Only Share", "frequency": "quarterly", "unit": "percent"},
        "RCCCBACTDPD90P": {"name": "CC Accounts: 90+ Days Past Due", "frequency": "quarterly", "unit": "percent"},
        "DRCCLACBS": {"name": "CC Delinquency Rate, All Banks", "frequency": "quarterly", "unit": "percent"},
        "DRCLACBS": {"name": "Consumer Loan Delinquency Rate", "frequency": "quarterly", "unit": "percent"},
        "TDSP": {"name": "Household Debt Service Ratio", "frequency": "quarterly", "unit": "percent"},
        "TERMCBCCALLNS": {"name": "Avg CC Interest Rate, All Accounts", "frequency": "quarterly", "unit": "percent"},
        "MEHOINUSA672N": {"name": "Real Median Household Income", "frequency": "annual", "unit": "dollars"},
    },
    "smb": {  # 8 indicators
        "BABATOTALSAUS": {"name": "Business Applications", "frequency": "weekly", "unit": "applications"},
        "BUSLOANS": {"name": "Commercial & Industrial Loans", "frequency": "weekly", "unit": "billions USD"},
        "ANFCI": {"name": "Chicago Fed Financial Conditions", "frequency": "weekly", "unit": "index"},
        "STLFSI4": {"name": "St. Louis Fed Financial Stress Index", "frequency": "weekly", "unit": "index"},
        "DRTSCIS": {"name": "Loan Officer Survey: C&I Tightening", "frequency": "quarterly", "unit": "percent"},
        "DRTSSP": {"name": "Loan Officer Survey: Spreads", "frequency": "quarterly", "unit": "percent"},
        "MNFCTRIRSA": {"name": "Manufacturers Inventories/Sales Ratio", "frequency": "monthly", "unit": "ratio"},
        "RETAILIRSA": {"name": "Retail Inventories/Sales Ratio", "frequency": "monthly", "unit": "ratio"},
    },
    "macro": {  # 45 indicators
        # Interest Rates & Yield Curve
        "DGS10": {"name": "10-Year Treasury Yield", "frequency": "daily", "unit": "percent"},
        "DGS2": {"name": "2-Year Treasury Yield", "frequency": "daily", "unit": "percent"},
        "DGS30": {"name": "30-Year Treasury Yield", "frequency": "daily", "unit": "percent"},
        "DGS5": {"name": "5-Year Treasury Yield", "frequency": "daily", "unit": "percent"},
        "DGS1": {"name": "1-Year Treasury Yield", "frequency": "daily", "unit": "percent"},
        "DTB3": {"name": "3-Month Treasury Bill", "frequency": "daily", "unit": "percent"},
        "T10Y2Y": {"name": "10Y-2Y Spread", "frequency": "daily", "unit": "percent"},
        "T10Y3M": {"name": "10Y-3M Spread", "frequency": "daily", "unit": "percent"},
        "DFF": {"name": "Fed Funds Rate", "frequency": "daily", "unit": "percent"},
        "SOFR": {"name": "SOFR Rate", "frequency": "daily", "unit": "percent"},
        # Credit Spreads
        "BAMLH0A0HYM2": {"name": "High Yield Spread (ICE BofA)", "frequency": "daily", "unit": "percent"},
        "BAMLC0A0CM": {"name": "Corporate Bond Spread", "frequency": "daily", "unit": "percent"},
        "BAMLC0A1CAAA": {"name": "AAA Corporate Spread", "frequency": "daily", "unit": "percent"},
        "BAMLC0A4CBBB": {"name": "BBB Corporate Spread", "frequency": "daily", "unit": "percent"},
        "TEDRATE": {"name": "TED Spread", "frequency": "daily", "unit": "percent"},
        # Inflation
        "CPIAUCSL": {"name": "CPI (All Urban)", "frequency": "monthly", "unit": "index"},
        "CPIFABSL": {"name": "CPI: Food & Beverages", "frequency": "monthly", "unit": "index"},
        "CUUR0000SAH": {"name": "CPI: Shelter", "frequency": "monthly", "unit": "index"},
        "CPIENGSL": {"name": "CPI: Energy", "frequency": "monthly", "unit": "index"},
        "CPIMEDSL": {"name": "CPI: Medical Care", "frequency": "monthly", "unit": "index"},
        "PCEPI": {"name": "PCE Price Index", "frequency": "monthly", "unit": "index"},
        "T5YIE": {"name": "5-Year Breakeven Inflation", "frequency": "daily", "unit": "percent"},
        "T10YIE": {"name": "10-Year Breakeven Inflation", "frequency": "daily", "unit": "percent"},
        "T5YIFR": {"name": "5Y5Y Forward Inflation Expectation", "frequency": "daily", "unit": "percent"},
        "MICH": {"name": "Michigan Inflation Expectations", "frequency": "monthly", "unit": "percent"},
        # Employment & Growth
        "UNRATE": {"name": "Unemployment Rate", "frequency": "monthly", "unit": "percent"},
        "GDPC1": {"name": "Real GDP", "frequency": "quarterly", "unit": "billions USD"},
        "A939RX0Q048SBEA": {"name": "Real GDP Per Capita", "frequency": "quarterly", "unit": "dollars"},
        "INDPRO": {"name": "Industrial Production", "frequency": "monthly", "unit": "index"},
        "CIVPART": {"name": "Labor Force Participation Rate", "frequency": "monthly", "unit": "percent"},
        "PAYEMS": {"name": "Total Nonfarm Payrolls", "frequency": "monthly", "unit": "thousands"},
        # Money Supply & Financial
        "M2SL": {"name": "M2 Money Supply", "frequency": "monthly", "unit": "billions USD"},
        "VIXCLS": {"name": "VIX", "frequency": "daily", "unit": "index"},
        "DTWEXBGS": {"name": "Trade Weighted Dollar Index (Broad)", "frequency": "daily", "unit": "index"},
        "DEXUSEU": {"name": "USD/EUR Exchange Rate", "frequency": "daily", "unit": "rate"},
        # Fiscal & Government
        "GFDEBTN": {"name": "Federal Debt Total Public", "frequency": "quarterly", "unit": "millions USD"},
        "FYFRGDA188S": {"name": "Federal Revenue as % of GDP", "frequency": "annual", "unit": "percent"},
        "MTSDS133FMS": {"name": "Federal Surplus or Deficit", "frequency": "monthly", "unit": "millions USD"},
        # GDP Components (Leading Indicators)
        "PRFI": {"name": "Private Residential Fixed Investment", "frequency": "quarterly", "unit": "billions USD"},
        "PCEDG": {"name": "PCE: Durable Goods", "frequency": "monthly", "unit": "billions USD"},
        "PCEND": {"name": "PCE: Nondurable Goods", "frequency": "monthly", "unit": "billions USD"},
        "PCES": {"name": "PCE: Services", "frequency": "monthly", "unit": "billions USD"},
        "NETEXP": {"name": "Net Exports", "frequency": "quarterly", "unit": "billions USD"},
        "CBI": {"name": "Change in Private Inventories", "frequency": "quarterly", "unit": "billions USD"},
        "GCE": {"name": "Government Consumption & Investment", "frequency": "quarterly", "unit": "billions USD"},
    },
    "housing": {  # 16 indicators
        "EXHOSLUSM495S": {"name": "Existing Home Sales", "frequency": "monthly", "unit": "millions"},
        "HSN1F": {"name": "New Home Sales", "frequency": "monthly", "unit": "thousands"},
        "HOUST": {"name": "Housing Starts", "frequency": "monthly", "unit": "thousands"},
        "PERMIT": {"name": "Building Permits", "frequency": "monthly", "unit": "thousands"},
        "MSPUS": {"name": "Median Sales Price", "frequency": "quarterly", "unit": "dollars"},
        "CSUSHPINSA": {"name": "Case-Shiller National HPI", "frequency": "monthly", "unit": "index"},
        "USSTHPI": {"name": "FHFA House Price Index", "frequency": "quarterly", "unit": "index"},
        "MORTGAGE30US": {"name": "30-Year Mortgage Rate", "frequency": "weekly", "unit": "percent"},
        "MORTGAGE15US": {"name": "15-Year Mortgage Rate", "frequency": "weekly", "unit": "percent"},
        "MSACSR": {"name": "Monthly Supply of Houses", "frequency": "monthly", "unit": "months"},
        "ACTLISCOUUS": {"name": "Active Listing Count", "frequency": "monthly", "unit": "listings"},
        "FIXHAI": {"name": "Housing Affordability Index", "frequency": "monthly", "unit": "index"},
        "RHORUSQ156N": {"name": "Homeownership Rate", "frequency": "quarterly", "unit": "percent"},
        "DRSFRMACBS": {"name": "Delinquency Rate: RE Loans", "frequency": "quarterly", "unit": "percent"},
        "COMPUTSA": {"name": "Housing Completions", "frequency": "monthly", "unit": "thousands"},
        "RNTSLDMM": {"name": "Median Asking Rent", "frequency": "monthly", "unit": "dollars"},
    },
    "commodities": {  # 14 indicators
        "DCOILWTICO": {"name": "WTI Crude Oil", "frequency": "daily", "unit": "$/barrel"},
        "DCOILBRENTEU": {"name": "Brent Crude Oil", "frequency": "daily", "unit": "$/barrel"},
        "GASREGW": {"name": "Regular Gasoline (FRED fallback)", "frequency": "weekly", "unit": "$/gallon"},
        "PCOPPUSDM": {"name": "Copper (Global Price)", "frequency": "monthly", "unit": "$/mt"},
        "PNICKUSDM": {"name": "Nickel (Global Price)", "frequency": "monthly", "unit": "$/mt"},
        "PALUMUSDM": {"name": "Aluminum (Global Price)", "frequency": "monthly", "unit": "$/mt"},
        "PZINCUSDM": {"name": "Zinc (Global Price)", "frequency": "monthly", "unit": "$/mt"},
        "PLEADUSDM": {"name": "Lead (Global Price)", "frequency": "monthly", "unit": "$/mt"},
        "PTINUSDM": {"name": "Tin (Global Price)", "frequency": "monthly", "unit": "$/mt"},
        "PWHEAMTUSDM": {"name": "Wheat (Global Price)", "frequency": "monthly", "unit": "$/mt"},
        "PMAIZMTUSDM": {"name": "Corn/Maize (Global Price)", "frequency": "monthly", "unit": "$/mt"},
        "PSOYBUSDM": {"name": "Soybeans (Global Price)", "frequency": "monthly", "unit": "$/mt"},
        "PCOFFOTMUSDM": {"name": "Coffee (Global Price)", "frequency": "monthly", "unit": "cents/lb"},
        "PSUGAISAUSDM": {"name": "Sugar (Global Price)", "frequency": "monthly", "unit": "cents/lb"},
    },
}

# =============================================================================
# BLS INDICATORS — 13 series
# =============================================================================

BLS_INDICATORS = {
    "consumer": {  # 2 indicators
        "CES0500000003": {"name": "Avg Hourly Earnings (Private)", "frequency": "monthly", "unit": "dollars"},
        "LNS14000000": {"name": "Unemployment Rate (BLS)", "frequency": "monthly", "unit": "percent"},
    },
    "smb": {  # 2 indicators
        "JTS000000000000000JOL": {"name": "JOLTS Job Openings", "frequency": "monthly", "unit": "thousands"},
        "JTS000000000000000QUR": {"name": "JOLTS Quits Rate", "frequency": "monthly", "unit": "percent"},
    },
    "macro": {  # 9 indicators
        "CUSR0000SA0": {"name": "CPI-U (BLS)", "frequency": "monthly", "unit": "index"},
        "WPUFD4": {"name": "PPI Final Demand", "frequency": "monthly", "unit": "index"},
        "CIU2010000000000A": {"name": "ECI: Wages & Salaries", "frequency": "quarterly", "unit": "index"},
        "CIU2020000000000A": {"name": "ECI: Benefits", "frequency": "quarterly", "unit": "index"},
        "LES1252881600Q": {"name": "Median Weekly Earnings (FT)", "frequency": "quarterly", "unit": "dollars"},
        "CUUR0000SAF1": {"name": "CPI-U: Food at Home", "frequency": "monthly", "unit": "index"},
        "CUUR0000SAF11": {"name": "CPI-U: Food Away from Home", "frequency": "monthly", "unit": "index"},
        "CUUR0000SAM": {"name": "CPI-U: Medical Care", "frequency": "monthly", "unit": "index"},
        "CUUR0000SAH1": {"name": "CPI-U: Rent of Primary Residence", "frequency": "monthly", "unit": "index"},
    },
}

# =============================================================================
# EIA INDICATORS — 5 series
# =============================================================================

EIA_INDICATORS = {
    "consumer": {  # 2 indicators
        "PET.EMM_EPMR_PTE_NUS_DPG.W": {"name": "Retail Gas Price (Regular)", "frequency": "weekly", "unit": "$/gallon"},
        "NG.N3010US3.M": {"name": "Natural Gas Residential Price", "frequency": "monthly", "unit": "$/MCF"},
    },
    "macro": {  # 3 indicators
        "PET.WCESTUS1.W": {"name": "Crude Oil Stocks", "frequency": "weekly", "unit": "thousand barrels"},
        "ELEC.PRICE.US-RES.M": {"name": "Electricity Residential Price", "frequency": "monthly", "unit": "cents/kWh"},
        "PET.EMM_EPD2D_PTE_NUS_DPG.W": {"name": "Retail Diesel Price", "frequency": "weekly", "unit": "$/gallon"},
    },
    "energy": {  # 5 indicators (mapped in indicators_300.py SRC)
        "PET.WGTSTUS1.W": {"name": "Gasoline Inventories", "frequency": "weekly", "unit": "thousand barrels"},
        "PET.WPULRL3S3.W": {"name": "Refinery Utilization", "frequency": "weekly", "unit": "percent"},
        "NG.NW2_EPG0_SWO_R48_BCF.W": {"name": "Natural Gas Storage", "frequency": "weekly", "unit": "BCF"},
        "PET.WGFUPUS2.W": {"name": "US Gasoline Demand", "frequency": "weekly", "unit": "thousand barrels/day"},
        "NG.N9133US2.M": {"name": "LNG Exports", "frequency": "monthly", "unit": "MMCF"},
    },
}

# =============================================================================
# TREASURY INDICATORS
# =============================================================================

TREASURY_INDICATORS = {
    "macro": {
        "yield_curve": {"name": "Treasury Yield Curve", "frequency": "daily", "unit": "percent"},
        "debt_to_penny": {"name": "Total Public Debt", "frequency": "daily", "unit": "billions USD"},
    }
}

# =============================================================================
# BEA INDICATORS (NIPA Tables)
# =============================================================================

BEA_INDICATORS = {
    "macro": {
        "T20100": {"name": "Personal Income & Outlays", "frequency": "quarterly", "table": "NIPA"},
        "T20305": {"name": "PCE by Major Type of Product", "frequency": "quarterly", "table": "NIPA"},
    }
}

# =============================================================================
# DASHBOARD SETTINGS
# =============================================================================

CACHE_EXPIRY_HOURS = {
    "daily": 4,
    "weekly": 24,
    "monthly": 72,
    "quarterly": 168,
}

DEFAULT_LOOKBACK_DAYS = int(os.environ.get("DEFAULT_LOOKBACK_DAYS", 365 * 2))

# Lookback options for sidebar selector
LOOKBACK_OPTIONS = {
    30: "1 Month",
    90: "3 Months",
    180: "6 Months",
    365: "1 Year",
    730: "2 Years",
    1095: "3 Years",
    1825: "5 Years",
    3650: "10 Years",
    7300: "20 Years",
}

# Chart scaling preferences (y-axis ranges)
CHART_SCALES = {
    "UMCSENT": {"ymin": 20, "ymax": 90},       # Consumer Sentiment
    "PCE": {"ymin": 10000, "ymax": 25000},      # PCE in billions
    "TOTALSL": {"ymin": 4000, "ymax": 6000},    # Consumer Credit in billions
}

# =============================================================================
# S3 PATH HELPERS
# =============================================================================

def s3_series_prefix(source: str, series_id: str) -> str:
    """Build the S3 prefix for a given source and series ID"""
    return f"{S3_RAW_PREFIX}/source={source}/series_id={series_id}/"

def s3_latest_key(source: str, series_id: str, year: str, date: str) -> str:
    """Build the full S3 key for a specific data file"""
    return f"{S3_RAW_PREFIX}/source={source}/series_id={series_id}/year={year}/{series_id}_{date}.json"


# =============================================================================
# ALL SERIES REGISTRY (for S3 reader lookups)
# =============================================================================

def get_all_fred_series() -> list:
    """Return flat list of all FRED series IDs across all tabs"""
    series = []
    for tab_series in FRED_INDICATORS.values():
        series.extend(tab_series.keys())
    return list(set(series))

def get_all_bls_series() -> list:
    """Return flat list of all BLS series IDs"""
    series = []
    for tab_series in BLS_INDICATORS.values():
        series.extend(tab_series.keys())
    return list(set(series))

def get_all_eia_series() -> list:
    """Return flat list of all EIA series IDs"""
    series = []
    for tab_series in EIA_INDICATORS.values():
        series.extend(tab_series.keys())
    return list(set(series))

def get_series_metadata(series_id: str) -> dict:
    """Look up metadata for any series ID across all sources"""
    for source_indicators in [FRED_INDICATORS, BLS_INDICATORS, EIA_INDICATORS]:
        for tab, series_dict in source_indicators.items():
            if series_id in series_dict:
                return series_dict[series_id]
    return {}


# =============================================================================
# NOTES
# =============================================================================
# Coverage: 132 unique API series across FRED (108), BLS (13), EIA (5),
#   Treasury (2), BEA (2) = ~50.7% of the 300-indicator framework
# Remaining 148 require proprietary feeds (Bloomberg, MSCI, CME, etc.)
#
# Phase 1 (current): Tiers 1-3 via FRED/BLS/EIA/Treasury/BEA
# Phase 2 (planned):  Tier 2 expansion (FX volatility, fixed-income depth)
# Phase 3 (planned):  Tier 3 specialized (housing, tech CapEx, energy infra)
# Phase 4 (planned):  Tier 4 alternative data via premium feeds
