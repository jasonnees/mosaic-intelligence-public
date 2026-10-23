"""
Backfill 20 years of FRED data into S3 datalake for all series in indicators_300.py SRC dict.
Partition format: raw/source=fred/series_id={SERIES_ID}/year={YYYY}/{SERIES_ID}_{YYYY-MM-DD}.json
"""

import json
import time
from collections import defaultdict
from datetime import datetime

import boto3
import requests
from dotenv import load_dotenv
import os

load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "mosaic-intelligence-datalake")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

OBSERVATION_START = "2000-01-01"
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# All unique FRED series IDs from SRC in indicators_300.py
SRC = {
    "Federal Funds Rate": "DFF",
    "2Y-10Y Treasury Spread": "T10Y2Y",
    "3M-10Y Treasury Spread": "T10Y3M",
    "5Y5Y Forward Inflation": "T5YIFR",
    "10Y TIPS Breakeven": "T10YIE",
    "5Y TIPS Breakeven": "T5YIE",
    "Real Yield Curve (TIPS)": "DFII10",
    "SOFR": "SOFR",
    "CDX NA Investment Grade": "BAMLC0A0CM",
    "CDX High Yield / High Yield Spreads": "BAMLH0A0HYM2",
    "VIX Index": "VIXCLS",
    "S&P 500": "SP500",
    "GDP Growth Rate": "A191RL1Q225SBEA",
    "Nonfarm Payrolls": "PAYEMS",
    "Unemployment Rate": "UNRATE",
    "Initial Claims (4-wk)": "ICSA",
    "Industrial Production": "INDPRO",
    "Capacity Utilization": "TCU",
    "CPI (YoY)": "CPIAUCSL",
    "Core CPI": "CPILFESL",
    "PCE Price Index": "PCEPI",
    "Personal Spending": "PCE",
    "Retail Sales": "RSXFS",
    "30Y Treasury": "DGS30",
    "2Y Treasury": "DGS2",
    "5Y Treasury": "DGS5",
    "TED Spread": "TEDRATE",
    "Fed Balance Sheet": "WALCL",
    "Bank Lending Standards / Sr Loan Officer Survey": "DRTSCILM",
    "C&I Loans": "BUSLOANS",
    "Consumer Delinquency": "DRCLACBS",
    "Credit Card Delinquency": "DRCCLACBS",
    "Mortgage Delinquency / Mortgage Delinq 90+": "DRSFRMACBS",
    "Nasdaq Composite": "NASDAQCOM",
    "Dow Jones Industrial": "DJIA",
    "WTI Crude": "DCOILWTICO",
    "Brent Crude": "DCOILBRENTEU",
    "Copper": "PCOPPUSDM",
    "Nat Gas (Henry Hub)": "DHHNGSP",
    "Dollar Index (DXY) / Trade-Weighted Dollar": "DTWEXBGS",
    "Euro/Dollar": "DEXUSEU",
    "Dollar/Yen": "DEXJPUS",
    "Dollar/Yuan": "DEXCHUS",
    "Trade Balance": "BOPGSTB",
    "Existing Home Sales": "EXHOSLUSM495S",
    "New Home Sales": "HSN1F",
    "Housing Starts": "HOUST",
    "Building Permits": "PERMIT",
    "Case-Shiller Index": "CSUSHPINSA",
    "FHFA House Prices": "USSTHPI",
    "30Y Mortgage Rate": "MORTGAGE30US",
    "Affordability Index": "FIXHAI",
    "Months Supply": "MSACSR",
    "Rental Vacancy": "RRVRUSQ156N",
    "Construction Spending": "TTLCONS",
    "Durable Goods Orders": "DGORDER",
    "Factory Orders": "AMTMNO",
    "Capacity Utilization (Mfg)": "MCUMFN",
    "Mfg Employment": "MANEMP",
    "Inventory/Sales": "ISRATIO",
    "Export Orders": "BOPTEXP",
    "Core CapEx Orders": "NEWORDER",
    "Productivity": "OPHPBS",
    "Unit Labor Costs": "ULCNFB",
    "Philly Fed Mfg": "GACDFSA066MSFRBPHI",
    "Empire State Mfg": "GACDISA066MSFRBNY",
    "Michigan Sentiment": "UMCSENT",
    "Personal Income": "PI",
    "Savings Rate": "PSAVERT",
    "Consumer Credit": "TOTALSL",
    "Auto Sales": "TOTALSA",
    "Participation Rate": "CIVPART",
    "Hourly Earnings": "CES0500000003",
    "JOLTS Openings": "JTSJOL",
    "JOLTS Quits Rate": "JTSQUR",
    "Employment Cost Index": "ECIWAG",
    "Temp Employment": "TEMPHELPS",
    "Debt-to-GDP": "GFDEGDQ188S",
    "Tax Revenue": "FYFRGDA188S",
    "Govt Spending": "FGEXPND",
    "Budget Deficit": "FYFSD",
    "Money Market Assets": "RRPONTSYD",
    "Financial Stress": "STLFSI4",
}

# Deduplicate series IDs
SERIES_IDS = sorted(set(SRC.values()))


def fetch_fred_observations(series_id: str) -> list[dict] | None:
    """Fetch all observations for a series from FRED API since 2000-01-01."""
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": OBSERVATION_START,
    }
    try:
        resp = requests.get(FRED_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("observations", [])
    except Exception as e:
        print(f"  ERROR fetching {series_id}: {e}")
        return None


def split_by_year(observations: list[dict]) -> dict[str, list[dict]]:
    """Split observations into buckets by year."""
    by_year = defaultdict(list)
    for obs in observations:
        date_str = obs.get("date", "")
        if len(date_str) >= 4:
            year = date_str[:4]
            by_year[year].append({"date": obs["date"], "value": obs.get("value", ".")})
    return dict(by_year)


def upload_to_s3(s3_client, series_id: str, year: str, observations: list[dict]) -> bool:
    """Upload one year of observations to S3."""
    key = f"raw/source=fred/series_id={series_id}/year={year}/{series_id}_{year}-01-01.json"
    body = json.dumps({"observations": observations}, separators=(",", ":"))
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        return True
    except Exception as e:
        print(f"  ERROR uploading {key}: {e}")
        return False


def main():
    print(f"Backfilling {len(SERIES_IDS)} unique FRED series to s3://{S3_BUCKET}/")
    print(f"Observation start: {OBSERVATION_START}")
    print(f"Region: {AWS_REGION}")
    print("=" * 70)

    s3 = boto3.client("s3", region_name=AWS_REGION)

    results = {}  # series_id -> {"status": "ok"/"fail", "obs": N, "years": N}
    total_obs = 0
    total_files = 0

    for i, series_id in enumerate(SERIES_IDS, 1):
        print(f"\n[{i}/{len(SERIES_IDS)}] {series_id} ...", end=" ", flush=True)

        observations = fetch_fred_observations(series_id)
        if observations is None:
            results[series_id] = {"status": "fail", "obs": 0, "years": 0, "error": "API error"}
            print("FAILED (API)")
            time.sleep(0.6)
            continue

        # Filter out missing values (FRED returns "." for missing)
        valid_obs = [o for o in observations if o.get("value", ".") != "."]
        by_year = split_by_year(valid_obs)

        if not by_year:
            results[series_id] = {"status": "ok", "obs": 0, "years": 0}
            print(f"0 observations (empty series)")
            time.sleep(0.6)
            continue

        year_count = 0
        obs_count = len(valid_obs)
        upload_ok = True

        for year in sorted(by_year.keys()):
            if not upload_to_s3(s3, series_id, year, by_year[year]):
                upload_ok = False
                break
            year_count += 1

        if upload_ok:
            results[series_id] = {"status": "ok", "obs": obs_count, "years": year_count}
            total_obs += obs_count
            total_files += year_count
            print(f"{obs_count:,} obs across {year_count} years -> OK")
        else:
            results[series_id] = {"status": "fail", "obs": obs_count, "years": year_count, "error": "S3 upload"}
            print("FAILED (S3)")

        # Rate limit: ~120 req/min = 0.5s between requests
        time.sleep(0.6)

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("BACKFILL SUMMARY")
    print("=" * 70)

    succeeded = [sid for sid, r in results.items() if r["status"] == "ok"]
    failed = [sid for sid, r in results.items() if r["status"] == "fail"]

    print(f"Total series attempted: {len(SERIES_IDS)}")
    print(f"Succeeded: {len(succeeded)}")
    print(f"Failed:    {len(failed)}")
    print(f"Total observations loaded: {total_obs:,}")
    print(f"Total S3 files written:    {total_files:,}")

    if failed:
        print(f"\nFailed series:")
        for sid in failed:
            err = results[sid].get("error", "unknown")
            print(f"  - {sid}: {err}")

    if succeeded:
        print(f"\nSucceeded series:")
        for sid in succeeded:
            r = results[sid]
            print(f"  - {sid}: {r['obs']:,} obs, {r['years']} years")

    print(f"\nDone at {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
