//-------------------------------------------------------------
// CONFIG
//-------------------------------------------------------------
const API_BASE = "http://127.0.0.1:8000/api";

//-------------------------------------------------------------
// HELPERS
//-------------------------------------------------------------
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

  const kpiRow = document.getElementById("kpiRow");
  if (kpiRow) kpiRow.style.display = viewId === "home" ? "grid" : "none";

  const kpiPortfolioRow = document.getElementById("kpiPortfolioRow");
  if (kpiPortfolioRow) kpiPortfolioRow.style.display = viewId === "home" ? "grid" : "none";
}

//-------------------------------------------------------------
// CATALOG + FILTERS
//-------------------------------------------------------------
let catalog = [];

async function loadSelectors() {
  try {
    catalog = await apiGet("/skus");

    const skuSelect = document.getElementById("skuSelect");
    const familySelect = document.getElementById("familySelect");

    if (!skuSelect || !familySelect) return;

    const families = [...new Set(catalog.map(x => x.family).filter(Boolean))].sort();
    familySelect.innerHTML = `<option value="">Todas las familias</option>`;
    families.forEach(f => {
      familySelect.innerHTML += `<option value="${f}">${f}</option>`;
    });

    renderSkuOptions();

    // Refrescar vistas al cambiar familia
    familySelect.addEventListener("change", async () => {
      renderSkuOptions();
      await loadMainChart();
      await loadForecastChart();
      await loadAlerts();
      await loadAlertsView();
      await loadRotation();
      await loadFamilyCoverage();
      await loadPortfolioKpis();
    });

  } catch (e) {
    console.warn("No se pudo cargar catálogo", e);
  }
}

function renderSkuOptions() {
  const skuSelect = document.getElementById("skuSelect");
  const familySelect = document.getElementById("familySelect");

  const selectedFamily = familySelect.value;
  let filtered = catalog;

  if (selectedFamily) {
    filtered = catalog.filter(x => x.family === selectedFamily);
  }

  skuSelect.innerHTML = `<option value="">Seleccionar SKU</option>`;
  filtered.map(x => x.sku).sort().forEach(sku => {
    skuSelect.innerHTML += `<option value="${sku}">${sku}</option>`;
  });
}

function filterBySelectors(data) {
  const family = document.getElementById("familySelect")?.value || "";
  const sku = document.getElementById("skuSelect")?.value || "";

  let filtered = data;

  if (family) {
    const valid = new Set(catalog.filter(x => x.family === family).map(x => x.sku));
    filtered = filtered.filter(d => valid.has(d.sku));
  }

  if (sku) filtered = filtered.filter(d => d.sku === sku);

  return filtered;
}

//-------------------------------------------------------------
// KPIs TÉCNICOS
//-------------------------------------------------------------
function renderKpis(k) {
  const row = document.getElementById("kpiRow");
  if (!row) return;

  row.innerHTML = "";

  const cards = [
    { title: "SKUs analizados", value: k.total_skus, sub: "dataset demo" },
    { title: "Precisión promedio (45d)", value: fmt(100 - k.mape_val_hybrid_q1, 1) + "%", sub: "mayor es mejor" },
    { title: "Precisión de volumen", value: fmt(k.ratio_pred_vs_real_pct, 2) + "%", sub: "real vs predicho" },
    { title: "Volumen real (45d)", value: fmt(k.real_total_q1, 0), sub: "unidades" }
  ];

  cards.forEach(c => {
    row.innerHTML += `
      <div class="bg-white rounded-2xl p-4 card-hover border border-slate-100 text-center">
        <p class="text-xs text-slate-500">${c.title}</p>
        <p class="text-2xl font-semibold mt-1">${c.value}</p>
        <p class="text-xs text-slate-400 mt-1">${c.sub}</p>
      </div>`;
  });
}

//-------------------------------------------------------------
// KPIs EJECUTIVOS DEL PORTAFOLIO
//-------------------------------------------------------------
async function loadPortfolioKpis() {
  const data = await apiGet("/kpis/portfolio");
  const row = document.getElementById("kpiPortfolioRow");
  if (!row) return;

  row.innerHTML = "";

  const cards = [
    { title: "SKUs en alerta", value: data.total_alertas, sub: "quiebre + riesgo" },
    { title: "Quiebre / Riesgo", value: `${data.quiebre} / ${data.riesgo}`, sub: "situación" },
    { title: "Cobertura promedio", value: fmt(data.avg_coverage, 1) + " días", sub: "portafolio" },
    { title: "Sugerencia total rep.", value: fmt(data.total_reposicion, 0), sub: "unidades" }
  ];

  cards.forEach(c => {
    row.innerHTML += `
      <div class="bg-white rounded-2xl p-4 card-hover border text-center border-slate-100">
        <p class="text-xs text-slate-500">${c.title}</p>
        <p class="text-2xl font-semibold mt-1">${c.value}</p>
        <p class="text-xs text-slate-400 mt-1">${c.sub}</p>
      </div>`;
  });
}

//-------------------------------------------------------------
// ALERTAS HOME
//-------------------------------------------------------------
async function loadAlerts() {
  let data = await apiGet("/alerts/reorder?limit=10");
  data = filterBySelectors(data);

  const body = document.getElementById("alertsTableBody");
  body.innerHTML = "";

  if (!data.length) {
    body.innerHTML = `
      <tr><td colspan="4" class="py-3 text-center text-slate-400">
      No hay alertas para los filtros seleccionados.
      </td></tr>`;
    return;
  }

  data.forEach(a => {
    const color =
      a.status === "QUIEBRE" ? "text-red-600" :
      a.status === "RIESGO" ? "text-amber-600" :
      "text-emerald-600";

    body.innerHTML += `
      <tr class="border-b last:border-0">
        <td class="py-2 text-center">${a.sku}</td>
        <td class="py-2 text-center font-semibold ${color}">${a.status}</td>
        <td class="py-2 text-center">${fmt(a.coverage_days, 1)}</td>
      </tr>`;
  });
}

//-------------------------------------------------------------
// TOP SKUs ROTACIÓN (HOME)
//-------------------------------------------------------------
async function loadRotation() {
  const data = await apiGet("/top_skus/rotation?limit=10");

  const body = document.getElementById("rotationTableBody");
  if (!body) return;

  body.innerHTML = "";

  data.forEach(r => {
    body.innerHTML += `
      <tr class="border-b last:border-0">
        <td class="py-2 text-center">${r.sku}</td>
        <td class="py-2 text-center">${fmt(r.total_out, 0)}</td>
      </tr>`;
  });
}

//-------------------------------------------------------------
// COBERTURA POR FAMILIA (HOME)
//-------------------------------------------------------------
async function loadFamilyCoverage() {
  const data = await apiGet("/family_coverage");

  Plotly.newPlot("chartFamilyCoverage", [{
    x: data.map(d => d.family),
    y: data.map(d => d.coverage),
    type: "bar",
    marker: { color: "steelblue" }
  }], {
    title: "Cobertura promedio por familia",
    xaxis: { title: "Familia" },
    yaxis: { title: "Días de cobertura" },
    template: "simple_white"
  });
}

//-------------------------------------------------------------
// ALERTS VIEW (DETALLE)
//-------------------------------------------------------------
async function loadAlertsView() {
  let data = await apiGet("/replenishment/all?limit=50");
  data = filterBySelectors(data);

  renderAlertsKpis(data);

  // ----- GRÁFICO -----
  if (data.length) {
    Plotly.newPlot("chartAlerts", [{
      x: data.map(d => d.sku),
      y: data.map(d => d.coverage_days ?? 0),
      type: "bar",
      marker: { color: data.map(d =>
        d.status === "QUIEBRE" ? "red" :
        d.status === "RIESGO" ? "orange" : "green"
      )}
    }], {
      title: "Cobertura proyectada por SKU",
      template: "simple_white",
      xaxis: { tickangle: -45 }
    });
  }

  // ----- TABLA -----
  const tbl = document.getElementById("replenishmentTableBody");
  tbl.innerHTML = "";

  if (!data.length) {
    tbl.innerHTML = `
      <tr><td colspan="6" class="text-center py-2 text-slate-400">
      No hay sugerencias de reposición.
      </td></tr>`;
    return;
  }

  data.forEach(d => {
    const color =
      d.status === "QUIEBRE" ? "text-red-600" :
      d.status === "RIESGO" ? "text-amber-600" :
      "text-emerald-600";

    tbl.innerHTML += `
      <tr class="border-b last:border-0">
        <td class="py-2 text-center">${d.sku}</td>
        <td class="py-2 text-center">${fmt(d.stock_actual, 0)}</td>
        <td class="py-2 text-center">${fmt(d.coverage_days, 1)}</td>
        <td class="py-2 text-center font-semibold ${color}">${d.status}</td>
        <td class="py-2 text-center">${fmt(d.qty_to_order, 0)}</td>
        <td class="py-2 text-center">${d.break_date ?? "-"}</td>
      </tr>`;
  });
}

function renderAlertsKpis(data) {
  const row = document.getElementById("kpiAlertsRow");
  if (!row) return;

  if (!data.length) {
    row.innerHTML = "";
    return;
  }

  const total = data.length;
  const quiebre = data.filter(d => d.status === "QUIEBRE").length;
  const riesgo = data.filter(d => d.status === "RIESGO").length;
  const avg = data.reduce((a, d) => a + (d.coverage_days || 0), 0) / total;
  const totalReq = data.reduce((a, d) => a + (d.qty_to_order || 0), 0);

  const cards = [
    { title: "SKUs en alerta", value: total, sub: "vista filtrada" },
    { title: "Quiebre / Riesgo", value: `${quiebre} / ${riesgo}`, sub: "estado" },
    { title: "Cobertura promedio", value: fmt(avg, 1) + " días", sub: "sobre SKUs visibles" },
    { title: "Sugerencia rep.", value: fmt(totalReq, 0), sub: "unidades" }
  ];

  row.innerHTML = "";
  cards.forEach(c => {
    row.innerHTML += `
      <div class="bg-white rounded-2xl p-4 border card-hover text-center">
        <p class="text-xs text-slate-500">${c.title}</p>
        <p class="text-2xl font-semibold mt-1">${c.value}</p>
        <p class="text-xs text-slate-400 mt-1">${c.sub}</p>
      </div>`;
  });
}

//-------------------------------------------------------------
// CHART PRINCIPAL (FORECAST VS REAL)
//-------------------------------------------------------------
async function loadMainChart() {
  const sku = document.getElementById("skuSelect")?.value;

  if (!sku) {
    clearMainChart();
    return;
  }

  const series = await apiGet(`/forecast_compare?sku=${encodeURIComponent(sku)}`);
  const { sku_used, hist, pred, real } = series;

  document.getElementById("chartSubtitle").textContent = `SKU: ${sku_used}`;

  Plotly.newPlot("chartMain", [
    { x: hist.map(d => d.date), y: hist.map(d => d.y), mode: "lines", name: "Histórico" },
    { x: pred.map(d => d.date), y: pred.map(d => d.y), mode: "lines+markers", name: "Pronóstico híbrido" },
    { x: real.map(d => d.date), y: real.map(d => d.y), mode: "lines", name: "Real" }
  ], {
    title: "Histórico vs Pronóstico híbrido vs Real",
    xaxis: { title: "Fecha" },
    yaxis: { title: "Unidades vendidas" },
    template: "simple_white"
  });
}

function clearMainChart() {
  const div = document.getElementById("chartMain");
  div.innerHTML = `
    <div class="text-xs text-slate-400 mt-10 text-center">
    Selecciona un SKU para visualizar el gráfico.
    </div>`;
  document.getElementById("chartSubtitle").textContent = "";
}

//-------------------------------------------------------------
// FORECAST VIEW
//-------------------------------------------------------------
async function loadForecastChart() {
  const sku = document.getElementById("skuSelect")?.value;
  if (!sku) return clearForecastChart();

  const rows = await apiGet(`/forecast/${encodeURIComponent(sku)}`);

  Plotly.newPlot("chartForecast", [{
    x: rows.map(r => r.date),
    y: rows.map(r => r.y_hat),
    mode: "lines+markers",
    name: "Pronóstico híbrido"
  }], {
    title: `Pronóstico para ${sku}`,
    template: "simple_white"
  });
}

function clearForecastChart() {
  document.getElementById("chartForecast").innerHTML = `
    <div class="text-xs text-center text-slate-400 mt-10">
      Selecciona un SKU para ver su pronóstico detallado.
    </div>`;
}

//-------------------------------------------------------------
// ERROR VIEW (TABLA + GRAFICO)
//-------------------------------------------------------------
async function loadErrorsChart() {
  const data = await apiGet("/top_skus/error?limit=20");

  const tbody = document.getElementById("errorsTableBody");
  tbody.innerHTML = "";

  data.forEach(r => {
    tbody.innerHTML += `
      <tr class="border-b last:border-0">
        <td class="py-2 text-center">${r.sku}</td>
        <td class="py-2 text-center">${fmt(r.mape_45d, 2)}</td>
        <td class="py-2 text-center">${fmt(r.rmse_45d, 3)}</td>
      </tr>`;
  });

  Plotly.newPlot("chartErrors", [{
    x: data.map(r => r.sku),
    y: data.map(r => r.mape_45d),
    type: "bar",
    marker: { color: "steelblue" }
  }], {
    title: "MAPE por SKU (Validación 45 días)",
    xaxis: { tickangle: -45 },
    yaxis: { title: "MAPE (%)" },
    template: "simple_white"
  });
}

//-------------------------------------------------------------
// COMPARATIVO INTERANUAL
//-------------------------------------------------------------
async function loadInterannualChart() {
  const div = document.getElementById("chartInterannual");
  if (!div) return;

  const sku = document.getElementById("skuSelect")?.value;

  if (!sku) {
    div.innerHTML = `
      <div class="text-xs text-center text-slate-400 mt-10">
        Selecciona un SKU para visualizar el comparativo interanual.
      </div>`;
    return;
  }

  const data = await apiGet(`/interannual?sku=${encodeURIComponent(sku)}`);

  if (!data.length) {
    div.innerHTML = `
      <div class="text-xs text-center text-slate-400 mt-10">
        No se encontraron datos históricos para el SKU seleccionado.
      </div>`;
    return;
  }

  Plotly.newPlot("chartInterannual", [{
    x: data.map(d => d.label),
    y: data.map(d => d.total_out),
    type: "bar"
  }], {
    title: `Comparativo interanual de volumen — ${sku}`,
    xaxis: { title: "Periodo" },
    yaxis: { title: "Unidades vendidas (OUT)" },
    template: "simple_white"
  });
}

//-------------------------------------------------------------
// REFRESH ALL
//-------------------------------------------------------------
async function refreshAll() {
  const kpis = await apiGet("/kpis/global");
  renderKpis(kpis);

  await loadPortfolioKpis();
  await loadSelectors();
  await loadMainChart();
  await loadForecastChart();
  await loadAlerts();
  await loadAlertsView();
  await loadErrorsChart();
  await loadRotation();
  await loadFamilyCoverage();
  await loadInterannualChart();

}

//-------------------------------------------------------------
// INIT
//-------------------------------------------------------------
async function init() {
  document.querySelectorAll("[data-view]").forEach(b => {
    b.addEventListener("click", () => setActiveView(b.dataset.view));
  });

  document.getElementById("btnRefresh")?.addEventListener("click", refreshAll);

  document.getElementById("skuSelect")?.addEventListener("change", async () => {
    await loadMainChart();
    await loadForecastChart();
    await loadAlerts();
    await loadAlertsView();
    await loadInterannualChart();
  });

  await refreshAll();
}

document.addEventListener("DOMContentLoaded", init);
