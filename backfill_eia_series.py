"""
Backfill EIA (Energy Information Administration) series into S3 datalake.
Fetches up to 20 years of history for all mapped EIA indicators.

Usage:
    python backfill_eia_series.py

Requires: EIA_API_KEY environment variable
S3 partition format: raw/source=eia/series_id={series_id}/year={year}/{series_id}_{date}.json
"""

import os
import sys
import json
import time
import requests
import boto3
from datetime import datetime, timedelta
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import config

# EIA series to backfill (from indicators_300.py SRC entries with source_type "eia")
EIA_SERIES = {
    "PET.WCESTUS1.W": {
        "name": "Crude Oil Inventories",
        "route": "petroleum/stoc/wstk",
        "params": {"frequency": "weekly", "data[0]": "value", "facets[series][]": "WCESTUS1"},
    },
    "PET.WGTSTUS1.W": {
        "name": "Gasoline Inventories",
        "route": "petroleum/stoc/wstk",
        "params": {"frequency": "weekly", "data[0]": "value", "facets[series][]": "WGTSTUS1"},
    },
    "PET.WPULRL3S3.W": {
        "name": "Refinery Utilization",
        "route": "petroleum/pnp/wiup",
        "params": {"frequency": "weekly", "data[0]": "value", "facets[series][]": "WPULRL3S3"},
    },
    "NG.NW2_EPG0_SWO_R48_BCF.W": {
        "name": "Natural Gas Storage",
        "route": "natural-gas/stor/wkly",
        "params": {"frequency": "weekly", "data[0]": "value"},
    },
    "PET.WGFUPUS2.W": {
        "name": "US Gasoline Demand",
        "route": "petroleum/cons/wpsup",
        "params": {"frequency": "weekly", "data[0]": "value", "facets[series][]": "WGFUPUS2"},
    },
    "NG.N9133US2.M": {
        "name": "LNG Exports",
        "route": "natural-gas/move/expc",
        "params": {"frequency": "monthly", "data[0]": "value"},
    },
}

BASE_URL = "https://api.eia.gov/v2"


def fetch_eia_series(series_id, route, params, api_key, start_date="2000-01-01"):
    """Fetch full history for an EIA series."""
    url = f"{BASE_URL}/{route}/data/"
    req_params = {
        "api_key": api_key,
        "start": start_date,
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": 10000,
        **params,
    }

    response = requests.get(url, params=req_params, timeout=60)
    response.raise_for_status()
    data = response.json()

    records = data.get("response", {}).get("data", [])
    if not records:
        return []

    observations = []
    for rec in records:
        period = rec.get("period", "")
        value = rec.get("value") or rec.get("price")
        if period and value is not None:
            try:
                float(value)
                observations.append({"date": period, "value": str(value)})
            except (ValueError, TypeError):
                continue

    return observations


def upload_to_s3(s3_client, bucket, series_id, observations):
    """Upload observations to S3, partitioned by year."""
    by_year = defaultdict(list)
    for obs in observations:
        year = obs["date"][:4]
        by_year[year].append(obs)

    files_written = 0
    for year, year_obs in sorted(by_year.items()):
        # Use the latest date in the year partition as the file date
        latest_date = max(o["date"] for o in year_obs)
        # Sanitize series_id for S3 key (replace dots with underscores)
        safe_id = series_id.replace(".", "_")
        key = f"{config.S3_RAW_PREFIX}/source=eia/series_id={series_id}/year={year}/{safe_id}_{latest_date}.json"

        body = json.dumps({"observations": year_obs}, indent=2)
        s3_client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
        files_written += 1

    return files_written


def main():
    api_key = os.environ.get("EIA_API_KEY") or config.EIA_API_KEY
    if not api_key:
        print("ERROR: EIA_API_KEY not set")
        sys.exit(1)

    bucket = config.S3_BUCKET_NAME
    s3 = boto3.client("s3", region_name=config.AWS_REGION)

    total_obs = 0
    total_files = 0
    start_date = "2000-01-01"

    print(f"EIA Backfill: {len(EIA_SERIES)} series → s3://{bucket}/")
    print(f"Date range: {start_date} to present")
    print("=" * 70)

    for series_id, meta in EIA_SERIES.items():
        print(f"\n[{series_id}] {meta['name']}...", end=" ", flush=True)
        try:
            observations = fetch_eia_series(
                series_id, meta["route"], meta["params"], api_key, start_date
            )
            if not observations:
                print("NO DATA")
                continue

            files = upload_to_s3(s3, bucket, series_id, observations)
            total_obs += len(observations)
            total_files += files
            date_range = f"{observations[0]['date']} to {observations[-1]['date']}"
            print(f"{len(observations)} obs, {files} files ({date_range})")

        except Exception as e:
            print(f"ERROR: {e}")

        time.sleep(0.5)  # Rate limiting

    print("\n" + "=" * 70)
    print(f"DONE: {total_obs:,} total observations, {total_files} S3 files written")


if __name__ == "__main__":
    main()
