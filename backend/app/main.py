from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor
from typing import List, Optional, Dict, Any
from datetime import date, timedelta

from .db import fetch_all, fetch_one

SCHEMA = "inv"

app = FastAPI(title="Inventory Forecasting API")

origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 0) STOCK SIMULADO (Opción 1)
#    - Se usa solo para demo operativa (TSP)
#    - Puedes editar valores o poner random controlado
# ============================================================

DEFAULT_STOCK = 300  # stock base si no hay valor específico

SIM_STOCK: Dict[str, float] = {
    # Puedes dejar algunos definidos (ejemplo) y el resto usa DEFAULT_STOCK
    "FJMNE49Q": 120,
    "MVRHK0O7": 150,
    "US50K9EP": 180,
    "CDP3EIW8": 100,
    "DMJ3FA8T": 90,
    "GIIRVJAP": 160,
}

def get_sim_stock(sku: str) -> float:
    return float(SIM_STOCK.get(sku, DEFAULT_STOCK))

# ============================================================
# 1) KPIs globales (45 días Q1-2025)
# ============================================================

@app.get("/api/kpis/global")
def get_global_kpis():
    sql_eval = f"""
        SELECT
            AVG(mape_q1) AS mape_val_hybrid_q1,
            AVG(rmse_q1) AS rmse_val_hybrid_q1,
            COUNT(DISTINCT sku) AS total_skus
        FROM {SCHEMA}.model_eval;
    """
    eval_row = fetch_one(sql_eval) or {}

    sql_real = f"""
        SELECT COALESCE(SUM(quantity),0) AS real_total_q1
        FROM {SCHEMA}.inventory_movements_stage
        WHERE movement_type = 'OUT'
          AND ts BETWEEN DATE '2025-01-01' AND DATE '2025-02-14';
    """
    real_row = fetch_one(sql_real) or {}

    sql_pred = f"""
        SELECT COALESCE(SUM(y_hat),0) AS pred_total_q1
        FROM {SCHEMA}.forecast
        WHERE ds BETWEEN DATE '2025-01-01' AND DATE '2025-02-14';
    """
    pred_row = fetch_one(sql_pred) or {}

    real_total = float(real_row.get("real_total_q1") or 0.0)
    pred_total = float(pred_row.get("pred_total_q1") or 0.0)
    ratio = (pred_total / real_total * 100.0) if real_total > 0 else None

    return {
        "total_skus": int(eval_row.get("total_skus") or 0),
        "mape_val_hybrid_q1": round(float(eval_row.get("mape_val_hybrid_q1") or 0.0), 2),
        "rmse_val_hybrid_q1": round(float(eval_row.get("rmse_val_hybrid_q1") or 0.0), 4),
        "real_total_q1": round(real_total, 0),
        "pred_total_q1": round(pred_total, 2),
        "ratio_pred_vs_real_pct": round(ratio, 2) if ratio else None
    }

# ============================================================
# 2) Catálogo SKUs
# ============================================================

@app.get("/api/skus")
def get_skus():
    sql = f"""
        SELECT sku, product_name, family, category
        FROM {SCHEMA}.products
        ORDER BY sku;
    """
    return fetch_all(sql)

# ============================================================
# 3) Histórico por SKU (OUT)
# ============================================================

@app.get("/api/history/{sku}")
def get_history_for_sku(sku: str):
    sql = f"""
        SELECT ts::date AS date, SUM(quantity) AS y
        FROM {SCHEMA}.inventory_movements
        WHERE sku = %(sku)s AND movement_type='OUT'
        GROUP BY ts::date
        ORDER BY date;
    """
    rows = fetch_all(sql, {"sku": sku})
    if not rows:
        raise HTTPException(status_code=404, detail="SKU sin histórico")
    return rows


# ============================================================
# 5) Real Q1-2025 (45 días) por SKU
# ============================================================

@app.get("/api/real/sku/{sku}")
def get_real_45_for_sku(sku: str):
    sql = f"""
        SELECT ts::date AS date, SUM(quantity) AS y
        FROM {SCHEMA}.inventory_movements_stage
        WHERE sku=%(sku)s AND movement_type='OUT'
          AND ts BETWEEN DATE '2025-01-01' AND DATE '2025-02-14'
        GROUP BY ts::date
        ORDER BY date;
    """
    return fetch_all(sql, {"sku": sku})

# ============================================================
# 6) Top SKUs con mayor error (NO duplicados)
# ============================================================

@app.get("/api/top_skus/error")
def get_top_skus_error(limit: int = 10):
    sql = f"""
        SELECT
            e.sku,
            e.mape_q1 AS mape_45d,
            e.rmse_q1 AS rmse_45d
        FROM {SCHEMA}.model_eval e
        ORDER BY e.mape_q1 DESC
        LIMIT %(limit)s;
    """
    return fetch_all(sql, {"limit": limit})

# ============================================================
# 7) Compare series para el chart principal
# ============================================================

@app.get("/api/forecast_compare")
def forecast_compare(sku: str):
    hist_sql = f"""
        SELECT ts::date AS date, SUM(quantity) AS y
        FROM {SCHEMA}.inventory_movements
        WHERE sku=%(sku)s AND movement_type='OUT'
        GROUP BY ts::date
        ORDER BY date DESC
        LIMIT 60;
    """
    hist = fetch_all(hist_sql, {"sku": sku})
    hist = list(reversed(hist))

    pred_sql = f"""
        SELECT ds::date AS date, y_hat AS y
        FROM {SCHEMA}.forecast
        WHERE sku=%(sku)s
          AND ds BETWEEN DATE '2025-01-01' AND DATE '2025-02-14'
        ORDER BY ds;
    """
    pred = fetch_all(pred_sql, {"sku": sku})

    real_sql = f"""
        SELECT ts::date AS date, SUM(quantity) AS y
        FROM {SCHEMA}.inventory_movements_stage
        WHERE sku=%(sku)s AND movement_type='OUT'
          AND ts BETWEEN DATE '2025-01-01' AND DATE '2025-02-14'
        GROUP BY ts::date
        ORDER BY date;
    """
    real = fetch_all(real_sql, {"sku": sku})

    if not pred:
        raise HTTPException(status_code=404, detail="SKU sin forecast")

    return {"sku_used": sku, "hist": hist, "pred": pred, "real": real}

# ============================================================
# 8) ALERTAS Y REPOSICIÓN (con stock simulado)
# ============================================================

def avg_daily_demand_45(sku: str) -> float:
    sql = f"""
        SELECT AVG(y_hat) AS avg_demand
        FROM {SCHEMA}.forecast
        WHERE sku=%(sku)s
          AND ds BETWEEN DATE '2025-01-01' AND DATE '2025-02-14';
    """
    row = fetch_one(sql, {"sku": sku}) or {}
    return float(row.get("avg_demand") or 0.0)

def classify_status(coverage_days):
    if coverage_days is None:
        return "SIN_DATO"
    if coverage_days < 3:
        return "QUIEBRE"
    if coverage_days < 10:
        return "RIESGO"
    return "OK"


@app.get("/api/replenishment/all")
def replenishment_all(limit: int = 20):
    skus = fetch_all(f"SELECT DISTINCT sku FROM {SCHEMA}.forecast")
    out = []

    for r in skus:
        sku = r["sku"]
        stock = get_sim_stock(sku)
        dem = avg_daily_demand_45(sku)

        coverage = (stock / dem) if dem > 0 else None
        status = classify_status(coverage)

        # regla simple de pedido para demo:
        target_days = 30  # objetivo de cobertura
        qty_to_order = max(target_days * dem - stock, 0) if dem > 0 else None

        break_date = (date.today() + timedelta(days=int(coverage))) if coverage else None

        out.append({
            "sku": sku,
            "stock_actual": round(stock, 2),
            "avg_daily_demand": round(dem, 3),
            "coverage_days": round(coverage, 2) if coverage else None,
            "status": status,
            "qty_to_order": round(qty_to_order, 2) if qty_to_order is not None else None,
            "break_date": str(break_date) if break_date else None
        })

    # ordenar por urgencia
    priority = {"QUIEBRE": 0, "RIESGO": 1, "OK": 2, "SIN_DATO": 3}
    out.sort(key=lambda x: (priority.get(x["status"], 9), x["coverage_days"] or 9e9))
    return out[:limit]

@app.get("/api/alerts/reorder")
def alerts_reorder(limit: int = 10):
    data = replenishment_all(limit=999)
    alerts = [d for d in data if d["status"] in ("QUIEBRE", "RIESGO")]
    return alerts[:limit]


# ============================================================
# 4) Forecast híbrido por SKU
# ============================================================

@app.get("/api/forecast/{sku}")
def get_forecast_for_sku(sku: str):
    sql = f"""
        SELECT sku, ds::date AS date, y_hat_min, y_hat, y_hat_max, model_type
        FROM {SCHEMA}.forecast
        WHERE sku = %(sku)s
        ORDER BY ds;
    """
    rows = fetch_all(sql, {"sku": sku})
    if not rows:
        raise HTTPException(status_code=404, detail="SKU sin forecast")
    return rows
