setTimeout(() => {
  if ($('[data-action="vault-import"]'))
    $('[data-action="vault-import"]').addEventListener("click", runVaultImport);
  if ($('[data-action="vault-command"]'))
    $('[data-action="vault-command"]').addEventListener(
      "click",
      copyVaultCommand,
    );
  if ($("#vault-import-file"))
    $("#vault-import-file").addEventListener("change", vaultImportLocal);
}, 0);
setTimeout(syncVaultFromApi, 100);
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
  $("#view-label").textContent = view.toUpperCase();
  renderAll();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function renderCharts() {
  const el = $("#chart-list");
  if (!el) return;
  if (!store.charts.length) {
    el.innerHTML =
      '<div class="empty-state"><b>No fixed points yet.</b>Create a chart to give the Oracle its first reference in time.</div>';
    return;
  }
  el.innerHTML = store.charts
    .map(
      (c) =>
        `<article class="chart-card"><div class="chart-type">${c.type}<br><span>CHART</span></div><div><h3>${escapeHtml(c.name)}</h3><p>${escapeHtml(c.description || "No description recorded.")}</p></div><div class="chart-date"><b>${c.date || "Undated"}</b><br>${escapeHtml(c.location || "Location not set")}</div></article>`,
    )
    .join("");
}
function renderTraks() {
  const el = $("#traks-container");
  if (!el) return;
  const traks = [
    [
      "Mars △ Saturn",
      store.charts[0]?.name || "Demo reference chart",
      "MAR 18 — APR 04, 2025",
      68,
      "APPLYING",
    ],
    [
      "Jupiter ☌ Sun",
      store.charts[1]?.name || "Earth / equinox",
      "APR 02 — APR 17, 2025",
      51,
      "SEPARATING",
    ],
    ["Venus □ Uranus", "Market cycle", "APR 21 — MAY 02, 2025", 32, "APPLYING"],
  ];
  el.innerHTML = traks
    .map(
      (t) =>
        `<article class="trak-card"><div><span class="section-kicker">TIME WINDOW</span><h3>${t[0]}</h3><p>${escapeHtml(t[1])}</p></div><div><p>${t[2]}</p><div class="trak-bar"><i style="width:${t[3]}%"></i></div></div><div class="trak-meta"><b>${t[3]} / 100</b>${t[4]}<br>orb 1°42'</div></article>`,
    )
    .join("");
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
function renderVaultStatus() {
  const data = JSON.parse(
    localStorage.getItem("merlin-oracle-vault") || "null",
  ) || {
    markets: 0,
    observations: 0,
    results: 0,
    earliest_timestamp: null,
    latest_timestamp: null,
  };
  if ($("#vault-markets")) $("#vault-markets").textContent = data.markets;
  if ($("#vault-observations"))
    $("#vault-observations").textContent = data.observations;
  if ($("#vault-results")) $("#vault-results").textContent = data.results;
  if ($("#vault-range"))
    $("#vault-range").textContent =
      data.earliest_timestamp && data.latest_timestamp
        ? `${data.earliest_timestamp.slice(0, 10)} → ${data.latest_timestamp.slice(0, 10)}`
        : "NO DATA";
}
async function syncVaultFromApi() {
  try {
    const response = await fetch("/api/vault/status");
    if (!response.ok) return;
    const data = await response.json();
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
function runVaultImport() {
  const ticker = $("#vault-ticker").value.trim();
  if (!ticker) {
    toast("Enter one market ticker before importing.");
    return;
  }
  const command = `python oracle.py import ${ticker}`;
  navigator.clipboard?.writeText(command);
  $("#vault-status-label").textContent = "COMMAND READY · PYTHON";
  $("#vault-progress-bar").style.width = "18%";
  toast(
    "Python import command copied. Run it locally to retrieve public data.",
  );
}
function copyVaultCommand() {
  const ticker = $("#vault-ticker").value.trim() || "MARKET_TICKER";
  const command = `python oracle.py import ${ticker} --database data/kalshi.db`;
  navigator.clipboard?.writeText(command);
  toast("Import command copied to clipboard.");
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
      "Set a precise point in time for the Oracle to investigate.";
    form.innerHTML =
      '<div class="form-grid"><div class="field"><label>NAME</label><input name="name" required placeholder="Bitcoin"></div><div class="field"><label>CHART TYPE</label><select name="type"><option>PERSON</option><option>EVENT</option><option>MARKET</option><option>EARTH</option><option>CUSTOM</option></select></div><div class="field full"><label>DESCRIPTION</label><textarea name="description"></textarea></div><div class="field"><label>DATE</label><input name="date" type="date" required></div><div class="field"><label>EXACT TIME</label><input name="time" type="time"></div><div class="field"><label>LOCATION</label><input name="location" placeholder="New York, NY"></div><div class="field"><label>SOURCE</label><input name="source" placeholder="Historical record"></div></div><button class="primary-button form-submit" type="submit">SAVE REFERENCE CHART →</button>';
    form.onsubmit = (e) => {
      e.preventDefault();
      store.charts.push({
        ...Object.fromEntries(new FormData(form)),
        created: new Date().toLocaleString(),
      });
      persist();
      closeModal();
      renderAll();
      switchView("charts");
      toast("Reference chart stored locally.");
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
$("#modal-close").addEventListener("click", closeModal);
$("#modal-backdrop").addEventListener("click", (e) => {
  if (e.target.id === "modal-backdrop") closeModal();
});
$("#open-settings").addEventListener("click", () =>
  toast("Oracle notes: offline, versioned, and private to this browser."),
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
