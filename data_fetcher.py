"""
Data fetching module for FRED, BLS, Treasury, and EIA APIs
Used as the API fallback layer when S3 data is unavailable.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import json
import os
from functools import lru_cache
import time

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import config


class DataFetchError(Exception):
    """Custom exception for data fetch errors"""
    pass


# =============================================================================
# FRED API
# =============================================================================

class FREDClient:
    """Client for Federal Reserve Economic Data API"""

    BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.FRED_API_KEY
        if not self.api_key:
            raise DataFetchError("FRED API key not configured")

    def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100000
    ) -> pd.DataFrame:
        """Fetch a single series from FRED"""

        if not start_date:
            start_date = (datetime.now() - timedelta(days=config.DEFAULT_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        url = f"{self.BASE_URL}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date,
            "limit": limit,
            "sort_order": "asc"
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "observations" not in data:
                return pd.DataFrame()

            df = pd.DataFrame(data["observations"])
            if df.empty:
                return df

            df["date"] = pd.to_datetime(df["date"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df[["date", "value"]].dropna()
            df = df.sort_values("date").reset_index(drop=True)
            df.columns = ["date", series_id]

            return df

        except requests.exceptions.RequestException as e:
            raise DataFetchError(f"FRED API error for {series_id}: {str(e)}")

    def get_multiple_series(self, series_ids: List[str], **kwargs) -> pd.DataFrame:
        """Fetch multiple series and merge them"""
        dfs = []
        for series_id in series_ids:
            try:
                df = self.get_series(series_id, **kwargs)
                if not df.empty:
                    dfs.append(df)
                time.sleep(0.1)  # Rate limiting
            except DataFetchError as e:
                print(f"Warning: {e}")
                continue

        if not dfs:
            return pd.DataFrame()

        result = dfs[0]
        for df in dfs[1:]:
            result = pd.merge(result, df, on="date", how="outer")

        return result.sort_values("date").reset_index(drop=True)


# =============================================================================
# BLS API
# =============================================================================

class BLSClient:
    """Client for Bureau of Labor Statistics API"""

    BASE_URL_V1 = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
    BASE_URL_V2 = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.BLS_API_KEY
        self.base_url = self.BASE_URL_V2 if self.api_key else self.BASE_URL_V1

    def get_series(
        self,
        series_id: str,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> pd.DataFrame:
        """Fetch a single series from BLS"""

        if not start_year:
            start_year = datetime.now().year - 3
        if not end_year:
            end_year = datetime.now().year

        payload = {
            "seriesid": [series_id],
            "startyear": str(start_year),
            "endyear": str(end_year),
        }

        if self.api_key:
            payload["registrationkey"] = self.api_key

        headers = {"Content-type": "application/json"}

        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "REQUEST_SUCCEEDED":
                raise DataFetchError(f"BLS API error: {data.get('message', 'Unknown error')}")

            if not data.get("Results", {}).get("series"):
                return pd.DataFrame()

            series_data = data["Results"]["series"][0]["data"]

            records = []
            for item in series_data:
                year = int(item["year"])
                period = item["period"]
                value = float(item["value"])

                if period.startswith("M"):
                    month = int(period[1:])
                    if month < 1 or month > 12:
                        continue
                    date = datetime(year, month, 1)
                elif period.startswith("Q"):
                    quarter = int(period[1:])
                    month = (quarter - 1) * 3 + 1
                    date = datetime(year, month, 1)
                else:
                    continue

                records.append({"date": date, series_id: value})

            df = pd.DataFrame(records)
            if df.empty:
                return df

            return df.sort_values("date").reset_index(drop=True)

        except requests.exceptions.RequestException as e:
            raise DataFetchError(f"BLS API error for {series_id}: {str(e)}")

    def get_multiple_series(self, series_ids: List[str], **kwargs) -> pd.DataFrame:
        """Fetch multiple series"""
        dfs = []
        for series_id in series_ids:
            try:
                df = self.get_series(series_id, **kwargs)
                if not df.empty:
                    dfs.append(df)
                time.sleep(0.5)  # BLS has stricter rate limits
            except DataFetchError as e:
                print(f"Warning: {e}")
                continue

        if not dfs:
            return pd.DataFrame()

        result = dfs[0]
        for df in dfs[1:]:
            result = pd.merge(result, df, on="date", how="outer")

        return result.sort_values("date").reset_index(drop=True)


# =============================================================================
# TREASURY API
# =============================================================================

class TreasuryClient:
    """Client for Treasury Fiscal Data API"""

    BASE_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"

    def get_yield_curve(self, days: int = 365) -> pd.DataFrame:
        """Fetch daily Treasury yield curve data"""

        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        url = f"{self.BASE_URL}/v2/accounting/od/avg_interest_rates"
        params = {
            "filter": f"record_date:gte:{start_date},security_desc:eq:Treasury Bills",
            "sort": "-record_date",
            "page[size]": 10000,
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if not data.get("data"):
                return pd.DataFrame()

            df = pd.DataFrame(data["data"])
            df["date"] = pd.to_datetime(df["record_date"])
            df["avg_interest_rate_amt"] = pd.to_numeric(df["avg_interest_rate_amt"], errors="coerce")

            return df[["date", "security_desc", "avg_interest_rate_amt"]].dropna()

        except requests.exceptions.RequestException as e:
            raise DataFetchError(f"Treasury API error: {str(e)}")

    def get_debt_to_penny(self, days: int = None) -> pd.DataFrame:
        """Fetch daily total public debt"""

        if days is None:
            days = config.DEFAULT_LOOKBACK_DAYS
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        url = f"{self.BASE_URL}/v2/accounting/od/debt_to_penny"
        params = {
            "filter": f"record_date:gte:{start_date}",
            "sort": "-record_date",
            "page[size]": 10000,
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if not data.get("data"):
                return pd.DataFrame()

            df = pd.DataFrame(data["data"])
            df["date"] = pd.to_datetime(df["record_date"])
            df["total_debt"] = pd.to_numeric(df["tot_pub_debt_out_amt"], errors="coerce") / 1e9

            return df[["date", "total_debt"]].dropna().sort_values("date").reset_index(drop=True)

        except requests.exceptions.RequestException as e:
            raise DataFetchError(f"Treasury API error: {str(e)}")


# =============================================================================
# EIA API (Corrected endpoints for v2)
# =============================================================================

class EIAClient:
    """Client for Energy Information Administration API v2"""

    BASE_URL = "https://api.eia.gov/v2"

    # Route map for known series to their correct v2 endpoints
    ROUTE_MAP = {
        # Gas prices — correct endpoint is /petroleum/pri/gnd (NOT /gasprice)
        "PET.EMM_EPMR_PTE_NUS_DPG.W": ("petroleum/pri/gnd", {
            "frequency": "weekly", "data[0]": "value",
            "facets[product][]": "EPM0", "facets[duoarea][]": "NUS"
        }),
        "PET.EMM_EPD2D_PTE_NUS_DPG.W": ("petroleum/pri/gnd", {
            "frequency": "weekly", "data[0]": "value",
            "facets[product][]": "EPD2D", "facets[duoarea][]": "NUS"
        }),
        # Crude oil stocks
        "PET.WCESTUS1.W": ("petroleum/stoc/wstk", {
            "frequency": "weekly", "data[0]": "value",
            "facets[series][]": "WCESTUS1"
        }),
        # Natural gas
        "NG.N3010US3.M": ("natural-gas/pri/sum", {
            "frequency": "monthly", "data[0]": "value"
        }),
        "NG.RNGWHHD.W": ("natural-gas/pri/sum", {
            "frequency": "weekly", "data[0]": "value",
            "facets[process][]": "PRS"
        }),
        # Electricity
        "ELEC.PRICE.US-RES.M": ("electricity/retail-sales", {
            "frequency": "monthly", "data[0]": "price",
            "facets[sectorid][]": "RES", "facets[stateid][]": "US"
        }),
        # Gasoline stocks (weekly)
        "PET.WGTSTUS1.W": ("petroleum/stoc/wstk", {
            "frequency": "weekly", "data[0]": "value",
            "facets[series][]": "WGTSTUS1"
        }),
        # Refinery utilization (weekly)
        "PET.WPULRL3S3.W": ("petroleum/pnp/wiup", {
            "frequency": "weekly", "data[0]": "value",
            "facets[series][]": "WPULRL3S3"
        }),
        # Nat Gas storage (weekly)
        "NG.NW2_EPG0_SWO_R48_BCF.W": ("natural-gas/stor/wkly", {
            "frequency": "weekly", "data[0]": "value",
        }),
        # US gasoline demand / product supplied (weekly)
        "PET.WGFUPUS2.W": ("petroleum/cons/wpsup", {
            "frequency": "weekly", "data[0]": "value",
            "facets[series][]": "WGFUPUS2"
        }),
        # LNG exports (monthly)
        "NG.N9133US2.M": ("natural-gas/move/expc", {
            "frequency": "monthly", "data[0]": "value",
        }),
    }

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.EIA_API_KEY

    def get_series(self, series_id: str, days: int = None) -> pd.DataFrame:
        """Fetch a series from EIA API v2"""

        if not self.api_key:
            raise DataFetchError("EIA API key not configured")

        if days is None:
            days = config.DEFAULT_LOOKBACK_DAYS

        if series_id in self.ROUTE_MAP:
            route, extra_params = self.ROUTE_MAP[series_id]
        else:
            # Generic fallback
            if series_id.startswith("PET"):
                route = "petroleum/pri/spt"
            elif series_id.startswith("NG"):
                route = "natural-gas/pri/sum"
            else:
                route = "petroleum/pri/spt"
            extra_params = {"frequency": "weekly", "data[0]": "value"}

        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        url = f"{self.BASE_URL}/{route}/data/"
        params = {
            "api_key": self.api_key,
            "start": start_date,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 5000,
            **extra_params
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if not data.get("response", {}).get("data"):
                return pd.DataFrame()

            df = pd.DataFrame(data["response"]["data"])

            if "period" in df.columns:
                df["date"] = pd.to_datetime(df["period"])

            # Handle different value column names
            value_col = "value" if "value" in df.columns else "price" if "price" in df.columns else None
            if value_col:
                df[series_id] = pd.to_numeric(df[value_col], errors="coerce")
            else:
                return pd.DataFrame()

            return df[["date", series_id]].dropna().sort_values("date").reset_index(drop=True)

        except requests.exceptions.RequestException as e:
            raise DataFetchError(f"EIA API error for {series_id}: {str(e)}")

    def get_gas_prices(self, days: int = None) -> pd.DataFrame:
        """
        Get retail gas prices with multi-level fallback:
        1. Try EIA v2 /petroleum/pri/gnd with EPM0 (all grades)
        2. Try with EPMR (regular grade)
        3. Fall back to FRED GASREGW series
        """

        if not self.api_key:
            raise DataFetchError("EIA API key not configured")

        if days is None:
            days = config.DEFAULT_LOOKBACK_DAYS

        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        # Attempt 1: EPM0 (all grades)
        for product in ["EPM0", "EPMR"]:
            try:
                url = f"{self.BASE_URL}/petroleum/pri/gnd/data/"
                params = {
                    "api_key": self.api_key,
                    "frequency": "weekly",
                    "data[0]": "value",
                    "facets[product][]": product,
                    "facets[duoarea][]": "NUS",
                    "start": start_date,
                    "sort[0][column]": "period",
                    "sort[0][direction]": "desc",
                    "length": 5000,
                }

                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                if data.get("response", {}).get("data"):
                    df = pd.DataFrame(data["response"]["data"])
                    df["date"] = pd.to_datetime(df["period"])
                    df["gas_price"] = pd.to_numeric(df["value"], errors="coerce")
                    result = df[["date", "gas_price"]].dropna().sort_values("date").reset_index(drop=True)
                    if not result.empty:
                        return result

            except requests.exceptions.RequestException:
                continue

        # Attempt 3: Fall back to FRED GASREGW
        try:
            fred = FREDClient()
            df = fred.get_series("GASREGW")
            if not df.empty:
                df.columns = ["date", "gas_price"]
                return df
        except DataFetchError:
            pass

        raise DataFetchError("Could not fetch gas prices from any source")


# =============================================================================
# CUSTOM DATA STORAGE
# =============================================================================

class CustomDataStore:
    """Store for user-provided custom indicators"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.custom_file = os.path.join(data_dir, "custom_indicators.json")
        os.makedirs(data_dir, exist_ok=True)

        if not os.path.exists(self.custom_file):
            with open(self.custom_file, "w") as f:
                json.dump({}, f)

    def add_indicator(
        self,
        name: str,
        data: List[Dict[str, Any]],
        category: str = "custom",
        unit: str = ""
    ) -> bool:
        """Add or update a custom indicator"""

        with open(self.custom_file, "r") as f:
            store = json.load(f)

        store[name] = {
            "category": category,
            "unit": unit,
            "data": data,
            "updated_at": datetime.now().isoformat()
        }

        with open(self.custom_file, "w") as f:
            json.dump(store, f, indent=2)

        return True

    def get_indicator(self, name: str) -> Optional[pd.DataFrame]:
        """Get a custom indicator as DataFrame"""

        with open(self.custom_file, "r") as f:
            store = json.load(f)

        if name not in store:
            return None

        df = pd.DataFrame(store[name]["data"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        return df

    def list_indicators(self) -> Dict[str, Any]:
        """List all custom indicators"""

        with open(self.custom_file, "r") as f:
            store = json.load(f)

        return {
            name: {
                "category": info["category"],
                "unit": info["unit"],
                "updated_at": info["updated_at"],
                "records": len(info["data"])
            }
            for name, info in store.items()
        }

    def delete_indicator(self, name: str) -> bool:
        """Delete a custom indicator"""

        with open(self.custom_file, "r") as f:
            store = json.load(f)

        if name in store:
            del store[name]
            with open(self.custom_file, "w") as f:
                json.dump(store, f, indent=2)
            return True

        return False


# =============================================================================
# UNIFIED DATA MANAGER (Legacy — use HybridDataManager from s3_reader.py)
# =============================================================================

class EconomicDataManager:
    """Unified manager for all data sources (direct API mode)"""

    def __init__(self):
        self.fred = FREDClient()
        self.bls = BLSClient()
        self.treasury = TreasuryClient()
        self.eia = EIAClient()
        self.custom = CustomDataStore()

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Get latest values for key metrics"""

        metrics = {}

        key_series = [
            ("ICSA", "Initial Claims"),
            ("UNRATE", "Unemployment"),
            ("DGS10", "10Y Yield"),
            ("T10Y2Y", "Yield Spread"),
            ("UMCSENT", "Consumer Sentiment"),
        ]

        for series_id, name in key_series:
            try:
                df = self.fred.get_series(series_id)
                if not df.empty:
                    latest = df.iloc[-1]
                    prev = df.iloc[-2] if len(df) > 1 else latest

                    metrics[name] = {
                        "value": latest[series_id],
                        "change": latest[series_id] - prev[series_id],
                        "date": latest["date"].strftime("%Y-%m-%d")
                    }
            except Exception:
                continue

        return metrics
