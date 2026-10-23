"""
Market Risk Explorer — FastAPI Backend
Provides API endpoints for custom data input
"""

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uvicorn

from data_fetcher import CustomDataStore, EconomicDataManager, DataFetchError

app = FastAPI(
    title="Market Risk Explorer API",
    description="API for feeding custom indicators into Market Risk Explorer",
    version="1.0.0"
)

# Enable CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize data store
custom_store = CustomDataStore()
data_manager = EconomicDataManager()


# =============================================================================
# MODELS
# =============================================================================

class DataPoint(BaseModel):
    date: str  # ISO format: YYYY-MM-DD
    value: float

class IndicatorCreate(BaseModel):
    name: str
    category: str = "custom"  # consumer, smb, macro, custom
    unit: str = ""
    data: List[DataPoint]

class IndicatorUpdate(BaseModel):
    data: List[DataPoint]
    append: bool = True  # If True, append to existing; if False, replace

class IndicatorResponse(BaseModel):
    name: str
    category: str
    unit: str
    record_count: int
    updated_at: str


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """Health check and API info"""
    return {
        "status": "healthy",
        "name": "Economic Dashboard API",
        "version": "1.0.0",
        "endpoints": {
            "POST /indicators": "Create a new custom indicator",
            "GET /indicators": "List all custom indicators",
            "GET /indicators/{name}": "Get indicator data",
            "PUT /indicators/{name}": "Update indicator data",
            "DELETE /indicators/{name}": "Delete an indicator",
            "GET /summary": "Get summary metrics from all sources",
        }
    }


@app.post("/indicators", response_model=IndicatorResponse)
async def create_indicator(indicator: IndicatorCreate):
    """
    Create a new custom indicator.
    
    Example:
    ```
    POST /indicators
    {
        "name": "atlas_aum",
        "category": "custom",
        "unit": "millions USD",
        "data": [
            {"date": "2024-01-01", "value": 100.5},
            {"date": "2024-02-01", "value": 105.2}
        ]
    }
    ```
    """
    
    # Convert to list of dicts
    data_list = [{"date": dp.date, "value": dp.value} for dp in indicator.data]
    
    success = custom_store.add_indicator(
        name=indicator.name,
        data=data_list,
        category=indicator.category,
        unit=indicator.unit
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create indicator")
    
    return IndicatorResponse(
        name=indicator.name,
        category=indicator.category,
        unit=indicator.unit,
        record_count=len(data_list),
        updated_at=datetime.now().isoformat()
    )


@app.get("/indicators")
async def list_indicators():
    """List all custom indicators"""
    return custom_store.list_indicators()


@app.get("/indicators/{name}")
async def get_indicator(name: str, format: str = "json"):
    """
    Get indicator data.
    
    Parameters:
    - name: Indicator name
    - format: Output format (json or csv)
    """
    
    df = custom_store.get_indicator(name)
    
    if df is None:
        raise HTTPException(status_code=404, detail=f"Indicator '{name}' not found")
    
    if format == "csv":
        return df.to_csv(index=False)
    
    return {
        "name": name,
        "data": df.to_dict(orient="records")
    }


@app.put("/indicators/{name}")
async def update_indicator(name: str, update: IndicatorUpdate):
    """
    Update an existing indicator's data.
    
    If append=True, new data points are added to existing data.
    If append=False, existing data is replaced entirely.
    """
    
    existing = custom_store.list_indicators()
    
    if name not in existing:
        raise HTTPException(status_code=404, detail=f"Indicator '{name}' not found")
    
    if update.append:
        # Get existing data and append
        df = custom_store.get_indicator(name)
        existing_data = df.to_dict(orient="records")
        new_data = [{"date": dp.date, "value": dp.value} for dp in update.data]
        
        # Merge by date, preferring new values
        data_dict = {d["date"]: d["value"] for d in existing_data}
        for d in new_data:
            data_dict[d["date"]] = d["value"]
        
        merged_data = [{"date": k, "value": v} for k, v in sorted(data_dict.items())]
    else:
        merged_data = [{"date": dp.date, "value": dp.value} for dp in update.data]
    
    info = existing[name]
    custom_store.add_indicator(
        name=name,
        data=merged_data,
        category=info["category"],
        unit=info["unit"]
    )
    
    return {
        "name": name,
        "record_count": len(merged_data),
        "updated_at": datetime.now().isoformat()
    }


@app.delete("/indicators/{name}")
async def delete_indicator(name: str):
    """Delete a custom indicator"""
    
    success = custom_store.delete_indicator(name)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Indicator '{name}' not found")
    
    return {"status": "deleted", "name": name}


@app.get("/summary")
async def get_summary():
    """Get summary metrics from all official data sources"""
    
    try:
        metrics = data_manager.get_summary_metrics()
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fred/{series_id}")
async def get_fred_series(series_id: str, days: int = 365):
    """Fetch a specific FRED series"""
    
    try:
        df = data_manager.fred.get_series(series_id)
        return {
            "series_id": series_id,
            "source": "FRED",
            "records": len(df),
            "data": df.to_dict(orient="records")
        }
    except DataFetchError as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# BATCH ENDPOINTS
# =============================================================================

class BatchRequest(BaseModel):
    indicators: List[IndicatorCreate]

@app.post("/indicators/batch")
async def create_batch_indicators(batch: BatchRequest):
    """Create multiple indicators at once"""
    
    results = []
    for indicator in batch.indicators:
        data_list = [{"date": dp.date, "value": dp.value} for dp in indicator.data]
        
        custom_store.add_indicator(
            name=indicator.name,
            data=data_list,
            category=indicator.category,
            unit=indicator.unit
        )
        
        results.append({
            "name": indicator.name,
            "records": len(data_list),
            "status": "created"
        })
    
    return {"created": len(results), "results": results}


# =============================================================================
# RUN SERVER
# =============================================================================

def start_api_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the FastAPI server"""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_api_server()
