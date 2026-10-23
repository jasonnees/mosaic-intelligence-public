"""
Compute historical statistics for ALL FRED series in the expanded SRC mapping.
Force-recomputes ALL indicators using full 20-year backfilled data from S3.
Saves results to target_range_analysis_full.json.
"""

import json
import sys
import os
import numpy as np
import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from s3_reader import HybridDataManager
from indicators_300 import SRC


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

    print(f"Force-recomputing ALL {len(SRC)} indicators with full 20-year history...")
    print(f"{'='*100}\n")

    results = {}
    errors = []
    success = 0
    fail = 0

    for indicator_name, src_entry in SRC.items():
        series_id = src_entry[0]

        print(f"[{success + fail + 1}/{len(SRC)}] {indicator_name} ({series_id})...", end=" ", flush=True)

        try:
            df = dm.get_fred_series(series_id, full_history=True)

            if df.empty:
                print("EMPTY")
                errors.append({"indicator": indicator_name, "series_id": series_id, "error": "empty dataframe"})
                fail += 1
                continue

            if "date" in df.columns:
                df = df.set_index("date").sort_index()

            values = df[series_id]
            stats = compute_stats(values)

            if stats is None:
                print("NO VALID VALUES")
                errors.append({"indicator": indicator_name, "series_id": series_id, "error": "no valid numeric values"})
                fail += 1
                continue

            results[indicator_name] = {
                "series_id": series_id,
                **stats,
            }

            years = round((pd.Timestamp(stats['last_date']) - pd.Timestamp(stats['first_date'])).days / 365.25, 1)
            print(f"OK  ({stats['count']} obs, {years}yr, p25={stats['p25']}, p75={stats['p75']})")
            success += 1

        except Exception as e:
            print(f"ERROR: {e}")
            errors.append({"indicator": indicator_name, "series_id": series_id, "error": str(e)})
            fail += 1

    # Save full results
    output_path = "/Users/jasonnees/mosaic-intelligence/target_range_analysis_full.json"
    output = {
        "generated": pd.Timestamp.now().isoformat(),
        "total_src_indicators": len(SRC),
        "successful": success,
        "failed": fail,
        "results": results,
        "errors": errors,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*100}")
    print(f"Results saved to {output_path}")
    print(f"Successful: {success} / {len(SRC)}")
    print(f"Failed: {fail}")

    # Summary of indicators with < 50 obs (insufficient for reliable IQR)
    short = {k: v for k, v in results.items() if v['count'] < 50}
    if short:
        print(f"\nWARNING: {len(short)} indicators with <50 observations:")
        for name, data in sorted(short.items(), key=lambda x: x[1]['count']):
            print(f"  {name}: {data['count']} obs ({data['first_date']} to {data['last_date']})")

    if errors:
        print(f"\nERRORS:")
        for err in errors:
            print(f"  {err['indicator']} ({err['series_id']}): {err['error']}")


if __name__ == "__main__":
    main()
