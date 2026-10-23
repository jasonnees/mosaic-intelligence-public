"""
Compute historical statistics for each FRED series in the SRC mapping.
Reads from S3 datalake via HybridDataManager, computes percentiles and summary stats,
and outputs JSON for use in updating target ranges.
"""

import json
import sys
import os
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Ensure we're in the right directory for relative imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from s3_reader import HybridDataManager

# SRC mapping: indicator name -> [series_id, url]
SRC = {
    "Federal Funds Rate": "DFF",
    "2Y-10Y Treasury Spread": "T10Y2Y",
    "3M-10Y Treasury Spread": "T10Y3M",
    "5Y5Y Forward Inflation": "T5YIFR",
    "10Y TIPS Breakeven": "T10YIE",
    "5Y TIPS Breakeven": "T5YIE",
    "Real Yield Curve (TIPS)": "DFII10",
    "SOFR": "SOFR",
    "VIX Index": "VIXCLS",
    "CDX NA Investment Grade": "BAMLC0A0CM",
    "CDX High Yield": "BAMLH0A0HYM2",
    "High Yield Spreads": "BAMLH0A0HYM2",
    "S&P 500": "SP500",
    "GDP Growth Rate": "GDPC1",
    "Nonfarm Payrolls": "PAYEMS",
    "Unemployment Rate": "UNRATE",
    "Initial Claims (4-wk)": "ICSA",
    "Industrial Production": "INDPRO",
    "Capacity Utilization": "TCU",
    "C.P.I. (year-over-year)": "CPIAUCSL",
    "P.C.E. Price Index": "PCEPI",
    "Personal Spending": "PCE",
    "Retail Sales": "RSXFS",
    "WTI Crude": "DCOILWTICO",
    "Brent Crude": "DCOILBRENTEU",
    "Copper": "PCOPPUSDM",
    "Dollar Index (DXY)": "DTWEXBGS",
    "Euro/Dollar": "DEXUSEU",
    "Existing Home Sales": "EXHOSLUSM495S",
    "Housing Starts": "HOUST",
    "Case-Shiller Index": "CSUSHPINSA",
    "30Y Mortgage Rate": "MORTGAGE30US",
    "Affordability Index": "FIXHAI",
    "Michigan Sentiment": "UMCSENT",
    "Savings Rate": "PSAVERT",
    "Hourly Earnings": "CES0500000003",
    "C&I Loans": "BUSLOANS",
    "Credit Card Delinquency": "DRCCLACBS",
    "Consumer Delinquency": "DRCLACBS",
    "Fed Balance Sheet": "WALCL",
    "30Y Treasury": "DGS30",
    "2Y Treasury": "DGS2",
    "5Y Treasury": "DGS5",
    "New Home Sales": "HSN1F",
    "Building Permits": "PERMIT",
    "Months Supply": "MSACSR",
    "TED Spread": "TEDRATE",
    "Consumer Credit": "TOTALSL",
}


def compute_stats(series: pd.Series) -> dict:
    """Compute summary statistics for a numeric series."""
    s = series.dropna()
    if len(s) == 0:
        return None
    return {
        "min": round(float(s.min()), 4),
        "p10": round(float(np.percentile(s, 10)), 4),
        "p25": round(float(np.percentile(s, 25)), 4),
        "median": round(float(np.median(s)), 4),
        "p75": round(float(np.percentile(s, 75)), 4),
        "p90": round(float(np.percentile(s, 90)), 4),
        "max": round(float(s.max()), 4),
        "mean": round(float(s.mean()), 4),
        "std": round(float(s.std()), 4),
        "current": round(float(s.iloc[-1]), 4),
        "count": int(len(s)),
        "first_date": str(series.index[0].date()) if hasattr(series.index[0], 'date') else str(series.index[0]),
        "last_date": str(series.index[-1].date()) if hasattr(series.index[-1], 'date') else str(series.index[-1]),
    }


def main():
    print("Initializing HybridDataManager...")
    dm = HybridDataManager()
    print(f"Data source: {dm.data_source}\n")

    # Deduplicate series_ids (CDX High Yield and High Yield Spreads share BAMLH0A0HYM2)
    seen_series = set()
    results = {}
    errors = []

    for indicator_name, series_id in SRC.items():
        print(f"Fetching {indicator_name} ({series_id})...", end=" ", flush=True)

        try:
            df = dm.get_fred_series(series_id)

            if df.empty:
                print("EMPTY - no data returned")
                errors.append({"indicator": indicator_name, "series_id": series_id, "error": "empty dataframe"})
                continue

            # The dataframe has columns: date, {series_id}
            # Set date as index for convenience
            if "date" in df.columns:
                df = df.set_index("date").sort_index()

            values = df[series_id]
            stats = compute_stats(values)

            if stats is None:
                print("NO VALID VALUES")
                errors.append({"indicator": indicator_name, "series_id": series_id, "error": "no valid numeric values"})
                continue

            results[indicator_name] = {
                "series_id": series_id,
                **stats,
            }

            print(f"OK  ({stats['count']} obs, current={stats['current']}, "
                  f"p25={stats['p25']}, median={stats['median']}, p75={stats['p75']})")

        except Exception as e:
            print(f"ERROR: {e}")
            errors.append({"indicator": indicator_name, "series_id": series_id, "error": str(e)})

    # Save results
    output_path = "/Users/jasonnees/mosaic-intelligence/target_range_analysis.json"
    output = {
        "generated": pd.Timestamp.now().isoformat(),
        "total_indicators": len(SRC),
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*100}")
    print(f"Results saved to {output_path}")
    print(f"Successful: {len(results)} / {len(SRC)}")
    print(f"Failed: {len(errors)}")

    # Print summary table
    print(f"\n{'='*100}")
    print(f"{'Indicator':<30} {'Series':<16} {'Count':>6} {'Min':>10} {'P25':>10} {'Median':>10} "
          f"{'P75':>10} {'Max':>10} {'Current':>10}")
    print("-" * 130)

    for name, data in sorted(results.items()):
        print(f"{name:<30} {data['series_id']:<16} {data['count']:>6} {data['min']:>10.2f} "
              f"{data['p25']:>10.2f} {data['median']:>10.2f} {data['p75']:>10.2f} "
              f"{data['max']:>10.2f} {data['current']:>10.2f}")

    if errors:
        print(f"\n{'='*100}")
        print("ERRORS:")
        for err in errors:
            print(f"  {err['indicator']} ({err['series_id']}): {err['error']}")


if __name__ == "__main__":
    main()
