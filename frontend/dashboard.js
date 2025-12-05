const API_BASE = "http://127.0.0.1:8000/api";

// helpers
async function apiGet(path) {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`API ${path} -> ${r.status}`);
  return await r.json();
}

function fmt(n, d = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return Number(n).toFixed(d);
}

function setActiveView(viewId) {
  document.querySelectorAll(".view-block").forEach(v => v.classList.add("hidden"));
  document.getElementById(`view-${viewId}`)?.classList.remove("hidden");

  document.querySelectorAll("[data-view]").forEach(b => b.classList.remove("active-item"));
  document.querySelector(`[data-view="${viewId}"]`)?.classList.add("active-item");
}

// ===================== KPIS =====================
function renderKpis(k) {
  const kpiRow = document.getElementById("kpiRow");
  if (!kpiRow) return;
  kpiRow.innerHTML = "";

  const cards = [
    { title: "SKUs analizados", value: k.total_skus ?? "-", sub: "dataset demo" },
    { title: "Precisión promedio (45d)", value: fmt(100 - k.mape_val_hybrid_q1, 1) + " %", sub: "mayor es mejor" },
    { title: "Precisión de volumen", value: fmt(k.ratio_pred_vs_real_pct, 2) + " %", sub: "total real vs predicho" },
    { title: "Volumen real (45d)", value: fmt(k.real_total_q1, 0), sub: "unidades reales" }
  ];

  cards.forEach(c => {
    const div = document.createElement("div");
    div.className = "bg-white rounded-2xl p-4 card-hover border border-slate-100";
    div.innerHTML = `
      <p class="text-xs text-slate-500">${c.title}</p>
      <p class="text-2xl font-semibold mt-1">${c.value}</p>
      <p class="text-xs text-slate-400 mt-1">${c.sub}</p>
    `;
    kpiRow.appendChild(div);
  });
}

// ===================== SELECTORES =====================
async function loadSelectors() {
  try {
    const cat = await apiGet("/skus");
    const skuSelect = document.getElementById("skuSelect");
    const familySelect = document.getElementById("familySelect");
    if (!skuSelect || !familySelect) return;

    // familias
    const families = [...new Set(cat.map(x => x.family).filter(Boolean))].sort();
    familySelect.innerHTML = `<option value="">Todas las familias</option>`;
    families.forEach(f => {
      const opt = document.createElement("option");
      opt.value = f; opt.textContent = f;
      familySelect.appendChild(opt);
    });

    // skus
    const skus = cat.map(x => x.sku).sort();
    skuSelect.innerHTML = `<option value="">Seleccionar SKU</option>`;
    skus.forEach(s => {
      const opt = document.createElement("option");
      opt.value = s; opt.textContent = s;
      skuSelect.appendChild(opt);
    });

  } catch (e) {
    console.warn("No se pudo cargar catálogo", e);
  }
}

// ===================== TOP SKUS ERROR =====================
async function loadTopSkus() {
  const data = await apiGet("/top_skus/error?limit=10");
  const body = document.getElementById("topSkusTableBody");
  if (!body) return;
  body.innerHTML = "";

  data.forEach(r => {
    const tr = document.createElement("tr");
    tr.className = "border-b last:border-0";
    tr.innerHTML = `
      <td class="py-2">${r.sku}</td>
      <td class="py-2 text-right">${fmt(r.mape_45d, 2)}%</td>
      <td class="py-2 text-right">${fmt(r.rmse_45d, 3)}</td>
    `;
    body.appendChild(tr);
  });
}

// ===================== ALERTAS (TABLA HOME) =====================
async function loadAlerts() {
  let data = [];
  try {
    data = await apiGet("/alerts/reorder?limit=10");
  } catch {
    data = [];
  }

  const body = document.getElementById("alertsTableBody");
  if (!body) return;
  body.innerHTML = "";

  if (!data.length) {
    body.innerHTML = `
      <tr><td colspan="4" class="py-3 text-slate-400 text-center">
        No hay alertas registradas en esta demo.
      </td></tr>`;
    return;
  }

  data.forEach(a => {
    const stateColor =
      a.status === "QUIEBRE" ? "text-red-600" :
        a.status === "RIESGO" ? "text-amber-600" :
          "text-emerald-600";

    const tr = document.createElement("tr");
    tr.className = "border-b last:border-0";
    tr.innerHTML = `
      <td class="py-2">${a.sku}</td>
      <td class="py-2 font-semibold ${stateColor}">${a.status}</td>
      <td class="py-2 text-right">${fmt(a.coverage_days, 1)}</td>
    `;
    body.appendChild(tr);
  });
}

// ===================== ALERTAS VIEW (GRAFICO + TABLA) =====================
async function loadAlertsView() {
  let data = [];
  try {
    data = await apiGet("/replenishment/all?limit=50");
  } catch (e) {
    console.warn("No se pudo cargar replenishment", e);
    return;
  }

  // -------- GRAFICO (solo si existe el div) --------
  const chartDiv = document.getElementById("chartAlerts");
  if (chartDiv) {
    const x = data.map(d => d.sku);
    const y = data.map(d => d.coverage_days ?? 0);
    const colors = data.map(d =>
      d.status === "QUIEBRE" ? "red" :
        d.status === "RIESGO" ? "orange" : "green"
    );

    Plotly.newPlot("chartAlerts", [{
      x, y, type: "bar", marker: { color: colors }, name: "Cobertura (días)"
    }], {
      title: "Cobertura proyectada por SKU",
      xaxis: { title: "SKU", tickangle: -45 },
      yaxis: { title: "Días de cobertura" },
      margin: { t: 40, r: 10, l: 50, b: 100 },
      template: "simple_white"
    }, { responsive: true });
  }

  // -------- TABLA --------
  const tbl = document.getElementById("replenishmentTableBody");
  if (!tbl) return;

  tbl.innerHTML = "";
  data.forEach(d => {
    const stateColor =
      d.status === "QUIEBRE" ? "text-red-600" :
        d.status === "RIESGO" ? "text-amber-600" :
          "text-emerald-600";

    const tr = document.createElement("tr");
    tr.className = "border-b last:border-0";
    tr.innerHTML = `
      <td class="py-2">${d.sku}</td>
      <td class="py-2 text-right">${fmt(d.stock_actual, 0)}</td>
      <td class="py-2 text-right">${fmt(d.coverage_days, 1)}</td>
      <td class="py-2 font-semibold ${stateColor}">${d.status}</td>
      <td class="py-2 text-right">${fmt(d.qty_to_order, 0)}</td>
      <td class="py-2">${d.break_date ?? "-"}</td>
    `;
    tbl.appendChild(tr);
  });
}


// ===================== CHART PRINCIPAL =====================
async function loadMainChart(sku = null) {
  const targetSku = sku || document.getElementById("skuSelect")?.value;
  if (!targetSku) return;

  series = await apiGet(`/forecast_compare?sku=${encodeURIComponent(targetSku)}`);

  const { sku_used, hist, pred, real } = series;

  document.getElementById("chartSubtitle").textContent = `SKU: ${sku_used}`;

  const traces = [
    { x: hist.map(d => d.date), y: hist.map(d => d.y), mode: "lines", name: "Histórico" },
    { x: pred.map(d => d.date), y: pred.map(d => d.y), mode: "lines+markers", name: "Pronóstico híbrido" },
    { x: real.map(d => d.date), y: real.map(d => d.y), mode: "lines", name: "Real" }
  ];

  Plotly.newPlot("chartMain", traces, {
    title: "Histórico vs Pronóstico híbrido vs Real",
    xaxis: { title: "Fecha" },
    yaxis: { title: "Unidades vendidas" },
    template: "simple_white"
  }, { responsive: true });
}

// ===================== FORECAST VIEW =====================
async function loadForecastChart() {
  const sku = document.getElementById("skuSelect")?.value;
  if (!sku) return;
  const rows = await apiGet(`/forecast/${encodeURIComponent(sku)}`);

  Plotly.newPlot("chartForecast", [{
    x: rows.map(d => d.date),
    y: rows.map(d => d.y_hat),
    mode: "lines+markers",
    name: "Pronóstico híbrido"
  }], {
    title: `Pronóstico híbrido — ${sku}`,
    xaxis: { title: "Fecha" },
    yaxis: { title: "Unidades" },
    template: "simple_white"
  }, { responsive: true });
}

// ===================== ERRORS VIEW =====================
async function loadErrorsChart() {
  const top = await apiGet("/top_skus/error?limit=20");

  Plotly.newPlot("chartErrors", [{
    x: top.map(d => d.sku),
    y: top.map(d => d.mape_45d),
    type: "bar",
    name: "MAPE 45d"
  }], {
    title: "Errores por SKU (MAPE 45 días)",
    xaxis: { title: "SKU", tickangle: -45 },
    yaxis: { title: "MAPE (%)" },
    template: "simple_white",
    margin: { t: 40, r: 10, l: 50, b: 100 }
  }, { responsive: true });
}

// ===================== REFRESH =====================
async function refreshAll() {
  const kpis = await apiGet("/kpis/global");
  renderKpis(kpis);

  await loadSelectors();
  await loadTopSkus();
  await loadAlerts();
  await loadMainChart();
  await loadForecastChart();
  await loadErrorsChart();
  await loadAlertsView();
}

async function init() {
  document.querySelectorAll("[data-view]").forEach(b => {
    b.addEventListener("click", () => setActiveView(b.dataset.view));
  });

  document.getElementById("btnRefresh")?.addEventListener("click", refreshAll);

  document.getElementById("skuSelect")?.addEventListener("change", async () => {
    await loadMainChart();
    await loadForecastChart();
  });

  await refreshAll();
}

document.addEventListener("DOMContentLoaded", init);
