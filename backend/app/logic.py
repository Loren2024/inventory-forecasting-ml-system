from .db import q, SCHEMA

def get_skus(limit=200):
    return q(f"""
        SELECT sku, product_name, family, category, warehouse, base_price
        FROM {SCHEMA}.products
        ORDER BY sku
        LIMIT %s
    """, [limit])

def get_forecast(sku: str, start: str, end: str):
    return q(f"""
        SELECT sku, ds::text, y_hat_min, y_hat, y_hat_max, model_type
        FROM {SCHEMA}.forecast
        WHERE sku=%s AND ds BETWEEN %s AND %s
        ORDER BY ds
    """, [sku, start, end])

def get_metrics_sku(sku: str):
    rows = q(f"""
        SELECT sku, mape_arima, rmse_arima, mape_rf, rmse_rf, mape_xgb, rmse_xgb
        FROM {SCHEMA}.model_meta
        WHERE sku=%s
    """, [sku])
    return rows[0] if rows else None

def get_eval_q1(sku: str):
    rows = q(f"""
        SELECT sku, mape_q1, rmse_q1
        FROM {SCHEMA}.model_eval
        WHERE sku=%s
    """, [sku])
    return rows[0] if rows else None

def kpis_globales():
    # consistencia global guardada en tu memoria: úsala como fallback si no existe model_eval
    rows = q(f"SELECT AVG(mape_q1) AS mape_prom, AVG(rmse_q1) AS rmse_prom FROM {SCHEMA}.model_eval")
    return rows[0]
