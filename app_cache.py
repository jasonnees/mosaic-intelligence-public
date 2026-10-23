"""Cache plain payloads, reconstruct app-specific classes outside pickle boundaries.

A module reload can leave a resource holding an older result-class identity.
Pickle rejects that object even though its fields are ordinary serializable data.
Keep only DataFrames and built-in metadata in st.cache_data.
"""
import streamlit as st
import config
from risk_catalog import BY_ID
from risk_data import RiskDataService

@st.cache_resource
def service():
    archive = None
    if config.DATA_SOURCE_MODE == 's3':
        try:
            from s3_reader import S3DataReader
            candidate = S3DataReader()
            if candidate.available:
                archive = candidate
        except Exception:
            pass
    return RiskDataService(archive=archive)

@st.cache_data(ttl=3600, show_spinner=False)
def indicator_payload(series_id, days):
    result = service().fetch(BY_ID[series_id], days)
    return dict(frame=result.frame, provenance=result.provenance,
                fetched_at=result.fetched_at, error=result.error)

def fetch(series_id, days):
    from risk_data import FetchResult
    return FetchResult(**indicator_payload(series_id, days))

fetch.clear = indicator_payload.clear
