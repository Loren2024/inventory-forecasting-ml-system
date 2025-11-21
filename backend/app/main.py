from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .db import fetch_all, fetch_one

app = FastAPI(title="Inventory Forecasting API")

# CORS para desarrollo: permite llamadas desde tu dashboard en 127.0.0.1:5500
origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      # si quieres, puedes poner ["*"] mientras desarrollas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from pydantic import BaseModel
from typing import List

class GlobalKpis(BaseModel):
    total_skus: int
    mape_train_arima: float
    mape_train_rf: float
    mape_train_xgb: float
    mape_val_hybrid_q1: float
    ratio_pred_vs_real_pct: float
    real_total_q1: int
    pred_total_q1: float

@app.get("/api/kpis/global", response_model=GlobalKpis)
def get_global_kpis():
    """
    KPIs globales simulados, coherentes con los resultados de validación.
    Estos valores vienen de los experimentos en Colab.
    """
    return GlobalKpis(
        total_skus=20,
        mape_train_arima=19.25,
        mape_train_rf=16.80,
        mape_train_xgb=17.14,
        mape_val_hybrid_q1=24.64,
        ratio_pred_vs_real_pct=98.67,
        real_total_q1=12383,
        pred_total_q1=12218.06,
    )


class TopSkuError(BaseModel):
    sku: str
    mape_q1: float
    rmse_q1: float

# Datos simulados (copiados de tus resultados reales en Colab)
TOP_SKUS_Q1 = [
    {"sku": "FJMNE49Q", "mape_q1": 54.1185, "rmse_q1": 1.4606},
    {"sku": "MVRHK0O7", "mape_q1": 52.4550, "rmse_q1": 1.9388},
    {"sku": "US50K9EP", "mape_q1": 47.3330, "rmse_q1": 1.8645},
    {"sku": "CDP3EIW8", "mape_q1": 44.6259, "rmse_q1": 1.2614},
    {"sku": "DMJ3FA8T", "mape_q1": 36.6125, "rmse_q1": 1.4534},
    {"sku": "LFXCTNCS", "mape_q1": 28.8889, "rmse_q1": 1.5973},
    {"sku": "9PDVDUT8", "mape_q1": 25.9738, "rmse_q1": 1.5560},
    {"sku": "0GEF63F3", "mape_q1": 23.9751, "rmse_q1": 2.8572},
    {"sku": "CDQMR9VA", "mape_q1": 23.0696, "rmse_q1": 1.6786},
    {"sku": "OKEPTZ9Y", "mape_q1": 21.9185, "rmse_q1": 1.6695},
]

@app.get("/api/top_skus/error", response_model=List[TopSkuError])
def get_top_skus_error(limit: int = 10):
    """
    Devuelve el top de SKUs con mayor error en Q1-2025,
    ordenados por MAPE descendente.
    """
    data_sorted = sorted(TOP_SKUS_Q1, key=lambda x: x["mape_q1"], reverse=True)
    return [TopSkuError(**row) for row in data_sorted[:limit]]




# ------------------ KPIs globales ------------------
@app.get("/api/kpis/global")
def get_global_kpis():
    sql_eval = """
        SELECT
            AVG(mape_q1_2025)   AS mape_avg_q1,
            AVG(rmse_q1_2025)   AS rmse_avg_q1
        FROM inv.model_eval;
    """
    eval_row = fetch_one(sql_eval) or {}

    sql_real = """
        SELECT COALESCE(SUM(quantity), 0) AS total_real
        FROM inv.inventory_movements
        WHERE movement_type = 'OUT'
          AND ts BETWEEN DATE '2025-01-01' AND DATE '2025-03-31';
    """
    real_row = fetch_one(sql_real) or {}

    sql_pred = """
        SELECT COALESCE(SUM(y_hat), 0) AS total_pred
        FROM inv.forecast
        WHERE ds BETWEEN DATE '2025-01-01' AND DATE '2025-03-31';
    """
    pred_row = fetch_one(sql_pred) or {}

    total_real = float(real_row.get("total_real") or 0.0)
    total_pred = float(pred_row.get("total_pred") or 0.0)
    ratio = (total_pred / total_real * 100.0) if total_real > 0 else None

    return {
        "mape_avg_q1": round(float(eval_row.get("mape_avg_q1") or 0.0), 2),
        "rmse_avg_q1": round(float(eval_row.get("rmse_avg_q1") or 0.0), 2),
        "total_real_q1": total_real,
        "total_pred_q1": round(total_pred, 2),
        "ratio_pred_vs_real_pct": round(ratio, 2) if ratio is not None else None
    }

# ------------------ Catálogo de SKUs ------------------
@app.get("/api/skus")
def get_skus():
    sql = """
        SELECT DISTINCT sku, product_name, family, category
        FROM inv.products
        ORDER BY sku;
    """
    return fetch_all(sql)

# ------------------ Histórico OUT por SKU ------------------
@app.get("/api/history/{sku}")
def get_history_for_sku(sku: str):
    sql = """
        SELECT
            ts::date AS date,
            SUM(quantity) AS y_real
        FROM inv.inventory_movements
        WHERE sku = %(sku)s
          AND movement_type = 'OUT'
        GROUP BY ts::date
        ORDER BY date;
    """
    rows = fetch_all(sql, {"sku": sku})
    if not rows:
        raise HTTPException(status_code=404, detail="SKU sin histórico")
    return rows

# ------------------ Forecast híbrido por SKU ------------------
@app.get("/api/forecast/{sku}")
def get_forecast_for_sku(sku: str):
    sql = """
        SELECT sku, ds AS date, y_hat_min, y_hat, y_hat_max, model_type
        FROM inv.forecast
        WHERE sku = %(sku)s
        ORDER BY ds;
    """
    rows = fetch_all(sql, {"sku": sku})
    if not rows:
        raise HTTPException(status_code=404, detail="SKU sin forecast")
    return rows

# ------------------ Top SKUs por error en Q1-2025 ------------------
@app.get("/api/top_skus/error")
def get_top_skus_error(limit: int = 10):
    sql = """
        SELECT
            e.sku,
            p.product_name,
            p.family,
            p.category,
            e.mape_q1_2025,
            e.rmse_q1_2025
        FROM inv.model_eval e
        LEFT JOIN inv.products p ON p.sku = e.sku
        ORDER BY e.mape_q1_2025 DESC
        LIMIT %(limit)s;
    """
    return fetch_all(sql, {"limit": limit})

# ------------------ Promedios de desempeño por modelo ------------------
@app.get("/api/model/performance")
def get_model_performance():
    sql = """
        SELECT
            AVG(mape_arima) AS mape_arima_avg,
            AVG(mape_rf)    AS mape_rf_avg,
            AVG(mape_xgb)   AS mape_xgb_avg,
            AVG(rmse_arima) AS rmse_arima_avg,
            AVG(rmse_rf)    AS rmse_rf_avg,
            AVG(rmse_xgb)   AS rmse_xgb_avg
        FROM inv.model_meta;
    """
    row = fetch_one(sql) or {}
    return {
        "mape": {
            "ARIMA": round(float(row.get("mape_arima_avg") or 0.0), 2),
            "RF":    round(float(row.get("mape_rf_avg") or 0.0), 2),
            "XGB":   round(float(row.get("mape_xgb_avg") or 0.0), 2),
        },
        "rmse": {
            "ARIMA": round(float(row.get("rmse_arima_avg") or 0.0), 2),
            "RF":    round(float(row.get("rmse_rf_avg") or 0.0), 2),
            "XGB":   round(float(row.get("rmse_xgb_avg") or 0.0), 2),
        },
    }

# ------------------ Conteo de campeones por SKU ------------------
@app.get("/api/model/champions")
def get_model_champions():
    sql = """
        SELECT
            sku,
            mape_arima,
            mape_rf,
            mape_xgb
        FROM inv.model_meta;
    """
    rows = fetch_all(sql)
    counts = {"ARIMA": 0, "RF": 0, "XGB": 0}

    for r in rows:
        m_dict = {
            "ARIMA": float(r["mape_arima"]) if r["mape_arima"] is not None else None,
            "RF":    float(r["mape_rf"])    if r["mape_rf"]    is not None else None,
            "XGB":   float(r["mape_xgb"])   if r["mape_xgb"]   is not None else None,
        }
        valid = {k: v for k, v in m_dict.items() if v is not None}
        if not valid:
            continue
        champion = min(valid, key=valid.get)
        counts[champion] += 1

    total = sum(counts.values()) or 1
    pct = {k: round(v / total * 100.0, 2) for k, v in counts.items()}

    return {
        "counts": counts,
        "percentages": pct,
        "total_skus": total
    }



