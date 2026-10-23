"""
S3 Data Reader for Mosaic Intelligence
Reads economic data from the S3 datalake instead of live API calls.
Falls back to live API if data not found in S3.
"""

import json
import re
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import io

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

import config


class S3DataReader:
    """
    Reads series data from the Mosaic Intelligence S3 datalake.
    
    S3 partition format (Hive-style):
        raw/source={source}/series_id={series_id}/year={year}/{series_id}_{date}.json
    
    FRED files contain the raw API response:
        { "observations": [{ "date": "2000-01-03", "value": "6.58" }, ...] }
    
    BLS files contain:
        { "Results": { "series": [{ "data": [{ "year": "2025", "period": "M01", "value": "..." }] }] } }
    """
    
    def __init__(self, bucket: str = None, region: str = None):
        if not HAS_BOTO3:
            raise ImportError("boto3 is required for S3 access. Install with: pip install boto3")
        
        self.bucket = bucket or config.S3_BUCKET_NAME
        self.region = region or config.AWS_REGION
        self.prefix = config.S3_RAW_PREFIX
        
        try:
            self.s3 = boto3.client("s3", region_name=self.region)
            # Quick check that credentials work
            self.s3.head_bucket(Bucket=self.bucket)
            self.available = True
        except (NoCredentialsError, ClientError) as e:
            print(f"S3 not available: {e}")
            self.available = False
    
    def _list_files(self, source: str, series_id: str) -> List[str]:
        """List all data files for a given source/series"""
        prefix = f"{self.prefix}/source={source}/series_id={series_id}/"
        
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            keys = []
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    if obj["Key"].endswith(".json"):
                        keys.append(obj["Key"])
            return sorted(keys, key=self._snapshot_order)
        except ClientError:
            return []
    
    @staticmethod
    def _snapshot_order(key):
        """Order snapshots by embedded acquisition date, not year partition."""
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", key.rsplit("/", 1)[-1])
        return (dates[-1] if dates else "", key)

    def _get_latest_file(self, source: str, series_id: str) -> Optional[str]:
        """Get the most recent data file key for a series"""
        files = self._list_files(source, series_id)
        return files[-1] if files else None
    
    def _read_json(self, key: str) -> Optional[dict]:
        """Read and parse a JSON file from S3"""
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            body = response["Body"].read().decode("utf-8")
            return json.loads(body)
        except (ClientError, json.JSONDecodeError) as e:
            print(f"Error reading s3://{self.bucket}/{key}: {e}")
            return None
    
    # =========================================================================
    # FRED
    # =========================================================================
    
    def get_fred_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        full_history: bool = False,
    ) -> pd.DataFrame:
        """
        Read a FRED series from S3.

        The raw files contain FRED API responses with observations arrays,
        partitioned by year. By default reads only the latest file for speed.
        Set full_history=True to read ALL year-partitioned files and merge.
        """
        if not self.available:
            return pd.DataFrame()

        if full_history or start_date:
            keys = self._list_files("fred", series_id)
        else:
            key = self._get_latest_file("fred", series_id)
            keys = [key] if key else []

        if not keys:
            return pd.DataFrame()

        all_rows = []
        for key in keys:
            data = self._read_json(key)
            if not data or "observations" not in data:
                continue
            for obs in data["observations"]:
                all_rows.append(obs)

        if not all_rows:
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df[["date", "value"]].dropna()
        df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
        df.columns = ["date", series_id]

        # Apply date filters
        if start_date:
            df = df[df["date"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["date"] <= pd.to_datetime(end_date)]

        return df.reset_index(drop=True)
    
    # =========================================================================
    # BLS
    # =========================================================================
    
    def get_bls_series(
        self,
        series_id: str,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Read a BLS series from S3.
        
        BLS raw files may be stored differently depending on the Lambda.
        Handles both raw BLS API response format and pre-processed format.
        """
        if not self.available:
            return pd.DataFrame()
        
        key = self._get_latest_file("bls", series_id)
        if not key:
            return pd.DataFrame()
        
        data = self._read_json(key)
        if not data:
            return pd.DataFrame()
        
        # Handle raw BLS API response format
        if "Results" in data:
            series_list = data.get("Results", {}).get("series", [])
            if not series_list:
                return pd.DataFrame()
            
            records = []
            for item in series_list[0].get("data", []):
                year = int(item["year"])
                period = item["period"]
                value = float(item["value"])
                
                if period.startswith("M"):
                    month = int(period[1:])
                    date = datetime(year, month, 1)
                elif period.startswith("Q"):
                    quarter = int(period[1:])
                    month = (quarter - 1) * 3 + 1
                    date = datetime(year, month, 1)
                else:
                    continue
                
                records.append({"date": date, series_id: value})
            
            df = pd.DataFrame(records)
        
        # Handle pre-processed format (list of {date, value} dicts)
        elif isinstance(data, list):
            df = pd.DataFrame(data)
            df["date"] = pd.to_datetime(df["date"])
            df[series_id] = pd.to_numeric(df["value"], errors="coerce")
            df = df[["date", series_id]]
        
        # Handle wrapped format { "data": [...] }
        elif "data" in data and isinstance(data["data"], list):
            df = pd.DataFrame(data["data"])
            df["date"] = pd.to_datetime(df.get("date", df.get("period", "")))
            df[series_id] = pd.to_numeric(df["value"], errors="coerce")
            df = df[["date", series_id]]
        
        else:
            return pd.DataFrame()
        
        if df.empty:
            return df
        
        df = df.dropna().sort_values("date").reset_index(drop=True)
        
        # Apply year filters
        if start_year:
            df = df[df["date"].dt.year >= start_year]
        if end_year:
            df = df[df["date"].dt.year <= end_year]
        
        return df.reset_index(drop=True)
    
    # =========================================================================
    # EIA
    # =========================================================================
    
    def get_eia_series(self, series_id: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Read an EIA series from S3. Handles both raw API response format
        and backfill observations format (year-partitioned like FRED)."""
        if not self.available:
            return pd.DataFrame()

        # Try reading all year-partitioned files (like FRED backfill format)
        keys = self._list_files("eia", series_id)
        if not keys:
            return pd.DataFrame()

        all_rows = []
        for key in keys:
            data = self._read_json(key)
            if not data:
                continue

            # Format 1: backfill format {"observations": [{date, value}, ...]}
            if "observations" in data:
                for obs in data["observations"]:
                    all_rows.append(obs)
            # Format 2: raw EIA API response {"response": {"data": [...]}}
            elif "response" in data:
                for rec in data.get("response", {}).get("data", []):
                    period = rec.get("period", "")
                    value = rec.get("value") if rec.get("value") is not None else rec.get("price")
                    if period and value is not None:
                        all_rows.append({"date": period, "value": str(value)})

        if not all_rows:
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df[["date", "value"]].dropna()
        df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
        df.columns = ["date", series_id]

        if start_date:
            df = df[df["date"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["date"] <= pd.to_datetime(end_date)]

        return df.reset_index(drop=True)
    
    # =========================================================================
    # TREASURY
    # =========================================================================
    
    def get_treasury_debt(self) -> pd.DataFrame:
        """Read Treasury debt data from S3"""
        if not self.available:
            return pd.DataFrame()
        
        key = self._get_latest_file("treasury", "debt_to_penny")
        if not key:
            # Try alternative key names
            key = self._get_latest_file("treasury", "debt")
        if not key:
            return pd.DataFrame()
        
        data = self._read_json(key)
        if not data:
            return pd.DataFrame()
        
        # Handle raw Treasury API response
        records = data.get("data", [])
        if records:
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df.get("record_date", ""))
            df["total_debt"] = pd.to_numeric(
                df.get("tot_pub_debt_out_amt", 0), errors="coerce"
            ) / 1e9  # Convert to billions
            return df[["date", "total_debt"]].dropna().sort_values("date").reset_index(drop=True)
        
        return pd.DataFrame()
    
    # =========================================================================
    # DATA EXCHANGE (Rearc CSV format)
    # =========================================================================

    def get_data_exchange_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Read a Data Exchange CSV series from S3.
        Rearc CSVs typically have columns: date, value (or DATE, {SERIES_ID}).
        """
        if not self.available:
            return pd.DataFrame()

        prefix = f"{self.prefix}/source=data_exchange/provider=rearc/series_id={series_id}/"

        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            csv_keys = []
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    if obj["Key"].endswith(".csv"):
                        csv_keys.append(obj["Key"])
            if not csv_keys:
                return pd.DataFrame()

            # Read the latest CSV
            latest_key = sorted(csv_keys, key=self._snapshot_order)[-1]
            response = self.s3.get_object(Bucket=self.bucket, Key=latest_key)
            csv_content = response["Body"].read().decode("utf-8")

            df = pd.read_csv(io.StringIO(csv_content))

            # Normalize column names
            df.columns = [c.strip().lower() for c in df.columns]

            # Find date and value columns
            date_col = next((c for c in df.columns if c in ("date", "observation_date")), None)
            value_col = next((c for c in df.columns if c in ("value", series_id.lower())), None)

            if not date_col or not value_col:
                # Fallback: first column is date, second is value
                if len(df.columns) >= 2:
                    date_col = df.columns[0]
                    value_col = df.columns[1]
                else:
                    return pd.DataFrame()

            df["date"] = pd.to_datetime(df[date_col])
            df[series_id] = pd.to_numeric(df[value_col], errors="coerce")
            df = df[["date", series_id]].dropna().sort_values("date").reset_index(drop=True)

            if start_date:
                df = df[df["date"] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df["date"] <= pd.to_datetime(end_date)]

            return df.reset_index(drop=True)

        except (ClientError, Exception) as e:
            print(f"Error reading Data Exchange CSV for {series_id}: {e}")
            return pd.DataFrame()

    # =========================================================================
    # UNIFIED ACCESS
    # =========================================================================
    
    def get_series(self, source: str, series_id: str, **kwargs) -> pd.DataFrame:
        """
        Unified method to get any series from S3 by source name.
        
        Args:
            source: "fred", "bls", "eia", or "treasury"
            series_id: The series identifier
            **kwargs: Additional filters (start_date, end_date, etc.)
        """
        if source == "fred":
            return self.get_fred_series(series_id, **kwargs)
        elif source == "bls":
            return self.get_bls_series(series_id, **kwargs)
        elif source == "eia":
            return self.get_eia_series(series_id)
        elif source == "treasury":
            if series_id == "debt_to_penny":
                return self.get_treasury_debt()
        elif source == "data_exchange":
            return self.get_data_exchange_series(series_id, **kwargs)

        return pd.DataFrame()
    
    def check_series_availability(self) -> Dict[str, Dict[str, bool]]:
        """
        Check which series are available in S3.
        Returns a dict: { "fred": { "DGS10": True, ... }, "bls": { ... }, ... }
        """
        availability = {"fred": {}, "bls": {}, "eia": {}, "treasury": {}}
        
        for series_id in config.get_all_fred_series():
            files = self._list_files("fred", series_id)
            availability["fred"][series_id] = len(files) > 0
        
        for series_id in config.get_all_bls_series():
            files = self._list_files("bls", series_id)
            availability["bls"][series_id] = len(files) > 0
        
        for series_id in config.get_all_eia_series():
            files = self._list_files("eia", series_id)
            availability["eia"][series_id] = len(files) > 0
        
        return availability
    
    def get_data_freshness(self, source: str, series_id: str) -> Optional[str]:
        """Get the date stamp of the most recent data file for a series"""
        key = self._get_latest_file(source, series_id)
        if key:
            # Extract date from filename pattern: {series_id}_{YYYY-MM-DD}.json
            try:
                filename = key.split("/")[-1]
                date_part = filename.replace(f"{series_id}_", "").replace(".json", "")
                return date_part
            except (IndexError, ValueError):
                pass
        return None


# =============================================================================
# HYBRID DATA MANAGER — S3 first, API fallback
# =============================================================================

class HybridDataManager:
    """
    Tries S3 first, falls back to live API if S3 data not available.
    Controlled by config.DATA_SOURCE_MODE:
      - "s3": S3 primary, API fallback
      - "api": API only (original behavior)
    """
    
    def __init__(self):
        self.mode = config.DATA_SOURCE_MODE
        self.s3_reader = None
        self._api_clients = {}
        
        if self.mode == "s3" and HAS_BOTO3:
            try:
                self.s3_reader = S3DataReader()
                if not self.s3_reader.available:
                    print("S3 not available, falling back to API mode")
                    self.s3_reader = None
            except Exception as e:
                print(f"S3 init failed: {e}, using API mode")
                self.s3_reader = None
    
    def _get_fred_client(self):
        """Lazy-load FRED client"""
        if "fred" not in self._api_clients:
            from data_fetcher import FREDClient
            self._api_clients["fred"] = FREDClient()
        return self._api_clients["fred"]
    
    def _get_bls_client(self):
        """Lazy-load BLS client"""
        if "bls" not in self._api_clients:
            from data_fetcher import BLSClient
            self._api_clients["bls"] = BLSClient()
        return self._api_clients["bls"]
    
    def _get_treasury_client(self):
        """Lazy-load Treasury client"""
        if "treasury" not in self._api_clients:
            from data_fetcher import TreasuryClient
            self._api_clients["treasury"] = TreasuryClient()
        return self._api_clients["treasury"]
    
    def _get_eia_client(self):
        """Lazy-load EIA client"""
        if "eia" not in self._api_clients:
            from data_fetcher import EIAClient
            self._api_clients["eia"] = EIAClient()
        return self._api_clients["eia"]
    
    def get_fred_series(self, series_id: str, full_history: bool = False, **kwargs) -> pd.DataFrame:
        """Get FRED series: S3 (normalized JSON) -> Data Exchange CSV -> live API"""
        if self.s3_reader:
            # Try normalized FRED JSON first (written by API fetcher or DX processor)
            df = self.s3_reader.get_fred_series(series_id, full_history=full_history, **kwargs)
            if not df.empty:
                return df

            # Try raw Data Exchange CSV as second source
            df = self.s3_reader.get_data_exchange_series(series_id, **kwargs) if config.DATA_EXCHANGE_ENABLED else pd.DataFrame()
            if not df.empty:
                return df

        # Fallback to live API
        try:
            client = self._get_fred_client()
            return client.get_series(series_id, **kwargs)
        except Exception as e:
            print(f"API fallback failed for FRED {series_id}: {e}")
            return pd.DataFrame()
    
    def get_bls_series(self, series_id: str, **kwargs) -> pd.DataFrame:
        """Get BLS series: S3 first, then API"""
        if self.s3_reader:
            df = self.s3_reader.get_bls_series(series_id, **kwargs)
            if not df.empty:
                return df
        
        try:
            client = self._get_bls_client()
            return client.get_series(series_id, **kwargs)
        except Exception as e:
            print(f"API fallback failed for BLS {series_id}: {e}")
            return pd.DataFrame()
    
    def get_treasury_debt(self, **kwargs) -> pd.DataFrame:
        """Get Treasury debt: S3 first, then API"""
        if self.s3_reader:
            df = self.s3_reader.get_treasury_debt()
            if not df.empty:
                return df
        
        try:
            client = self._get_treasury_client()
            return client.get_debt_to_penny(**kwargs)
        except Exception as e:
            print(f"API fallback failed for Treasury: {e}")
            return pd.DataFrame()
    
    def get_eia_series(self, series_id: str, **kwargs) -> pd.DataFrame:
        """Get EIA series: S3 first, then API"""
        if self.s3_reader:
            df = self.s3_reader.get_eia_series(series_id, **kwargs)
            if not df.empty:
                return df

        try:
            client = self._get_eia_client()
            return client.get_series(series_id, **kwargs)
        except Exception as e:
            print(f"API fallback failed for EIA {series_id}: {e}")
            return pd.DataFrame()

    def get_eia_gas_prices(self, **kwargs) -> pd.DataFrame:
        """Get gas prices: S3 first (via FRED GASREGW fallback series), then EIA API with fallback chain"""
        # Try S3 first — check for the FRED GASREGW series which is the ultimate fallback
        if self.s3_reader:
            df = self.s3_reader.get_fred_series("GASREGW")
            if not df.empty:
                df.columns = ["date", "gas_price"]
                return df

        # Fall back to live EIA API with its multi-level fallback chain
        try:
            client = self._get_eia_client()
            return client.get_gas_prices(**kwargs)
        except Exception as e:
            print(f"API fallback failed for gas prices: {e}")
            return pd.DataFrame()

    @property
    def data_source(self) -> str:
        """Report which data source is active"""
        if self.s3_reader and self.s3_reader.available:
            return "S3 (with API fallback)"
        return "API (direct)"
