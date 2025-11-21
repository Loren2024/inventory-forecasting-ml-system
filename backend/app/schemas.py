from pydantic import BaseModel
from typing import List, Optional

class ForecastRow(BaseModel):
    sku: str
    ds: str
    y_hat_min: float
    y_hat: float
    y_hat_max: float
    model_type: str

class SkuInfo(BaseModel):
    sku: str
    product_name: str
    family: str
    category: str
    warehouse: str
    base_price: float

class MetricRow(BaseModel):
    sku: str
    mape_arima: float
    rmse_arima: float
    mape_rf: float
    rmse_rf: float
    mape_xgb: float
    rmse_xgb: float

class EvalRow(BaseModel):
    sku: str
    mape_q1: float
    rmse_q1: float
