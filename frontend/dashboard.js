// frontend/dashboard.js

const API_BASE = "http://127.0.0.1:8000";

// Helper genérico para GET
async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} en ${path}`);
  }
  return res.json();
}

// Helper para formatear números con seguridad
function safeToFixed(value, digits = 2, suffix = "") {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return num.toFixed(digits) + suffix;
}

// ============================
// Carga de KPIs globales
// ============================
async function loadKpis() {
  try {
    const data = await apiGet("/api/kpis/global");
    console.log("KPIs recibidos:", data);

    // KPIs en tarjetas
    document.getElementById("kpi-total-skus").textContent =
      data.total_skus;

    document.getElementById("kpi-mape-train-arima").textContent =
      safeToFixed(data.mape_train_arima, 2, " %");

    document.getElementById("kpi-mape-train-rf").textContent =
      safeToFixed(data.mape_train_rf, 2, " %");

    document.getElementById("kpi-mape-train-xgb").textContent =
      safeToFixed(data.mape_train_xgb, 2, " %");

    document.getElementById("kpi-mape-val-hybrid").textContent =
      safeToFixed(data.mape_val_hybrid_q1, 2, " %");

    document.getElementById("kpi-ratio-volumen").textContent =
      safeToFixed(data.ratio_pred_vs_real_pct, 2, " %");

    document.getElementById("kpi-real-total-q1").textContent =
      safeToFixed(data.real_total_q1, 0);

    document.getElementById("kpi-pred-total-q1").textContent =
      safeToFixed(data.pred_total_q1, 2);

    // Gráfico de barras: MAPE entrenamiento por modelo
    const chartDiv = document.getElementById("chart-mape-models");
    if (chartDiv && window.Plotly) {
      const modelos = ["ARIMA", "Random Forest", "XGBoost"];
      const mapes = [
        data.mape_train_arima,
        data.mape_train_rf,
        data.mape_train_xgb
      ];

      const trace = {
        x: modelos,
        y: mapes,
        type: "bar",
        text: mapes.map(v => safeToFixed(v, 1, " %")),
        textposition: "outside"
      };

      const layout = {
        title: "Comparación de MAPE promedio por modelo (entrenamiento)",
        xaxis: { title: "Modelo" },
        yaxis: { title: "MAPE (%)" },
        margin: { t: 40, b: 60 }
      };

      Plotly.newPlot(chartDiv, [trace], layout);
    }

  } catch (err) {
    console.error("Error en loadKpis:", err);
  }
}

// ============================
// Top SKUs por error (Q1-2025)
// ============================
async function loadTopSkus() {
  try {
    const rows = await apiGet("/api/top_skus/error?limit=10");
    console.log("Top SKUs recibidos:", rows);

    // Tabla Top SKUs
    const tbody = document.getElementById("tbl-top-skus-body");
    if (tbody) {
      tbody.innerHTML = "";
      rows.forEach((r, idx) => {
        const tr = document.createElement("tr");

        const rankTd = document.createElement("td");
        rankTd.className = "px-2 py-1";
        rankTd.textContent = idx + 1;

        const skuTd = document.createElement("td");
        skuTd.className = "px-2 py-1 font-mono";
        skuTd.textContent = r.sku;

        const mapeTd = document.createElement("td");
        mapeTd.className = "px-2 py-1 text-right";
        mapeTd.textContent = safeToFixed(r.mape_q1, 2, " %");

        const rmseTd = document.createElement("td");
        rmseTd.className = "px-2 py-1 text-right";
        rmseTd.textContent = safeToFixed(r.rmse_q1, 2);

        tr.appendChild(rankTd);
        tr.appendChild(skuTd);
        tr.appendChild(mapeTd);
        tr.appendChild(rmseTd);

        tbody.appendChild(tr);
      });
    }

    // Gráfico de barras Top SKUs (MAPE)
    const chartBar = document.getElementById("chart-top-skus");
    if (chartBar && window.Plotly && rows.length > 0) {
      const skus = rows.map(r => r.sku);
      const mapes = rows.map(r => r.mape_q1);

      const trace = {
        x: skus,
        y: mapes,
        type: "bar",
        text: mapes.map(v => safeToFixed(v, 1, " %")),
        textposition: "outside"
      };

      const layout = {
        title: "Top 10 SKUs por error (MAPE Q1-2025)",
        xaxis: { title: "SKU" },
        yaxis: { title: "MAPE (%)" },
        margin: { t: 40, b: 80 }
      };

      Plotly.newPlot(chartBar, [trace], layout);
    }

    // Gráfico de dispersión MAPE vs RMSE
    const chartScat = document.getElementById("chart-scat-top-skus");
    if (chartScat && window.Plotly && rows.length > 0) {
      const skus = rows.map(r => r.sku);
      const mapes = rows.map(r => r.mape_q1);
      const rmses = rows.map(r => r.rmse_q1);

      const trace = {
        x: mapes,
        y: rmses,
        mode: "markers+text",
        type: "scatter",
        text: skus,
        textposition: "top center"
      };

      const layout = {
        title: "Relación MAPE vs. RMSE por SKU (Q1-2025)",
        xaxis: { title: "MAPE (%)" },
        yaxis: { title: "RMSE" },
        margin: { t: 40, b: 60, l: 60, r: 20 }
      };

      Plotly.newPlot(chartScat, [trace], layout);
    }

  } catch (err) {
    console.error("Error en loadTopSkus:", err);
  }
}

// ============================
// Inicialización
// ============================
document.addEventListener("DOMContentLoaded", () => {
  loadKpis();
  loadTopSkus();
});
