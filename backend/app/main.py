# ============================================================
# Inventory Forecasting API – Simulación Profesional 2025 (Determinística)
# ============================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from datetime import date, timedelta

from .db import fetch_all, fetch_one, SCHEMA


# ============================================================
# CONFIG API
# ============================================================

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
# PRODUCT MAP (para simulación basada en categoría/familia)
# ============================================================

PRODUCT_MAP: Dict[str, Dict[str, Any]] = {}

def load_product_map():
    """Carga catálogo de productos para simulación."""
    global PRODUCT_MAP
    rows = fetch_all(f"SELECT sku, category, family FROM {SCHEMA}.products")
    PRODUCT_MAP = {r["sku"]: r for r in rows}

load_product_map()


# ============================================================
# SIMULACIÓN DETERMINÍSTICA DE STOCK Y DEMANDA
# ============================================================

# Stock base por categoría
CATEGORY_BASE = {
    "Premium": 10,      # inventario bajo → multiplica 10x rotación diaria
    "Industrial": 20,   # alta rotación → multiplica 20x rotación diaria
    "Estándar": 15,     # rotación media
}

# Ajustes por familia
FAMILY_MULTIPLIER = {
    "Herramientas": 1.3,
    "Pinturas": 1.1,
    "Seguridad": 0.8,
}

# Modo estrés (campañas, proyectos, estacionalidad)
STRESS_MODE = True

# Cachés
ROTATION_CACHE = {}
SIM_STOCK_CACHE = {}


def get_rotation_for_sku(sku: str) -> float:
    """Rotación diaria promedio del SKU basada en OUTs históricos."""
    if sku in ROTATION_CACHE:
        return ROTATION_CACHE[sku]

    sql = f"""
        SELECT ts::date AS fecha, SUM(quantity) AS daily_out
        FROM {SCHEMA}.inventory_movements
        WHERE sku=%s AND movement_type='OUT'
        GROUP BY fecha;
    """
    rows = fetch_all(sql, (sku,))

    if not rows:
        ROTATION_CACHE[sku] = 1.0
        return 1.0

    rot = sum(r["daily_out"] for r in rows) / len(rows)
    ROTATION_CACHE[sku] = max(rot, 0.5)  # evitar rot 0
    return ROTATION_CACHE[sku]


def get_q1_factor(sku: str) -> float:
    """Ajuste según importancia del SKU en Q1-2025."""
    sql = f"""
        SELECT SUM(quantity) AS vol
        FROM {SCHEMA}.inventory_movements_stage
        WHERE sku=%s AND movement_type='OUT'
          AND ts BETWEEN DATE '2025-01-01' AND DATE '2025-02-14';
    """
    row = fetch_one(sql, (sku,)) or {"vol": 1}
    vol = float(row["vol"] or 1)

    # Valor promedio aproximado del dataset Q1-2025
    avg_vol = 300.0
    factor = vol / avg_vol

    # Normalizamos a rango 0.5–2.0
    return max(0.5, min(2.0, factor))


def simulate_stock_for_sku(sku: str) -> int:
    """Stock inicial simulado de forma determinística basada en datos reales."""
    if sku in SIM_STOCK_CACHE:
        return SIM_STOCK_CACHE[sku]

    info = PRODUCT_MAP.get(sku, {})
    category = info.get("category", "Industrial")
    family = info.get("family", None)

    rot = get_rotation_for_sku(sku)
    base = CATEGORY_BASE.get(category, 15)

    # asegurar que todo sea float
    rot = float(rot)
    base = float(base)

    stock = rot * base

    if family:
        stock = float(stock) * float(FAMILY_MULTIPLIER.get(family, 1.0))

    stock = float(stock) * float(get_q1_factor(sku))

    stock = int(max(5, stock))  # nunca menos de 5 unidades
    # nunca menos de 5 unidades

    SIM_STOCK_CACHE[sku] = stock
    return stock


def demand_stats_45(sku: str) -> float:
    """Demanda diaria simulada usando forecast (escenario conservador)."""
    sql = f"""
        SELECT 
            AVG(y_hat_min) AS dem_min,
            AVG(y_hat)     AS dem_central,
            AVG(y_hat_max) AS dem_max
        FROM {SCHEMA}.forecast
        WHERE sku=%(sku)s
          AND ds BETWEEN DATE '2025-01-01' AND DATE '2025-02-14';
    """
    row = fetch_one(sql, {"sku": sku}) or {}

    dem_max = float(row["dem_max"] or 0)

    # Ajustar según familia
    family = PRODUCT_MAP.get(sku, {}).get("family", None)
    if family:
        dem_max *= FAMILY_MULTIPLIER.get(family, 1.0)

    # Escenario de estrés
    if STRESS_MODE:
        dem_max *= 1.5

    return dem_max


def classify_status(coverage_days):
    """Clasificación operativa."""
    if coverage_days is None:
        return "SIN_DATO"
    if coverage_days < 5:
        return "QUIEBRE"
    if coverage_days < 15:
        return "RIESGO"
    return "OK"


# ============================================================
# 1) KPI GLOBAL (HOME)
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

    real_total = float(real_row.get("real_total_q1") or 0)
    pred_total = float(pred_row.get("pred_total_q1") or 0)
    ratio = (pred_total / real_total * 100) if real_total > 0 else None

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
# 3) Histórico por SKU
# ============================================================

@app.get("/api/history/{sku}")
def get_history_for_sku(sku: str):
    sql = f"""
        SELECT ts::date AS date, SUM(quantity) AS y
        FROM {SCHEMA}.inventory_movements
        WHERE sku=%(sku)s AND movement_type='OUT'
        GROUP BY ts::date
        ORDER BY date;
    """
    rows = fetch_all(sql, {"sku": sku})
    if not rows:
        raise HTTPException(status_code=404, detail="SKU sin histórico")
    return rows


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


# ============================================================
# 5) Real Q1-2025 por SKU
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
# 6) TOP SKUs error
# ============================================================

@app.get("/api/top_skus/error")
def get_top_skus_error(limit: int = 10):
    sql = f"""
        SELECT sku, mape_q1 AS mape_45d, rmse_q1 AS rmse_45d
        FROM {SCHEMA}.model_eval
        ORDER BY mape_q1 DESC
        LIMIT %(limit)s;
    """
    return fetch_all(sql, {"limit": limit})


# ============================================================
# 7) Forecast compare para gráfico principal
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

    return {"sku_used": sku, "hist": hist, "pred": pred, "real": real}


# ============================================================
# 8) Comparativo interanual por SKU
#    - 2022–2024: OUT en inventory_movements
#    - Q1-2025: OUT en inventory_movements_stage
# ============================================================

@app.get("/api/interannual")
def interannual_compare(sku: str):
    # Histórico 2022–2024
    sql_hist = f"""
        SELECT 
            EXTRACT(YEAR FROM ts)::int AS year,
            SUM(quantity) AS total_out
        FROM {SCHEMA}.inventory_movements
        WHERE sku = %(sku)s
          AND movement_type = 'OUT'
          AND ts::date BETWEEN DATE '2022-01-01' AND DATE '2024-12-31'
        GROUP BY year
        ORDER BY year;
    """
    hist_rows = fetch_all(sql_hist, {"sku": sku}) or []

    # Q1-2025 (primeros 45 días)
    sql_q1 = f"""
        SELECT 
            COALESCE(SUM(quantity), 0) AS total_out
        FROM {SCHEMA}.inventory_movements_stage
        WHERE sku = %(sku)s
          AND movement_type = 'OUT'
          AND ts BETWEEN DATE '2025-01-01' AND DATE '2025-02-14';
    """
    q1_row = fetch_one(sql_q1, {"sku": sku}) or {"total_out": 0}

    result = []

    for r in hist_rows:
        result.append({
            "label": str(int(r["year"])),
            "total_out": float(r["total_out"] or 0)
        })

    # Agregamos Q1-2025 como una barra separada
    result.append({
        "label": "Q1 2025",
        "total_out": float(q1_row["total_out"] or 0)
    })

    return result


# ============================================================
# 9) ALERTAS Y REPOSICIÓN – Simulación Profesional Determinística
# ============================================================

@app.get("/api/replenishment/all")
def replenishment_all(limit: int = 50):

    skus = fetch_all(f"SELECT DISTINCT sku FROM {SCHEMA}.forecast")
    out = []

    for r in skus:
        sku = r["sku"]

        # 1. Stock basado en categoría/familia/rotación/Q1
        stock = simulate_stock_for_sku(sku)

        # 2. Demanda simulada basada en forecast
        dem = demand_stats_45(sku)

        # 3. Cobertura
        coverage = (stock / dem) if dem > 0 else None

        # 4. Estado
        status = classify_status(coverage)

        # 5. Sugerencia de reposición
        target_days = 30
        qty_to_order = max(int(target_days * dem - stock), 0) if dem > 0 else 0

        # 6. Fecha de quiebre simulada basada en enero 2025
        fecha_base = date(2025, 1, 1)
        if coverage:
            fecha_proyectada = fecha_base + timedelta(days=int(coverage))
            horizonte = date(2025, 2, 14)

            break_date = (
                fecha_proyectada.strftime("%Y-%m-%d")
                if fecha_proyectada <= horizonte
                else "> horizonte del modelo"
            )
        else:
            break_date = None

        out.append({
            "sku": sku,
            "stock_actual": stock,
            "avg_daily_demand": round(dem, 2),
            "coverage_days": round(coverage, 1) if coverage else None,
            "status": status,
            "qty_to_order": qty_to_order,
            "break_date": break_date
        })

    # ordenar por prioridad
    priority = {"QUIEBRE": 0, "RIESGO": 1, "OK": 2, "SIN_DATO": 3}
    out.sort(key=lambda x: (priority.get(x["status"], 9), x["coverage_days"] or 9999))

    return out[:limit]


@app.get("/api/alerts/reorder")
def alerts_reorder(limit: int = 10):
    data = replenishment_all(limit=999)
    alerts = [d for d in data if d["status"] in ("QUIEBRE", "RIESGO")]
    return alerts[:limit]


# ============================================================
# 10) KPIs ejecutivos del portafolio
# ============================================================

@app.get("/api/kpis/portfolio")
def get_portfolio_kpis():

    data = replenishment_all(limit=999)  # ya calcula stock, demanda, cobertura, etc.

    if not data:
        return {
            "total_alertas": 0,
            "quiebre": 0,
            "riesgo": 0,
            "avg_coverage": None,
            "total_reposicion": 0,
            "brecha_stock": 0
        }

    total_alertas = sum(1 for d in data if d["status"] in ("QUIEBRE", "RIESGO"))
    quiebre = sum(1 for d in data if d["status"] == "QUIEBRE")
    riesgo = sum(1 for d in data if d["status"] == "RIESGO")

    avg_coverage = sum((d["coverage_days"] or 0) for d in data) / len(data)

    total_reposicion = sum((d["qty_to_order"] or 0) for d in data)

    # brecha = demanda total 45d - stock total simulado
    total_stock = sum(d["stock_actual"] for d in data)
    total_demanda = sum(d["avg_daily_demand"] * 45 for d in data)
    brecha_stock = max(0, int(total_demanda - total_stock))

    return {
        "total_alertas": total_alertas,
        "quiebre": quiebre,
        "riesgo": riesgo,
        "avg_coverage": avg_coverage,
        "total_reposicion": total_reposicion,
        "brecha_stock": brecha_stock,
    }

# ============================================================
# 11) Top SKUs con mayor rotación histórica (2022–2024)
# ============================================================

@app.get("/api/top_skus/rotation")
def get_top_rotation(limit: int = 10):
    sql = f"""
        SELECT sku, SUM(quantity) AS total_out
        FROM {SCHEMA}.inventory_movements
        WHERE movement_type='OUT'
        GROUP BY sku
        ORDER BY total_out DESC
        LIMIT %(limit)s;
    """
    return fetch_all(sql, {"limit": limit})


# ============================================================
# 12) Cobertura promedio por familia (basado en simulación)
# ============================================================

@app.get("/api/family_coverage")
def family_coverage():

    data = replenishment_all(limit=999)

    # mapear familias
    family_map = {p["sku"]: p["family"] for p in fetch_all(f"SELECT sku, family FROM {SCHEMA}.products")}

    agg = {}
    for d in data:
        fam = family_map.get(d["sku"], "Sin familia")
        if fam not in agg:
            agg[fam] = []
        agg[fam].append(d["coverage_days"] or 0)

    result = [
        {"family": fam, "coverage": sum(vals) / len(vals)}
        for fam, vals in agg.items()
    ]

    return result
