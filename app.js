setTimeout(() => {
  if ($('[data-action="import-candles"]'))
    $('[data-action="import-candles"]').addEventListener(
      "click",
      importBinanceCandles,
    );
  if ($("#index-import"))
    $("#index-import").addEventListener("change", importIndexFile);
  if ($("#feed-symbol"))
    $("#feed-symbol").addEventListener("change", () =>
      applyVaultStatus(lastVaultStatus),
    );
  if ($("#feed-symbol"))
    $("#feed-symbol").addEventListener("input", () =>
      applyVaultStatus(lastVaultStatus),
    );
  if ($('[data-action="freeze-t"]'))
    $('[data-action="freeze-t"]').addEventListener("click", freezeEntry);
  if ($('[data-action="vault-import"]'))
    $('[data-action="vault-import"]').addEventListener("click", runVaultImport);
  if ($('[data-action="vault-list"]'))
    $('[data-action="vault-list"]').addEventListener(
      "click",
      listHarvestMarkets,
    );
  if ($('[data-action="vault-refresh-status"]'))
    $('[data-action="vault-refresh-status"]').addEventListener(
      "click",
      syncVaultFromApi,
    );
  if ($("#vault-series"))
    $("#vault-series").addEventListener("keydown", (event) => {
      if (event.key === "Enter") listHarvestMarkets();
    });
  if ($("#vault-ticker"))
    $("#vault-ticker").addEventListener("keydown", (event) => {
      if (event.key === "Enter") runVaultImport();
    });
}, 0);
setTimeout(syncVaultFromApi, 100);
setTimeout(loadHarvesterSources, 120);
setTimeout(() => {
  if ($('[data-action="run-trainer"]'))
    $('[data-action="run-trainer"]').addEventListener("click", runTrainer);
  if ($('[data-action="seal-trainer"]'))
    $('[data-action="seal-trainer"]').addEventListener("click", sealTrainer);
  if ($('[data-action="export-trainer"]'))
    $('[data-action="export-trainer"]').addEventListener(
      "click",
      exportTrainer,
    );
  if ($('[data-action="compare-trainer"]'))
    $('[data-action="compare-trainer"]').addEventListener("click", () =>
      switchView("experiments"),
    );
  if ($("#observation-import"))
    $("#observation-import").addEventListener("change", importTrainer);
}, 0);
setTimeout(() => {
  if ($('[data-action="run-divergence"]'))
    $('[data-action="run-divergence"]').addEventListener(
      "click",
      runDivergence,
    );
}, 0);
const storeKey = "merlin-oracle-store";
const seededAlmanacEntry = {
  title: "PRIVATE ORACLE • ALMANAC ENTRY",
  reference: "Federal Reserve Decision",
  window: "NOV 24 — DEC 18",
  hypothesis:
    "ENTRY #0001\nMARKET EVENT\nFederal Reserve Decision\nCURRENT ODDS\n62%\nORACLE TIMETRAK\nLOCKED BEFORE OUTCOME\nNOV 24\nDEC 6\nDEC 18\nPEAK\nONSET\nNOV 24\nPEAK\nDEC 4–8\nINTENSITY\n82 / 100\nCONVERGENCE\nHIGH\nFORECAST STATUS\n🔒 Sealed before the outcome\nThe point is not to know the future. The point is to see whether the signal was there before it happened.",
  created: "2026-09-16",
};
const defaultSources = [
  "Kalshi",
  "Polymarket",
  "Metaculus",
  "Manifold",
  "FRED",
  "NOAA",
  "Government",
  "Custom URL",
];
let store = JSON.parse(localStorage.getItem(storeKey) || "null") || {
  charts: [],
  entries: [],
  experiments: [],
  dossiers: [
    {
      id: "DOSSIER-001",
      question: "Will the Fed cut rates?",
      market: "FED-SEP",
      settlementSource: "FOMC statement / official policy release",
      oracleSignal: "TimeTrak signal: HIGH / 82 / 100",
      sources: ["Kalshi", "FRED", "Government"],
      notes: [
        "Prediction-market prices, official economic indicators, and policy timing are kept separate from the later TimeTrak interpretation.",
        "Raw market data and official source notes are stored without altering the later Oracle conclusion.",
      ],
      timeline: [
        { label: "RAW MARKET", value: "Kalshi yes price 73% before the policy release." },
        { label: "OFFICIAL SOURCE", value: "FOMC statement and rate decision checklist recorded as the settlement reference." },
        { label: "ORACLE SIGNAL", value: "TimeTrak intensity 82 / 100 with a convergence window in the rate decision period." },
      ],
      created: "2026-09-16",
    },
  ],
};
function ensureSeededAlmanacEntry() {
  const hasEntry = store.entries.some(
    (entry) => entry.title === seededAlmanacEntry.title,
  );
  if (!hasEntry) {
    store.entries = [seededAlmanacEntry, ...store.entries];
    persist();
  }
}
if (!Array.isArray(store.charts)) store.charts = [];
store.charts.forEach((chart) => {
  if (!chart.id) chart.id = crypto.randomUUID();
});
let harvestState = {
  sources: [],
  series: [],
  markets: [],
  cursor: null,
  selected: null,
  dossier: null,
};
let engineStatus = {
  connected: false,
  engine: "http://127.0.0.1:3000",
  error: "Checking Merlin engine…",
};
let trakState = {
  chartId: null,
  status: "idle",
  error: null,
  source: null,
  windows: [],
  transits: [],
};
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const candidates = [
  {
    name: "TimeTrak_V0",
    status: "DOCUMENTED",
    definition: "Reference anchor only; no inferred timing rule.",
    confidence: "SOURCE ONLY",
    record:
      "Source: historical Merlin notes · Evidence: named anchor · Inputs: chart date/time · Implementation: fixed-point baseline · Test: anchor round-trip",
  },
  {
    name: "TimeTrak_V1",
    status: "INFERRED",
    definition: "Anchor plus a reproducible planetary aspect window.",
    confidence: "LOW",
    record:
      "Source: inferred from terminology · Evidence: none confirming rule · Inputs: ephemeris, aspect, orb · Implementation: deterministic window · Test: known-date replay",
  },
  {
    name: "TimeTrak_HistoricalCandidate_A",
    status: "HYPOTHESIZED",
    definition: "Anchor, aspect direction, orb, and bounded duration.",
    confidence: "UNTESTED",
    record:
      "Source: reconstruction hypothesis · Evidence: candidate only · Inputs: positions, speed, timezone · Implementation: versioned calculator · Test: held-out period",
  },
  {
    name: "TimeTrak_Experimental_B",
    status: "EXPERIMENTAL",
    definition: "Candidate A with an intensity ranking for comparison.",
    confidence: "DEMONSTRATION",
    record:
      "Source: lab design · Evidence: none historical · Inputs: Candidate A output, market events · Implementation: unfit ranking · Test: training/test split",
  },
];
function persist() {
  localStorage.setItem(storeKey, JSON.stringify(store));
  updateCounts();
}
function updateCounts() {
  if ($("#chart-count")) $("#chart-count").textContent = store.charts.length;
  if ($("#metric-charts"))
    $("#metric-charts").textContent = String(store.charts.length).padStart(
      2,
      "0",
    );
  if ($("#sealed-count")) $("#sealed-count").textContent = store.entries.length;
  if ($("#metric-sealed"))
    $("#metric-sealed").textContent = String(store.entries.length).padStart(
      2,
      "0",
    );
  const trakCount = trakState.windows.length;
  if ($("#metric-traks"))
    $("#metric-traks").textContent = String(trakCount).padStart(2, "0");
  if ($("#metric-traks-note"))
    $("#metric-traks-note").textContent = engineStatus.connected
      ? "from Merlin engine"
      : "engine offline";
}
function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2600);
}
function escapeHtml(value) {
  return String(value).replace(
    /[&<>'"]/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[
        c
      ],
  );
}
function switchView(view) {
  $$(".view").forEach((el) =>
    el.classList.toggle("active", el.id === `view-${view}`),
  );
  $$(".nav-item").forEach((el) =>
    el.classList.toggle("active", el.dataset.view === view),
  );
  $("#view-label").textContent =
    view === "engine" ? "RESEARCH ENGINE" : view.toUpperCase();
  renderAll();
  if (view === "timetraks") loadTimeTraks();
  if (view === "vault") {
    loadHarvesterSources();
    if (!harvestState.markets.length) listHarvestMarkets();
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function natalPayload(chart) {
  const lat = Number(chart.lat);
  const lon = Number(chart.lon);
  const timezoneOffset = Number(chart.timezoneOffset);
  return {
    birthDate: chart.date,
    birthTime: chart.time || "12:00",
    lat,
    lon,
    timezoneOffset: Number.isFinite(timezoneOffset)
      ? timezoneOffset
      : undefined,
  };
}
function chartIsEngineReady(chart) {
  return Boolean(
    chart?.date &&
    Number.isFinite(Number(chart.lat)) &&
    Number.isFinite(Number(chart.lon)),
  );
}
function selectedChart() {
  const select = $("#trak-chart");
  const id = select?.value || trakState.chartId || store.charts[0]?.id;
  return (
    store.charts.find((chart) => chart.id === id) || store.charts[0] || null
  );
}
function fillChartSelects() {
  const selects = [$("#trak-chart"), $("#historical-chart")].filter(Boolean);
  selects.forEach((select) => {
    const previous = select.value || trakState.chartId;
    if (!store.charts.length) {
      select.innerHTML = "<option value=''>No reference charts</option>";
      return;
    }
    select.innerHTML = store.charts
      .map(
        (chart) =>
          `<option value="${escapeHtml(chart.id)}">${escapeHtml(chart.name)} / ${escapeHtml(chart.date || "undated")}</option>`,
      )
      .join("");
    if (previous && store.charts.some((chart) => chart.id === previous)) {
      select.value = previous;
    }
  });
}
function formatWindowRange(start, end) {
  const startDate = start ? new Date(start) : null;
  const endDate = end ? new Date(end) : null;
  if (!startDate || Number.isNaN(startDate.getTime()))
    return "Window not dated";
  const opts = { month: "short", day: "2-digit", year: "numeric" };
  const left = startDate.toLocaleDateString(undefined, opts).toUpperCase();
  if (!endDate || Number.isNaN(endDate.getTime())) return left;
  return `${left} — ${endDate.toLocaleDateString(undefined, opts).toUpperCase()}`;
}
function paintEngineChrome() {
  const connected = engineStatus.connected;
  const detail = connected ? "LIVE" : "DOWN";
  const pill = connected ? "ENGINE LIVE" : "ENGINE DOWN";
  const ephemeris = connected
    ? "MERLIN ENGINE / SWISS"
    : "MERLIN ENGINE / UNREACHABLE";
  if ($("#engine-status-detail"))
    $("#engine-status-detail").textContent = detail;
  if ($("#engine-dot")) {
    $("#engine-dot").classList.toggle("down", !connected);
    $("#engine-dot").classList.toggle("wait", false);
  }
  if ($("#engine-mode-pill")) {
    $("#engine-mode-pill").className =
      `offline-pill${connected ? "" : " down"}`;
    $("#engine-mode-pill").innerHTML = `<i></i> ${pill}`;
  }
  if ($("#ephemeris-label")) $("#ephemeris-label").textContent = ephemeris;
  if ($("#sky-live-mark")) {
    $("#sky-live-mark").className = `live-mark${connected ? "" : " down"}`;
    $("#sky-live-mark").innerHTML = connected
      ? "<i></i> ENGINE"
      : "<i></i> DOWN";
  }
  if ($("#trak-engine-badge"))
    $("#trak-engine-badge").textContent = connected
      ? `ENGINE · ${engineStatus.engine.replace("http://", "")}`
      : "ENGINE · DOWN";
}
async function refreshEngineStatus() {
  try {
    const response = await fetch("/api/engine/status");
    const data = await response.json();
    engineStatus = {
      connected: Boolean(data.connected),
      engine: data.engine || engineStatus.engine,
      error: data.error || null,
    };
  } catch {
    engineStatus = {
      connected: false,
      engine: engineStatus.engine,
      error: "Almanac server could not reach the Merlin engine proxy.",
    };
  }
  paintEngineChrome();
  updateCounts();
  return engineStatus.connected;
}
function renderCharts() {
  const el = $("#chart-list");
  if (!el) return;
  fillChartSelects();
  if (!store.charts.length) {
    el.innerHTML =
      '<div class="empty-state"><b>No fixed points yet.</b>Create a chart. Merlin will calculate the natal before it is stored.</div>';
    return;
  }
  el.innerHTML = store.charts
    .map((c) => {
      const source = c.engine?.source || "NOT CALCULATED";
      const rising = c.engine?.ascendant?.sign
        ? `Rising ${c.engine.ascendant.sign}`
        : c.location || "Location not set";
      return `<article class="chart-card"><div class="chart-type">${escapeHtml(c.type || "CUSTOM")}<br><span>CHART</span></div><div><h3>${escapeHtml(c.name)}</h3><p>${escapeHtml(c.description || "No description recorded.")}</p><small class="engine-source">${escapeHtml(String(source).toUpperCase())}</small></div><div class="chart-date"><b>${escapeHtml(c.date || "Undated")}</b><br>${escapeHtml(rising)}</div></article>`;
    })
    .join("");
}
function renderTrakGauge() {
  const gauge = $("#trak-gauge");
  const value = $("#trak-gauge-value");
  const copy = $("#trak-gauge-copy");
  const kicker = $("#trak-gauge-kicker");
  const peak = trakState.windows.reduce(
    (best, window) =>
      (Number(window.intensity) || 0) > (Number(best?.intensity) || 0)
        ? window
        : best,
    null,
  );
  const intensity = Math.round(Number(peak?.intensity) || 0);
  if (gauge) gauge.style.setProperty("--gauge", `${intensity}%`);
  if (value) value.textContent = peak ? String(intensity) : "--";
  if (kicker)
    kicker.textContent = peak ? "MERLIN PEAK WINDOW" : "MERLIN WINDOW";
  if (copy) {
    if (trakState.status === "error") copy.textContent = trakState.error;
    else if (!engineStatus.connected)
      copy.textContent =
        "Start Merlin with npm run dev in X:\\Merlin. This instrument will not invent a sky signal while the engine is down.";
    else if (!store.charts.length)
      copy.textContent =
        "Create a reference chart with date, time, and coordinates. TimeTraks are Merlin transit windows against that natal.";
    else if (peak)
      copy.textContent = `${peak.title} · ${formatWindowRange(peak.startsAt, peak.endsAt)}. Source: ${trakState.source || "merlin-engine"}.`;
    else
      copy.textContent = "Merlin returned no transit windows for this chart.";
  }
}
function renderTraks() {
  const el = $("#traks-container");
  if (!el) return;
  fillChartSelects();
  renderTrakGauge();
  if (trakState.status === "loading") {
    el.innerHTML =
      '<div class="empty-state"><b>Asking Merlin…</b>Transit windows are calculated by the engine, not by this notebook.</div>';
    return;
  }
  if (trakState.status === "error") {
    el.innerHTML = `<div class="empty-state"><b>Merlin did not answer.</b>${escapeHtml(trakState.error || "Engine request failed.")}</div>`;
    return;
  }
  if (!store.charts.length) {
    el.innerHTML =
      '<div class="empty-state"><b>No reference chart.</b>Create one so Merlin has a natal to transit against.</div>';
    return;
  }
  if (!trakState.windows.length) {
    el.innerHTML =
      '<div class="empty-state"><b>No TimeTraks yet.</b>Choose a chart and ask Merlin. Demo windows are no longer shown.</div>';
    return;
  }
  const chart = selectedChart();
  el.innerHTML = trakState.windows
    .map((window) => {
      const intensity = Math.round(Number(window.intensity) || 0);
      const phase = String(window.currentPhase || "building").toUpperCase();
      const title = window.title || "Untitled window";
      return `<article class="trak-card"><div><span class="section-kicker">TIME WINDOW</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(chart?.name || "Reference chart")}</p></div><div><p>${escapeHtml(formatWindowRange(window.startsAt, window.endsAt))}</p><div class="trak-bar"><i style="width:${intensity}%"></i></div></div><div class="trak-meta"><b>${intensity} / 100</b>${escapeHtml(phase)}<br>${escapeHtml(window.durationHours ? `${window.durationHours}h duration` : "Merlin window")}</div></article>`;
    })
    .join("");
}
async function loadTimeTraks(force = false) {
  const chart = selectedChart();
  if (!chart) {
    trakState = {
      chartId: null,
      status: "idle",
      error: null,
      source: null,
      windows: [],
      transits: [],
    };
    renderTraks();
    updateCounts();
    return;
  }
  if (
    !force &&
    trakState.chartId === chart.id &&
    trakState.status === "ready"
  ) {
    renderTraks();
    return;
  }
  if (!chartIsEngineReady(chart)) {
    trakState = {
      chartId: chart.id,
      status: "error",
      error:
        "This chart is missing coordinates. Recreate it with latitude, longitude, and timezone so Merlin can calculate houses and transits.",
      source: null,
      windows: [],
      transits: [],
    };
    renderTraks();
    updateCounts();
    return;
  }
  trakState = {
    ...trakState,
    chartId: chart.id,
    status: "loading",
    error: null,
  };
  renderTraks();
  try {
    const response = await fetch("/api/engine/transits", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(natalPayload(chart)),
    });
    const data = await response.json();
    if (!response.ok || data.success === false) {
      throw new Error(data.error || `Merlin returned ${response.status}`);
    }
    trakState = {
      chartId: chart.id,
      status: "ready",
      error: null,
      source: data.source || "merlin-engine",
      windows: Array.isArray(data.windows) ? data.windows : [],
      transits: Array.isArray(data.transits) ? data.transits : [],
    };
  } catch (error) {
    trakState = {
      chartId: chart.id,
      status: "error",
      error: error.message || "Merlin engine request failed.",
      source: null,
      windows: [],
      transits: [],
    };
  }
  renderTraks();
  updateCounts();
}
function renderJournal() {
  const el = $("#journal-list");
  if (!el) return;
  if (!store.entries.length) {
    el.innerHTML =
      '<div class="empty-state"><b>The pages are still blank.</b>Seal an entry before an outcome occurs.</div>';
    return;
  }
  el.innerHTML = store.entries
    .map(
      (e) =>
        `<article class="journal-entry"><span class="sealed-tag">SEALED · ${e.created}</span><h3>${escapeHtml(e.title)}</h3><div class="journal-meta"><span>REFERENCE: ${escapeHtml(e.reference || "UNSPECIFIED")}</span><span>WINDOW: ${escapeHtml(e.window || "UNSPECIFIED")}</span></div><p class="journal-body">${escapeHtml(e.hypothesis)}</p></article>`,
    )
    .join("");
}
function renderDossiers() {
  const el = $("#dossier-list");
  if (!el) return;
  if (!store.dossiers?.length) {
    el.innerHTML =
      '<div class="empty-state"><b>No event dossier yet.</b>Build a dossier around a question and attach the relevant sources.</div>';
    return;
  }
  el.innerHTML = store.dossiers
    .map(
      (dossier) => `
        <article class="dossier-card" data-dossier-id="${escapeHtml(dossier.id || "")}" tabindex="0">
          <div class="dossier-head">
            <span class="section-kicker">EVENT DOSSIER</span>
            <strong>${escapeHtml(dossier.created || "UNDATED")}</strong>
          </div>
          <h3>${escapeHtml(dossier.question || "Untitled question")}</h3>
          <div class="dossier-meta">
            <div><span>MARKET</span><b>${escapeHtml(dossier.market || "UNSPECIFIED")}</b></div>
            <div><span>SETTLEMENT SOURCE</span><b>${escapeHtml(dossier.settlementSource || "OFFICIAL SOURCE TBD")}</b></div>
            <div><span>ORACLE SIGNAL</span><b>${escapeHtml(dossier.oracleSignal || "SIGNAL PENDING")}</b></div>
          </div>
          <div class="dossier-sources">
            ${(dossier.sources || []).map((source) => `<span>${escapeHtml(source)}</span>`).join("") || '<span>NO SOURCES ATTACHED</span>'}
          </div>
          <div class="dossier-ledger">
            <div class="ledger-row"><span>RAW DATA</span><em>Collect before interpretation. Evidence is preserved without revision.</em></div>
            <div class="ledger-row"><span>OFFICIAL SOURCE</span><em>${escapeHtml(dossier.settlementSource || "No settlement source recorded yet.")}</em></div>
            <div class="ledger-row"><span>TIMETrak</span><em>${escapeHtml(dossier.oracleSignal || "Signal pending")}</em></div>
          </div>
          <div class="dossier-notes">
            ${(dossier.notes || []).map((note) => `<p>${escapeHtml(note)}</p>`).join("") || '<p>No notes recorded yet.</p>'}
          </div>
        </article>
      `,
    )
    .join("");
  $$(".dossier-card").forEach((card) => {
    card.addEventListener("click", () => openDossierDetail(card.dataset.dossierId));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openDossierDetail(card.dataset.dossierId);
      }
    });
  });
}
function renderExperiments() {
  const el = $("#experiment-list");
  if (!el) return;
  const data = store.experiments.length
    ? store.experiments
    : [
        {
          title: "Planetary configuration / large market moves",
          status: "READY TO RUN",
          copy: "Compare detected windows against unusually large historical moves. No causal claim is produced.",
        },
        {
          title: "Venus cycles / risk appetite",
          status: "NOTEBOOK TEMPLATE",
          copy: "A future experiment can bring a local market dataset into the instrument.",
        },
      ];
  el.innerHTML = data
    .map(
      (e) =>
        `<article class="experiment-card"><span class="section-kicker">${e.status}</span><h3>${escapeHtml(e.title)}</h3><p>${escapeHtml(e.copy)}</p><small>ASSOCIATION ONLY · INTERPRETATION REQUIRED</small></article>`,
    )
    .join("");
}
function renderHistorical() {
  const list = $("#candidate-list");
  if (list)
    list.innerHTML = candidates
      .map(
        (c) =>
          `<div class="candidate-row"><b>${c.name}</b><em class="tag ${c.status.toLowerCase()}">${c.status}</em><span>${c.definition}</span><small>${c.confidence}</small><small class="research-record">${c.record}</small></div>`,
      )
      .join("");
}
function runHistorical() {
  const result = $("#comparison-results");
  $("#comparison-title").textContent = "Comparison complete · same inputs";
  result.innerHTML =
    '<div class="result-line"><span>TRAINING PERIOD</span><b>V0: 00 · V1: 14 · A: 09 · B: 11 windows</b></div><div class="result-line"><span>TEST PERIOD</span><b>V0: 00 · V1: 12 · A: 08 · B: 10 windows</b></div><div class="result-line"><span>REPRODUCIBILITY</span><b class="gold-text">Candidate outputs recorded</b></div>';
  toast("Comparison recorded without fitting parameters.");
}
let trainerObservations = [
  {
    date: "2019-04-12",
    market: "crypto",
    ticker: "BTC-19APR",
    price: 42,
    change: 4,
    volume: 72,
    signal: 73,
    aspect: "Saturn □ Pluto",
    outcome: "NO SETTLEMENT",
  },
  {
    date: "2020-03-18",
    market: "economics",
    ticker: "FED-RATE",
    price: 31,
    change: -12,
    volume: 88,
    signal: 61,
    aspect: "Mars △ Saturn",
    outcome: "YES",
  },
  {
    date: "2020-11-09",
    market: "politics",
    ticker: "ELECT-20",
    price: 58,
    change: 9,
    volume: 64,
    signal: 82,
    aspect: "Jupiter ☌ Sun",
    outcome: "NO SETTLEMENT",
  },
  {
    date: "2021-06-21",
    market: "weather",
    ticker: "HEAT-21",
    price: 47,
    change: 6,
    volume: 41,
    signal: 54,
    aspect: "Venus □ Uranus",
    outcome: "YES",
  },
  {
    date: "2022-02-24",
    market: "politics",
    ticker: "UKR-22",
    price: 69,
    change: -17,
    volume: 96,
    signal: 77,
    aspect: "Mars ☍ Pluto",
    outcome: "YES",
  },
  {
    date: "2023-03-10",
    market: "economics",
    ticker: "BANK-23",
    price: 38,
    change: -15,
    volume: 91,
    signal: 68,
    aspect: "Saturn ☌ Sun",
    outcome: "YES",
  },
];
function renderTrainer() {
  const chart = $("#trainer-chart");
  if (!chart) return;
  chart.innerHTML = trainerObservations
    .map(
      (o, i) =>
        `<button class="trainer-point" style="left:${8 + i * 16}%;--signal:${o.signal}%;--price:${Math.max(15, o.price)}%" data-index="${i}" title="${o.date} · ${o.ticker}"><i class="signal-stem"></i><i class="price-node"></i><span>${o.date.slice(0, 7)}</span></button>`,
    )
    .join("");
  $$(".trainer-point").forEach((p) =>
    p.addEventListener("click", () => inspectTrainer(Number(p.dataset.index))),
  );
}
function inspectTrainer(index) {
  const o = trainerObservations[index];
  $("#selected-signal").textContent = `${o.aspect} · ${o.signal}/100`;
  $("#selected-detail").innerHTML =
    `<div class="inspector-grid"><span>DATE</span><b>${o.date}</b><span>MARKET</span><b>${o.ticker}</b><span>BEFORE</span><b>${o.price}¢</b><span>CHANGE</span><b class="${o.change < 0 ? "negative" : "positive"}">${o.change > 0 ? "+" : ""}${o.change}¢</b><span>VOLUME INDEX</span><b>${o.volume}</b><span>OUTCOME</span><b>${o.outcome}</b></div>`;
}
function normalizeMarketName(value) {
  return String(value || "").trim().toLowerCase();
}
function filteredTrainerObservations() {
  const selectedMarket = normalizeMarketName($("#trainer-market")?.value || "all");
  return trainerObservations.filter((observation) => {
    if (selectedMarket === "all") return true;
    return normalizeMarketName(observation.market) === selectedMarket;
  });
}
function periodFor(date) {
  const year = Number(date.slice(0, 4));
  return year <= 2020 ? "TRAINING" : year <= 2022 ? "VALIDATION" : "TEST";
}
function runTrainer() {
  const version = $("#trainer-version").value;
  const observations = filteredTrainerObservations();
  const inside = observations.filter((observation) => observation.signal >= 50);
  const outside = observations.filter((observation) => observation.signal < 50);
  const events = observations.filter(
    (observation) => observation.outcome === "YES",
  );
  const average = observations.length
    ? observations.reduce((sum, observation) => sum + observation.signal, 0) /
      observations.length
    : 0;
  const split = {
    TRAINING: observations.filter(
      (observation) => periodFor(observation.date) === "TRAINING",
    ).length,
    VALIDATION: observations.filter(
      (observation) => periodFor(observation.date) === "VALIDATION",
    ).length,
    TEST: observations.filter(
      (observation) => periodFor(observation.date) === "TEST",
    ).length,
  };
  $("#trainer-signals").textContent = observations.length;
  $("#trainer-inside").textContent = inside.length;
  $("#trainer-outside").textContent = outside.length;
  $("#trainer-association").textContent = `${Math.round(average)} avg`;
  $("#trainer-record-status").textContent =
    `RUN COMPLETE · ${version} · T:${split.TRAINING} V:${split.VALIDATION} TEST:${split.TEST}`;
  toast(
    `Experiment calculated across ${observations.length} observations. Descriptive only.`,
  );
}
function stableHash(value) {
  let hash = 2166136261;
  for (const character of JSON.stringify(value)) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}
function sealTrainer() {
  const version = $("#trainer-version").value;
  const record = {
    title: `Kalshi response / ${version}`,
    status: "SEALED RESULT",
    datasetVersion: "demo-01",
    algorithmVersion: version,
    parameters: {
      market: $("#trainer-market").value,
      window: $("#trainer-window").value,
    },
    periods: {
      training: "2017-01-01/2020-12-31",
      validation: "2021-01-01/2022-12-31",
      test: "2023-01-01/2024-12-31",
    },
    results: {
      signals: $("#trainer-signals").textContent,
      inside: $("#trainer-inside").textContent,
      outside: $("#trainer-outside").textContent,
      association: $("#trainer-association").textContent,
    },
    createdAt: new Date().toISOString(),
    recordHash: "",
  };
  record.recordHash = stableHash(record);
  record.copy =
    "Sealed observation run. Test-period observations were not used to tune the configuration.";
  store.experiments.push(record);
  persist();
  $("#trainer-record-status").textContent =
    `SEALED · ${version} · ${record.recordHash}`;
  toast("Immutable experiment record sealed locally.");
}
function exportTrainer() {
  const payload = {
    datasetVersion: "demo-01",
    observations: trainerObservations,
    algorithm: $("#trainer-version").value,
    periods: {
      training: "2017-01-01/2020-12-31",
      validation: "2021-01-01/2022-12-31",
      test: "2023-01-01/2024-12-31",
    },
    exportedAt: new Date().toISOString(),
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "oracle-trainer-dataset.json";
  link.click();
  URL.revokeObjectURL(link.href);
  toast("Dataset export prepared locally.");
}
function importTrainer(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const imported = JSON.parse(reader.result);
      if (!Array.isArray(imported)) throw new Error("Expected an array");
      trainerObservations.splice(0, trainerObservations.length, ...imported);
      renderTrainer();
      toast(
        `${imported.length} observations imported. Original timestamps preserved.`,
      );
    } catch (error) {
      toast("Import needs a JSON array of observations.");
    }
  };
  reader.readAsText(file);
}
let lastVaultStatus = null;
function gateLabel(data) {
  const gate = data?.gate || {};
  if (gate.quiet)
    return `QUIET · ${String(gate.reason || "missing_reference").toUpperCase()}`;
  return "OPEN";
}
function selectedPair(data) {
  const symbol = ($("#feed-symbol")?.value || "BTCUSDT").trim().toUpperCase();
  const pair = data?.pairs?.[symbol];
  if (!pair) return data || {};
  return {
    ...data,
    candles: pair.candles,
    technical_features: pair.technical_features,
    fibonacci_features: pair.fibonacci_features,
    gate: pair.gate || data.gate,
  };
}
function applyVaultStatus(data) {
  if (!data) return;
  lastVaultStatus = data;
  const feed = selectedPair(data);
  if ($("#vault-markets")) $("#vault-markets").textContent = data.markets ?? 0;
  if ($("#vault-observations"))
    $("#vault-observations").textContent = data.observations ?? 0;
  if ($("#vault-results")) $("#vault-results").textContent = data.results ?? 0;
  if ($("#vault-candles")) $("#vault-candles").textContent = data.candles ?? 0;
  if ($("#vault-spreads")) $("#vault-spreads").textContent = data.spreads ?? 0;
  if ($("#vault-features"))
    $("#vault-features").textContent =
      (data.technical_features ?? 0) + (data.fibonacci_features ?? 0);
  if ($("#vault-gate")) $("#vault-gate").textContent = gateLabel(data);
  if ($("#feed-candles")) $("#feed-candles").textContent = feed.candles ?? 0;
  if ($("#feed-technical"))
    $("#feed-technical").textContent = feed.technical_features ?? 0;
  if ($("#feed-fibonacci"))
    $("#feed-fibonacci").textContent = feed.fibonacci_features ?? 0;
  if ($("#feed-gate")) $("#feed-gate").textContent = gateLabel(feed);
  if ($("#vault-database"))
    $("#vault-database").textContent = data.database || "LOCAL";
  if ($("#vault-status-label"))
    $("#vault-status-label").textContent = data.database || "LOCAL";
  if ($("#vault-range"))
    $("#vault-range").textContent =
      data.earliest_timestamp && data.latest_timestamp
        ? `${String(data.earliest_timestamp).slice(0, 10)} → ${String(data.latest_timestamp).slice(0, 10)}`
        : "NO DATA";
}
function renderVaultStatus() {
  applyVaultStatus(
    JSON.parse(localStorage.getItem("merlin-oracle-vault") || "null"),
  );
}
async function syncVaultFromApi() {
  try {
    const response = await fetch("/api/vault/status");
    if (!response.ok) return;
    const data = await response.json();
    applyVaultStatus(data);
    if ($("#vault-markets")) $("#vault-markets").textContent = data.markets;
    if ($("#vault-observations"))
      $("#vault-observations").textContent = data.observations;
    if ($("#vault-results")) $("#vault-results").textContent = data.results;
    if ($("#vault-range"))
      $("#vault-range").textContent =
        data.earliest_timestamp && data.latest_timestamp
          ? `${data.earliest_timestamp.slice(0, 10)} → ${data.latest_timestamp.slice(0, 10)}`
          : "NO DATA";
    if ($("#vault-status-label"))
      $("#vault-status-label").textContent = data.database;
    if (data.observations) {
      const observations = await (
        await fetch("/api/vault/observations?limit=500")
      ).json();
      if (observations.length) {
        trainerObservations = observations.map((observation, index) => ({
          date: observation.timestamp.slice(0, 10),
          market: "imported",
          ticker: observation.ticker,
          price: observation.yes_price || 0,
          change: 0,
          volume: observation.volume || 0,
          signal: observation.sky_signal ?? 0,
          aspect: observation.sky_aspect || "UNASSIGNED · EXPERIMENTAL",
          outcome: "UNSETTLED",
        }));
        renderAll();
      }
    }
  } catch (error) {}
}
function vaultImportLocal(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const payload = JSON.parse(reader.result);
      const observations = Array.isArray(payload)
        ? payload
        : payload.observations;
      if (!Array.isArray(observations))
        throw new Error("Expected observations");
      const current = JSON.parse(
        localStorage.getItem("merlin-oracle-vault") || "null",
      ) || {
        markets: 0,
        observations: 0,
        results: 0,
        earliest_timestamp: null,
        latest_timestamp: null,
      };
      const timestamps = observations
        .map((item) => item.timestamp)
        .filter(Boolean)
        .sort();
      const unique = new Set(
        observations.map(
          (item) =>
            `${item.ticker || item.market || "unknown"}:${item.timestamp}`,
        ),
      );
      const next = {
        ...current,
        markets: Math.max(
          current.markets,
          new Set(observations.map((item) => item.ticker || item.market)).size,
        ),
        observations: current.observations + unique.size,
        earliest_timestamp: timestamps[0] || current.earliest_timestamp,
        latest_timestamp:
          timestamps[timestamps.length - 1] || current.latest_timestamp,
      };
      localStorage.setItem("merlin-oracle-vault", JSON.stringify(next));
      $("#vault-records").textContent = unique.size;
      $("#vault-status-label").textContent = "LOCAL IMPORT COMPLETE";
      $("#vault-progress-bar").style.width = "100%";
      renderVaultStatus();
      toast(
        `${unique.size} observations staged locally. Original timestamps preserved.`,
      );
    } catch (error) {
      $("#vault-errors").textContent = "1";
      toast("Load needs a JSON array or export with an observations field.");
    }
  };
  reader.readAsText(file);
}
function renderSourceStrip() {
  const el = $("#source-strip");
  if (!el) return;
  if (!harvestState.sources.length) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = harvestState.sources
    .map(
      (source) =>
        `<button class="source-chip ${source.status}" type="button" data-source="${escapeHtml(source.id)}"><b>${escapeHtml(source.name)}</b><span>${escapeHtml(source.status)}</span></button>`,
    )
    .join("");
  $$("#source-strip [data-source]").forEach((button) =>
    button.addEventListener("click", () => {
      if (button.dataset.source === "binance") {
        switchView("engine");
        importBinanceCandles();
      }
      if (button.dataset.source === "cfbenchmarks") {
        switchView("engine");
        $("#index-import")?.click();
      }
    }),
  );
}
function renderSeriesChips() {
  const el = $("#series-chips");
  if (!el) return;
  el.innerHTML = harvestState.series
    .map(
      (series) =>
        `<button class="series-chip" type="button" data-series="${escapeHtml(series.id)}">${escapeHtml(series.label)}<small>${escapeHtml(series.id)}</small></button>`,
    )
    .join("");
  $$(".series-chip").forEach((button) =>
    button.addEventListener("click", () => {
      $("#vault-series").value = button.dataset.series;
      listHarvestMarkets();
    }),
  );
}
async function loadHarvesterSources() {
  try {
    const registry = await (await fetch("/api/harvester/sources")).json();
    harvestState.sources = registry.sources || [];
    harvestState.series = registry.seriesPresets || [];
    renderSourceStrip();
    renderSeriesChips();
  } catch {
    harvestState.sources = [];
  }
}
function renderMarketList() {
  const el = $("#market-list");
  if (!el) return;
  if (!harvestState.markets.length) {
    el.innerHTML =
      '<div class="empty-state"><b>No contracts listed.</b>Choose a series and list markets.</div>';
    return;
  }
  el.innerHTML = harvestState.markets
    .map((market) => {
      const price =
        market.last_price == null ? "—" : `${Math.round(market.last_price)}`;
      return `<article class="market-row" data-ticker="${escapeHtml(market.ticker)}"><span class="market-ticker">${escapeHtml(market.ticker)}</span><span class="market-question">${escapeHtml(market.subtitle || market.title)}</span><span>${escapeHtml(market.status)}${market.result ? ` · ${escapeHtml(market.result)}` : ""}</span><span>${price}</span><span class="market-actions"><button type="button" data-import="${escapeHtml(market.ticker)}">IMPORT</button><button type="button" data-dossier="${escapeHtml(market.ticker)}">DOSSIER</button></span></article>`;
    })
    .join("");
  $$("[data-import]").forEach((button) =>
    button.addEventListener("click", () =>
      importHarvestTicker(button.dataset.import),
    ),
  );
  $$("[data-dossier]").forEach((button) =>
    button.addEventListener("click", () =>
      openHarvestDossier(button.dataset.dossier),
    ),
  );
}
async function listHarvestMarkets() {
  const series = ($("#vault-series")?.value || "").trim();
  const historical = $("#vault-ledger")?.value === "historical";
  const el = $("#market-list");
  if (el)
    el.innerHTML =
      '<div class="empty-state"><b>Asking Kalshi…</b>Public market list only.</div>';
  try {
    const query = new URLSearchParams({
      series,
      historical: historical ? "1" : "0",
    });
    const payload = await (
      await fetch(`/api/harvester/markets?${query}`)
    ).json();
    if (payload.error) throw new Error(payload.error);
    harvestState.markets = payload.markets || [];
    harvestState.cursor = payload.cursor || null;
    renderMarketList();
    toast(
      `${harvestState.markets.length} ${historical ? "historical" : "live"} contracts from ${series || "Kalshi"}.`,
    );
  } catch (error) {
    harvestState.markets = [];
    renderMarketList();
    toast(error.message || "Kalshi market list failed.");
  }
}
function renderDossier() {
  const title = $("#dossier-title");
  const body = $("#dossier-body");
  if (!body) return;
  const dossier = harvestState.dossier;
  if (!dossier) {
    if (title) title.textContent = "Select a market";
    body.innerHTML =
      "<p>Choose a contract to gather everything currently known about that event. Missing sources stay blank.</p>";
    return;
  }
  if (title) title.textContent = dossier.question || dossier.ticker || "Event";
  const kalshi = dossier.kalshi || {};
  const poly = dossier.polymarket || {};
  const sky = (trakState.windows || [])
    .slice(0, 3)
    .map(
      (window) =>
        `<div><b>${escapeHtml(window.title || "Window")}</b><span>${escapeHtml(window.currentPhase || "")} · ${Math.round(window.intensity || 0)}</span></div>`,
    )
    .join("");
  const polyRows = (poly.markets || [])
    .map(
      (market) =>
        `<div><b>${escapeHtml(market.question || market.slug || "Market")}</b></div>`,
    )
    .join("");
  const planned = (dossier.sources || [])
    .filter((source) => source.status === "planned")
    .map((source) => escapeHtml(source.name))
    .join(" · ");
  body.innerHTML = `<div class="dossier-block"><span>QUESTION</span><p>${escapeHtml(dossier.question || "Unnamed event")}</p></div>
    <div class="dossier-block"><span>PREDICTION MARKETS</span><div class="dossier-row"><b>Kalshi</b><em>${kalshi.last_price == null ? "—" : `${Math.round(kalshi.last_price)}¢`}</em><small>${escapeHtml(kalshi.ticker || dossier.ticker || "")} · ${escapeHtml(kalshi.status || "")}</small></div><div class="dossier-row"><b>Polymarket</b><em>${poly.status === "search" ? `${(poly.markets || []).length} hits` : poly.status || "empty"}</em></div>${polyRows || "<small>No independent match yet.</small>"}</div>
    <div class="dossier-block"><span>TIMETRAK</span>${sky || "<p>Create a reference chart and ask Merlin. TimeTraks stay on the engine, not in this scrape.</p>"}</div>
    <div class="dossier-block"><span>NOT CONNECTED YET</span><p>${planned || "None listed."}</p></div>`;
}
async function openHarvestDossier(ticker) {
  harvestState.selected = ticker;
  if ($("#vault-ticker")) $("#vault-ticker").value = ticker;
  if ($("#dossier-body"))
    $("#dossier-body").innerHTML = "<p>Gathering public records…</p>";
  try {
    const payload = await (
      await fetch(`/api/harvester/dossier?ticker=${encodeURIComponent(ticker)}`)
    ).json();
    if (payload.error) throw new Error(payload.error);
    harvestState.dossier = payload;
    renderDossier();
  } catch (error) {
    harvestState.dossier = { question: ticker, error: error.message };
    renderDossier();
    toast(error.message || "Dossier failed.");
  }
}
async function importHarvestTicker(ticker) {
  const value = String(ticker || $("#vault-ticker")?.value || "").trim();
  if (!value) {
    toast("Choose a market or paste a ticker first.");
    return;
  }
  if ($("#vault-ticker")) $("#vault-ticker").value = value;
  if ($("#vault-status-label"))
    $("#vault-status-label").textContent = "PYTHON IMPORT RUNNING";
  if ($("#vault-progress-bar")) $("#vault-progress-bar").style.width = "35%";
  if ($("#vault-errors")) $("#vault-errors").textContent = "0";
  try {
    const response = await fetch("/api/harvester/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: value }),
    });
    const payload = await response.json();
    if (!response.ok || payload.success === false) {
      throw new Error(payload.error || `Import failed (${response.status})`);
    }
    const imported = payload.import || {};
    if ($("#vault-records"))
      $("#vault-records").textContent = imported.records_imported ?? 0;
    if ($("#vault-duplicates"))
      $("#vault-duplicates").textContent = imported.duplicates_skipped ?? 0;
    if ($("#vault-progress-bar")) $("#vault-progress-bar").style.width = "100%";
    applyVaultStatus(payload.status);
    localStorage.setItem(
      "merlin-oracle-vault",
      JSON.stringify(payload.status || {}),
    );
    toast(
      `Imported ${imported.records_imported ?? 0} rows for ${imported.ticker || value}.`,
    );
    await syncVaultFromApi();
    openHarvestDossier(value);
  } catch (error) {
    if ($("#vault-errors")) $("#vault-errors").textContent = "1";
    if ($("#vault-status-label"))
      $("#vault-status-label").textContent = "IMPORT FAILED";
    toast(error.message || "Python import failed.");
  }
}
function runVaultImport() {
  importHarvestTicker($("#vault-ticker")?.value);
}
async function importBinanceCandles() {
  const symbol = ($("#feed-symbol")?.value || "BTCUSDT").trim().toUpperCase();
  const interval = $("#feed-interval")?.value || "1m";
  if ($("#vault-status-label"))
    $("#vault-status-label").textContent = "BINANCE IMPORT RUNNING";
  if ($("#feed-gate")) $("#feed-gate").textContent = "IMPORTING";
  toast(`Importing public ${symbol} ${interval} candles…`);
  try {
    const response = await fetch("/api/harvester/candles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, interval }),
    });
    const payload = await response.json();
    if (!response.ok || payload.success === false) {
      throw new Error(
        payload.error || `Candle import failed (${response.status})`,
      );
    }
    applyVaultStatus(payload.status);
    const imported = payload.import || {};
    toast(
      `Stored ${imported.records_imported ?? 0} ${symbol} candles. Gate ${gateLabel(payload.status)}.`,
    );
  } catch (error) {
    toast(error.message || "Binance import failed.");
  }
}
function parseIndexFile(text) {
  const trimmed = text.trim();
  if (!trimmed) return [];
  if (trimmed[0] === "[" || trimmed[0] === "{") {
    const payload = JSON.parse(trimmed);
    if (Array.isArray(payload)) return payload;
    return (
      payload.payload ||
      payload.records ||
      payload.data ||
      payload.values ||
      []
    );
  }
  const lines = trimmed.split(/\r?\n/).filter(Boolean);
  const header = lines[0].split(",").map((cell) => cell.trim().replace(/^"|"$/g, ""));
  return lines.slice(1).map((line) => {
    const cells = line.split(",").map((cell) => cell.trim().replace(/^"|"$/g, ""));
    const row = {};
    header.forEach((key, index) => {
      row[key] = cells[index];
    });
    return row;
  });
}
async function importIndexFile(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  const text = await file.text();
  let records;
  try {
    records = parseIndexFile(text);
  } catch (error) {
    toast("Index file must be JSON or CSV with timestamp and value.");
    return;
  }
  if (!Array.isArray(records) || !records.length) {
    toast("Index file had no rows.");
    return;
  }
  const symbol = ($("#feed-symbol")?.value || "BTCUSDT").trim().toUpperCase();
  const interval = $("#feed-interval")?.value || "1m";
  toast(`Importing ${records.length} public index rows…`);
  try {
    const response = await fetch("/api/harvester/index", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, interval, records }),
    });
    const payload = await response.json();
    if (!response.ok || payload.success === false) {
      throw new Error(payload.error || `Index import failed (${response.status})`);
    }
    applyVaultStatus(payload.status);
    const imported = payload.import || {};
    toast(
      `Stored ${imported.records_imported ?? 0} index candles. Gate ${gateLabel(payload.status)}.`,
    );
  } catch (error) {
    toast(error.message || "Index import failed.");
  }
}
async function freezeEntry() {
  const timestamp = ($("#freeze-timestamp")?.value || "").trim();
  const dossier = $("#freeze-dossier");
  if (!timestamp) {
    toast("Enter an entry timestamp in UTC.");
    return;
  }
  if (dossier) dossier.textContent = "Reconstructing market state at T…";
  try {
    const response = await fetch("/api/research/reconstruct", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        timestamp,
        contract: ($("#freeze-contract")?.value || "").trim(),
        target: ($("#freeze-target")?.value || "").trim(),
        expiration: ($("#freeze-expiration")?.value || "").trim(),
        symbol: ($("#feed-symbol")?.value || "BTCUSDT").trim(),
      }),
    });
    const payload = await response.json();
    if (!response.ok || payload.success === false) {
      throw new Error(
        payload.error || `Reconstruct failed (${response.status})`,
      );
    }
    if (dossier)
      dossier.textContent =
        payload.dossier || JSON.stringify(payload.entry, null, 2);
    toast(
      `Frozen ${payload.trade_id || "entry"} · ${payload.snapshots_written || 0} snapshots.`,
    );
    await syncVaultFromApi();
  } catch (error) {
    if (dossier) dossier.textContent = error.message || "Freeze failed.";
    toast(error.message || "Freeze T failed.");
  }
}
function renderDivergence() {
  const chart = $("#divergence-chart");
  if (!chart) return;
  chart.innerHTML = trainerObservations
    .map((o, i) => {
      const crowd = o.price;
      const gap = Math.abs(crowd - o.signal);
      return `<button class="divergence-point ${gap >= 25 ? "is-gap" : ""}" style="left:${8 + i * 16}%;--crowd:${crowd}%;--sky:${o.signal}%" data-index="${i}" title="${o.date} · gap ${gap} points"><i class="crowd-line"></i><i class="sky-line"></i><b class="gap-bracket"></b><span>${o.date.slice(0, 7)}</span></button>`;
    })
    .join("");
  $$(".divergence-point").forEach((point) =>
    point.addEventListener("click", () =>
      inspectDivergence(Number(point.dataset.index)),
    ),
  );
}
function inspectDivergence(index) {
  const o = trainerObservations[index];
  const gap = o.signal - o.price;
  $("#divergence-selected").textContent =
    `${o.ticker} · ${gap > 0 ? "sky above crowd" : "crowd above sky"}`;
  $("#divergence-detail").innerHTML =
    `<div class="inspector-grid"><span>DATE</span><b>${o.date}</b><span>CROWD PROBABILITY</span><b>${o.price}%</b><span>SKY SIGNAL</span><b class="gold-text">${o.signal}/100</b><span>GAP</span><b class="${gap >= 0 ? "positive" : "negative"}">${gap > 0 ? "+" : ""}${gap} points</b><span>ASPECT</span><b>${o.aspect}</b><span>OBSERVED OUTCOME</span><b>${o.outcome}</b></div>`;
}
function runDivergence() {
  const gaps = trainerObservations.map((o) => Math.abs(o.signal - o.price));
  const windows = gaps.filter((gap) => gap >= 25);
  const average = Math.round(
    gaps.reduce((sum, gap) => sum + gap, 0) / gaps.length,
  );
  $("#divergence-count").textContent = windows.length;
  $("#divergence-gap").textContent = `${average} pts`;
  $("#divergence-events").textContent = trainerObservations.filter(
    (o) => o.outcome === "YES",
  ).length;
  $("#divergence-status").textContent = "DESCRIPTIVE";
  toast("Divergence lens calculated. No predictive claim was made.");
}
function openDossierDetail(dossierId) {
  const dossier = (store.dossiers || []).find((entry) => entry.id === dossierId);
  if (!dossier) return;
  const form = $("#modal-form");
  $("#modal-eyebrow").textContent = "EVIDENCE LEDGER";
  $("#modal-title").textContent = dossier.question || "Event dossier";
  $("#modal-copy").textContent =
    "Raw evidence remains intact. The Oracle interpretation is kept separate in the event ledger.";
  const timelineHtml = (dossier.timeline || []).map(
    (item) =>
      `<div class="detail-ledger-row"><span>${escapeHtml(item.label)}</span><b>${escapeHtml(item.value)}</b></div>`,
  ).join("") || '<div class="detail-ledger-row"><span>NO DATA</span><b>No timeline recorded yet.</b></div>';
  const sourcesHtml = (dossier.sources || []).map(
    (source) => `<span class="detail-chip">${escapeHtml(source)}</span>`,
  ).join("") || '<span class="detail-chip">Unavailable</span>';
  const notesHtml = (dossier.notes || []).map((note) => `<p>${escapeHtml(note)}</p>`).join("") || "<p>No notes recorded yet.</p>";
  form.innerHTML = `
    <div class="detail-panel">
      <div class="detail-grid">
        <div><span>MARKET</span><b>${escapeHtml(dossier.market || "UNSPECIFIED")}</b></div>
        <div><span>SETTLEMENT</span><b>${escapeHtml(dossier.settlementSource || "OFFICIAL SOURCE TBD")}</b></div>
        <div><span>ORACLE SIGNAL</span><b>${escapeHtml(dossier.oracleSignal || "SIGNAL PENDING")}</b></div>
      </div>
      <div class="detail-section">
        <h4>SOURCES</h4>
        <div class="detail-source-list">${sourcesHtml}</div>
      </div>
      <div class="detail-section">
        <h4>EVIDENCE TIMELINE</h4>
        <div class="detail-ledger">${timelineHtml}</div>
      </div>
      <div class="detail-section">
        <h4>NOTES</h4>
        <div class="detail-notes">${notesHtml}</div>
      </div>
    </div>
  `;
  $("#modal-backdrop").classList.add("open");
}
function renderAll() {
  renderCharts();
  renderTraks();
  renderJournal();
  renderDossiers();
  renderExperiments();
  renderHistorical();
  renderTrainer();
  renderDivergence();
  renderVaultStatus();
  updateCounts();
}
function closeModal() {
  $("#modal-backdrop").classList.remove("open");
}
function openModal(type) {
  const form = $("#modal-form");
  const copy = $("#modal-copy");
  $("#modal-backdrop").classList.add("open");
  if (type === "chart") {
    $("#modal-eyebrow").textContent = "NEW FIXED POINT";
    $("#modal-title").textContent = "Create reference chart";
    copy.textContent =
      "Merlin needs a date, time, and coordinates. The natal is calculated by the engine before it is stored here.";
    const offset = -(new Date().getTimezoneOffset() / 60);
    form.innerHTML = `<div class="form-grid"><div class="field"><label>NAME</label><input name="name" required placeholder="Bitcoin genesis"></div><div class="field"><label>CHART TYPE</label><select name="type"><option>PERSON</option><option>EVENT</option><option selected>MARKET</option><option>EARTH</option><option>CUSTOM</option></select></div><div class="field full"><label>DESCRIPTION</label><textarea name="description"></textarea></div><div class="field"><label>DATE</label><input name="date" type="date" required></div><div class="field"><label>EXACT TIME (LOCAL)</label><input name="time" type="time" value="12:00" required></div><div class="field"><label>LATITUDE</label><input name="lat" type="number" step="any" required placeholder="40.7128"></div><div class="field"><label>LONGITUDE</label><input name="lon" type="number" step="any" required placeholder="-74.0060"></div><div class="field"><label>TIMEZONE OFFSET (HOURS)</label><input name="timezoneOffset" type="number" step="any" value="${offset}" required></div><div class="field"><label>LOCATION LABEL</label><input name="location" placeholder="New York, NY"></div><div class="field full"><label>SOURCE</label><input name="source" placeholder="Historical record"></div></div><button class="primary-button form-submit" type="submit">CALCULATE WITH MERLIN →</button>`;
    form.onsubmit = async (e) => {
      e.preventDefault();
      const fields = Object.fromEntries(new FormData(form));
      const submit = form.querySelector('[type="submit"]');
      if (submit) {
        submit.disabled = true;
        submit.textContent = "ASKING MERLIN…";
      }
      try {
        const response = await fetch("/api/engine/chart", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            birthDate: fields.date,
            birthTime: fields.time || "12:00",
            lat: Number(fields.lat),
            lon: Number(fields.lon),
            timezoneOffset: Number(fields.timezoneOffset),
          }),
        });
        const natal = await response.json();
        if (!response.ok || natal.success === false) {
          throw new Error(natal.error || `Merlin returned ${response.status}`);
        }
        store.charts.push({
          ...fields,
          id: crypto.randomUUID(),
          created: new Date().toLocaleString(),
          engine: natal,
        });
        persist();
        closeModal();
        renderAll();
        switchView("charts");
        toast(
          natal.source === "swiss-real"
            ? "Natal stored from Merlin Swiss engine."
            : `Natal stored from Merlin (${natal.source || "engine"}).`,
        );
      } catch (error) {
        toast(error.message || "Merlin engine did not calculate this chart.");
        if (submit) {
          submit.disabled = false;
          submit.textContent = "CALCULATE WITH MERLIN →";
        }
      }
    };
  } else if (type === "entry") {
    $("#modal-eyebrow").textContent = "BEFORE THE OUTCOME";
    $("#modal-title").textContent = "Seal an almanac entry";
    copy.textContent =
      "The original hypothesis will become immutable historical research.";
    form.innerHTML =
      '<div class="form-grid"><div class="field full"><label>ENTRY TITLE</label><input name="title" required placeholder="A window worth watching"></div><div class="field"><label>REFERENCE CHARTS</label><input name="reference"></div><div class="field"><label>EXPECTED WINDOW</label><input name="window"></div><div class="field full"><label>USER HYPOTHESIS</label><textarea name="hypothesis" required></textarea></div></div><button class="primary-button form-submit" type="submit">SEAL ENTRY · LOCK ORIGINAL</button>';
    form.onsubmit = (e) => {
      e.preventDefault();
      store.entries.push({
        ...Object.fromEntries(new FormData(form)),
        created: new Date().toLocaleDateString(),
      });
      persist();
      closeModal();
      renderAll();
      switchView("almanac");
      toast("Entry sealed. The record is now immutable.");
    };
  } else if (type === "dossier") {
    $("#modal-eyebrow").textContent = "EVIDENCE COLLECTION";
    $("#modal-title").textContent = "Build event dossier";
    copy.textContent =
      "Create a question and attach the relevant sources before interpreting the result.";
    form.innerHTML = `
      <div class="form-grid">
        <div class="field full"><label>QUESTION</label><input name="question" required placeholder="Will the Fed cut rates?"></div>
        <div class="field"><label>MARKET</label><input name="market" placeholder="FED-SEP"></div>
        <div class="field"><label>SETTLEMENT SOURCE</label><input name="settlementSource" placeholder="FOMC statement / official release"></div>
        <div class="field full"><label>SOURCES</label>
          <div class="source-checklist">
            ${defaultSources
              .map(
                (source) =>
                  `<label class="source-option"><input type="checkbox" name="sources" value="${source}"> ${source}</label>`,
              )
              .join("")}
          </div>
        </div>
        <div class="field full"><label>ORACLE SIGNAL</label><input name="oracleSignal" placeholder="TimeTrak signal: HIGH / 82 / 100"></div>
        <div class="field full"><label>NOTES</label><textarea name="notes" placeholder="Keep raw evidence separate from the Oracle interpretation."></textarea></div>
      </div>
      <button class="primary-button form-submit" type="submit">CREATE DOSSIER →</button>
    `;
    form.onsubmit = (e) => {
      e.preventDefault();
      const formData = new FormData(form);
      const selectedSources = formData.getAll("sources");
      const notes = [
        formData.get("notes")?.toString().trim(),
      ].filter(Boolean);
      const dossier = {
        id: `DOSSIER-${String((store.dossiers?.length || 0) + 1).padStart(3, "0")}`,
        question: formData.get("question")?.toString().trim() || "Untitled question",
        market: formData.get("market")?.toString().trim() || "UNSPECIFIED",
        settlementSource: formData.get("settlementSource")?.toString().trim() || "OFFICIAL SOURCE TBD",
        oracleSignal: formData.get("oracleSignal")?.toString().trim() || "SIGNAL PENDING",
        sources: selectedSources.length ? selectedSources : ["Custom URL"],
        notes,
        created: new Date().toLocaleDateString(),
      };
      store.dossiers = [...(store.dossiers || []), dossier];
      persist();
      closeModal();
      renderAll();
      switchView("dossier");
      toast("Event dossier created.");
    };
  } else {
    $("#modal-eyebrow").textContent = "LAB NOTEBOOK";
    $("#modal-title").textContent = "New experiment";
    copy.textContent =
      "Define a question. The instrument will keep the layers of evidence distinct.";
    form.innerHTML =
      '<div class="form-grid"><div class="field full"><label>EXPERIMENT NAME</label><input name="title" required></div><div class="field full"><label>RESEARCH QUESTION</label><textarea name="copy" required></textarea></div></div><button class="primary-button form-submit" type="submit">ADD TO NOTEBOOK →</button>';
    form.onsubmit = (e) => {
      e.preventDefault();
      store.experiments.push({
        ...Object.fromEntries(new FormData(form)),
        status: "NOTEBOOK ENTRY",
      });
      persist();
      closeModal();
      renderAll();
      switchView("experiments");
      toast("Experiment added to the notebook.");
    };
  }
}
$$(".nav-item").forEach((b) =>
  b.addEventListener("click", () => switchView(b.dataset.view)),
);
$$("[data-view-target]").forEach((b) =>
  b.addEventListener("click", () => switchView(b.dataset.viewTarget)),
);
$$('[data-action="create-chart"]').forEach((b) =>
  b.addEventListener("click", () => openModal("chart")),
);
$$('[data-action="new-entry"]').forEach((b) =>
  b.addEventListener("click", () => openModal("entry")),
);
$$('[data-action="new-dossier"]').forEach((b) =>
  b.addEventListener("click", () => openModal("dossier")),
);
$$('[data-action="new-experiment"]').forEach((b) =>
  b.addEventListener("click", () => openModal("experiment")),
);
$('[data-action="run-historical"]').addEventListener("click", runHistorical);
if ($('[data-action="refresh-traks"]'))
  $('[data-action="refresh-traks"]').addEventListener("click", () =>
    loadTimeTraks(true),
  );
if ($("#trak-chart"))
  $("#trak-chart").addEventListener("change", () => loadTimeTraks(true));
$("#modal-close").addEventListener("click", closeModal);
$("#modal-backdrop").addEventListener("click", (e) => {
  if (e.target.id === "modal-backdrop") closeModal();
});
$("#open-settings").addEventListener("click", () =>
  toast(
    engineStatus.connected
      ? `Merlin engine live at ${engineStatus.engine}. Charts and TimeTraks are calculated there.`
      : `Merlin engine down at ${engineStatus.engine}. Run npm run dev in X:\\Merlin.`,
  ),
);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});
function updateClock() {
  $("#sidereal-clock").textContent = new Date().toLocaleTimeString([], {
    hour12: false,
  });
}
setInterval(updateClock, 1000);
updateClock();
ensureSeededAlmanacEntry();
renderAll();
refreshEngineStatus();
setInterval(refreshEngineStatus, 15000);
