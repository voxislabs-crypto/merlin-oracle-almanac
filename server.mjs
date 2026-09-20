import { createServer } from "node:http";
import { readFile, writeFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import {
  buildDossier,
  isSafeToken,
  listKalshiMarkets,
  loadRegistry,
  runOracle,
} from "./oracle/harvester.mjs";

const root = fileURLToPath(new URL(".", import.meta.url));
const port = Number(process.env.PORT || 8000);
const merlinEngineUrl = (
  process.env.MERLIN_ENGINE_URL || "http://127.0.0.1:3000"
).replace(/\/$/, "");
const databasePath = join(root, "data", "kalshi.db");
const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".png": "image/png",
};

let sqliteModule = undefined;
let astronomyModule = undefined;

async function getAstronomy() {
  if (astronomyModule === false) return null;
  if (astronomyModule) return astronomyModule;
  try {
    astronomyModule = await import("./oracle/swiss-ephemeris.mjs");
    return astronomyModule;
  } catch {
    astronomyModule = false;
    return null;
  }
}

async function getDatabaseSync() {
  if (sqliteModule === false) return null;
  if (sqliteModule) return sqliteModule.DatabaseSync;
  try {
    sqliteModule = await import("node:sqlite");
    return sqliteModule.DatabaseSync;
  } catch {
    sqliteModule = false;
    return null;
  }
}

async function pythonStatus() {
  try {
    const status = await runOracle(["status", "--database", "data/kalshi.db"], {
      timeoutMs: 20000,
    });
    return { ...status, database: status.database || "LOCAL / PYTHON SQLITE" };
  } catch (error) {
    return {
      markets: 0,
      observations: 0,
      results: 0,
      earliest_timestamp: null,
      latest_timestamp: null,
      last_import: null,
      database: "LOCAL / EMPTY",
      error: error.message,
    };
  }
}

async function databaseStatus() {
  try {
    const DatabaseSync = await getDatabaseSync();
    if (!DatabaseSync) return pythonStatus();
    const database = new DatabaseSync(databasePath, { readOnly: true });
    const count = (table) =>
      database.prepare(`SELECT COUNT(*) AS count FROM ${table}`).get().count;
    const bounds = database
      .prepare(
        "SELECT MIN(timestamp) AS earliest, MAX(timestamp) AS latest FROM market_observations",
      )
      .get();
    const lastImport = database
      .prepare("SELECT finished_at FROM import_log ORDER BY id DESC LIMIT 1")
      .get();
    const safeCount = (table) => {
      try {
        return count(table);
      } catch {
        return 0;
      }
    };
    let candleBounds = { start: null, end: null };
    try {
      candleBounds =
        database
          .prepare(
            "SELECT MIN(open_time) AS start, MAX(close_time) AS end FROM candles",
          )
          .get() || candleBounds;
    } catch {
      candleBounds = { start: null, end: null };
    }
    let gate = {
      quiet: true,
      reason: "missing_reference",
      spread_bps: null,
      timestamp: null,
    };
    try {
      const lastSpread = database
        .prepare(
          "SELECT timestamp, quiet, reason, spread_bps FROM spread_snapshots ORDER BY timestamp DESC LIMIT 1",
        )
        .get();
      if (lastSpread) {
        gate = {
          timestamp: lastSpread.timestamp,
          quiet: Boolean(lastSpread.quiet),
          reason: lastSpread.reason,
          spread_bps: lastSpread.spread_bps,
        };
      }
    } catch {
      gate = {
        quiet: true,
        reason: "missing_reference",
        spread_bps: null,
        timestamp: null,
      };
    }
    const pairs = {};
    try {
      const pairRows = database
        .prepare(
          "SELECT symbol, COUNT(*) AS candles, MIN(open_time) AS start, MAX(close_time) AS end FROM candles GROUP BY symbol",
        )
        .all();
      for (const row of pairRows) {
        let pairGate = {
          quiet: true,
          reason: "missing_reference",
          spread_bps: null,
          timestamp: null,
        };
        try {
          const last = database
            .prepare(
              "SELECT timestamp, quiet, reason, spread_bps FROM spread_snapshots WHERE symbol=? ORDER BY timestamp DESC LIMIT 1",
            )
            .get(row.symbol);
          if (last) {
            pairGate = {
              timestamp: last.timestamp,
              quiet: Boolean(last.quiet),
              reason: last.reason,
              spread_bps: last.spread_bps,
            };
          }
        } catch {}
        let technical = 0;
        let fibonacci = 0;
        try {
          technical = database
            .prepare(
              "SELECT COUNT(*) AS count FROM technical_features WHERE symbol=?",
            )
            .get(row.symbol).count;
          fibonacci = database
            .prepare(
              "SELECT COUNT(*) AS count FROM fibonacci_features WHERE symbol=?",
            )
            .get(row.symbol).count;
        } catch {}
        pairs[row.symbol] = {
          candles: row.candles,
          candle_start: row.start,
          candle_end: row.end,
          technical_features: technical,
          fibonacci_features: fibonacci,
          gate: pairGate,
        };
      }
    } catch {}
    const status = {
      markets: safeCount("markets"),
      observations: safeCount("market_observations"),
      results: safeCount("market_results"),
      candles: safeCount("candles"),
      spreads: safeCount("spread_snapshots"),
      technical_features: safeCount("technical_features"),
      fibonacci_features: safeCount("fibonacci_features"),
      reconstructions: safeCount("trade_reconstructions"),
      earliest_timestamp: bounds.earliest,
      latest_timestamp: bounds.latest,
      candle_start: candleBounds?.start || null,
      candle_end: candleBounds?.end || null,
      last_import: lastImport?.finished_at || null,
      gate,
      pairs,
      database: "LOCAL / SQLITE",
    };
    database.close();
    return status;
  } catch {
    return {
      markets: 0,
      observations: 0,
      results: 0,
      candles: 0,
      spreads: 0,
      technical_features: 0,
      fibonacci_features: 0,
      reconstructions: 0,
      earliest_timestamp: null,
      latest_timestamp: null,
      candle_start: null,
      candle_end: null,
      last_import: null,
      gate: { quiet: true, reason: "missing_reference", spread_bps: null },
      database: "LOCAL / EMPTY",
    };
  }
}

async function databaseObservations(url) {
  try {
    const DatabaseSync = await getDatabaseSync();
    if (!DatabaseSync) {
      const limit = Math.min(
        Number(url.searchParams.get("limit") || 500),
        5000,
      );
      const rows = await runOracle(
        [
          "observations",
          "--database",
          "data/kalshi.db",
          "--limit",
          String(limit),
        ],
        { timeoutMs: 20000 },
      );
      return Array.isArray(rows) ? rows : [];
    }
    const database = new DatabaseSync(databasePath, { readOnly: true });
    const limit = Math.min(Number(url.searchParams.get("limit") || 500), 5000);
    const rows = database
      .prepare(
        "SELECT ticker, timestamp, yes_price, no_price, yes_bid, yes_ask, volume, open_interest FROM market_observations ORDER BY timestamp LIMIT ?",
      )
      .all(limit);
    database.close();
    const astronomy = await getAstronomy();
    return rows.map((row) => {
      try {
        if (!astronomy) return row;
        const signal = astronomy.calculateTimeTrak(row.timestamp);
        return {
          ...row,
          sky_signal: signal.intensity,
          sky_aspect: `${signal.objectA} ${signal.aspect} ${signal.objectB}`,
          sky_orb: signal.orb,
          sky_direction: signal.direction,
          sky_onset: signal.onset,
          sky_peak: signal.peak,
          sky_duration_hours: signal.durationHours,
          astronomy_version: signal.astronomyVersion,
          timetrak_version: signal.calculationVersion,
        };
      } catch {
        return row;
      }
    });
  } catch {
    return [];
  }
}

function sendJson(response, payload, status = 200) {
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(JSON.stringify(payload));
}

async function readJsonBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function engineDownPayload(error) {
  const timedOut = error?.name === "AbortError";
  return {
    connected: false,
    success: false,
    engine: merlinEngineUrl,
    error: timedOut
      ? `Merlin engine at ${merlinEngineUrl} timed out.`
      : `Merlin engine is not reachable at ${merlinEngineUrl}. In X:\\Merlin run npm run dev, then reload this instrument.`,
  };
}

async function callMerlin(
  pathname,
  { method = "GET", body, timeoutMs = 8000 } = {},
) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${merlinEngineUrl}${pathname}`, {
      method,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const text = await response.text();
    let payload = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      payload = {
        error: text.slice(0, 240) || "Merlin returned a non-JSON response",
      };
    }
    return { ok: response.ok, status: response.status, payload };
  } finally {
    clearTimeout(timer);
  }
}

function compactNatal(payload) {
  const data = payload?.data || {};
  const positions = Array.isArray(data.positions)
    ? data.positions.map((planet) => ({
        name: planet.name,
        sign: planet.sign,
        degree: planet.degree,
        minute: planet.minute,
        house: planet.house,
        longitude: planet.longitude,
        retrograde: planet.retrograde,
      }))
    : [];
  return {
    success: payload?.success === true,
    source: payload?.source || data?.metadata?.calculationSource || null,
    positions,
    ascendant: data.ascendant || null,
    mc: data.mc || null,
    personalitySnapshot: data.personalitySnapshot || null,
    metadata: data.metadata || null,
  };
}

function compactTransits(payload) {
  const data = payload?.data || {};
  const windows = Array.isArray(data.transitWindows) ? data.transitWindows : [];
  const transits = Array.isArray(data.significant)
    ? data.significant
    : Array.isArray(data.all)
      ? data.all.slice(0, 12)
      : [];
  return {
    success: payload?.success === true,
    source: payload?.source || null,
    windows,
    transits,
    summary: data.summary || null,
  };
}

function natalInput(body) {
  const birthDate = String(body?.birthDate || "").slice(0, 10);
  const birthTime = String(body?.birthTime || "12:00").slice(0, 5);
  const lat = Number(body?.lat);
  const lon = Number(body?.lon);
  const timezoneOffset = Number(body?.timezoneOffset);
  return {
    birthDate,
    birthTime,
    lat,
    lon,
    timezoneOffset: Number.isFinite(timezoneOffset)
      ? timezoneOffset
      : undefined,
    clientDate: body?.clientDate || undefined,
  };
}

function missingNatal(input) {
  if (!input.birthDate) return "birthDate is required";
  if (!Number.isFinite(input.lat) || !Number.isFinite(input.lon)) {
    return "lat and lon are required so Merlin can calculate houses and transits";
  }
  return null;
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url, `http://${request.headers.host}`);
  if (url.pathname === "/api/vault/status") {
    sendJson(response, await databaseStatus());
    return;
  }
  if (url.pathname === "/api/vault/observations") {
    sendJson(response, await databaseObservations(url));
    return;
  }
  if (url.pathname === "/api/harvester/sources") {
    sendJson(response, await loadRegistry());
    return;
  }
  if (url.pathname === "/api/harvester/markets") {
    try {
      const payload = await listKalshiMarkets({
        series: url.searchParams.get("series") || "",
        historical: url.searchParams.get("historical") === "1",
        cursor: url.searchParams.get("cursor") || "",
        limit: Number(url.searchParams.get("limit") || 40),
      });
      sendJson(response, payload);
    } catch (error) {
      sendJson(
        response,
        { success: false, error: error.message, markets: [] },
        error.status || 502,
      );
    }
    return;
  }
  if (url.pathname === "/api/harvester/import") {
    if (request.method !== "POST") {
      sendJson(
        response,
        { success: false, error: "POST a market ticker" },
        405,
      );
      return;
    }
    try {
      const body = await readJsonBody(request);
      const ticker = String(body.ticker || "").trim();
      if (!isSafeToken(ticker)) {
        sendJson(
          response,
          { success: false, error: "Enter a valid Kalshi market ticker." },
          400,
        );
        return;
      }
      const result = await runOracle(
        ["import", ticker, "--database", "data/kalshi.db"],
        { timeoutMs: 180000 },
      );
      const status = await pythonStatus();
      sendJson(response, { success: true, import: result, status });
    } catch (error) {
      if (error instanceof SyntaxError) {
        sendJson(
          response,
          { success: false, error: "Request body must be JSON" },
          400,
        );
        return;
      }
      sendJson(response, { success: false, error: error.message }, 500);
    }
    return;
  }
  if (url.pathname === "/api/harvester/candles") {
    if (request.method !== "POST") {
      sendJson(
        response,
        { success: false, error: "POST a Binance symbol" },
        405,
      );
      return;
    }
    try {
      const body = await readJsonBody(request);
      const symbol = String(body.symbol || "BTCUSDT")
        .trim()
        .toUpperCase();
      const interval = String(body.interval || "1m").trim();
      if (
        !isSafeToken(symbol) ||
        !["1m", "5m", "15m", "1h"].includes(interval)
      ) {
        sendJson(
          response,
          {
            success: false,
            error: "Enter a valid public Binance symbol and interval.",
          },
          400,
        );
        return;
      }
      const args = [
        "candles",
        symbol,
        "--interval",
        interval,
        "--database",
        "data/kalshi.db",
      ];
      if (body.start) args.push("--start", String(body.start));
      if (body.end) args.push("--end", String(body.end));
      const result = await runOracle(args, { timeoutMs: 180000 });
      const status = await pythonStatus();
      sendJson(response, { success: true, import: result, status });
    } catch (error) {
      sendJson(response, { success: false, error: error.message }, 500);
    }
    return;
  }
  if (url.pathname === "/api/harvester/index") {
    if (request.method !== "POST") {
      sendJson(response, { success: false, error: "POST index records" }, 405);
      return;
    }
    try {
      const body = await readJsonBody(request);
      const symbol = String(body.symbol || "BTCUSDT").trim().toUpperCase();
      const interval = String(body.interval || "1m").trim();
      const records = body.records ?? body.payload ?? body.data ?? [];
      if (!isSafeToken(symbol) || !["1m", "5m", "15m", "1h"].includes(interval)) {
        sendJson(
          response,
          { success: false, error: "Enter a valid symbol and interval." },
          400,
        );
        return;
      }
      if (!Array.isArray(records) || !records.length) {
        sendJson(
          response,
          { success: false, error: "Index file had no timestamp/value rows." },
          400,
        );
        return;
      }
      const uploadPath = join(root, "data", "_index_upload.json");
      await writeFile(uploadPath, JSON.stringify(records), "utf8");
      const result = await runOracle(
        [
          "index",
          "data/_index_upload.json",
          "--symbol",
          symbol,
          "--interval",
          interval,
          "--database",
          "data/kalshi.db",
        ],
        { timeoutMs: 180000 },
      );
      const status = await pythonStatus();
      sendJson(response, { success: true, import: result, status });
    } catch (error) {
      sendJson(response, { success: false, error: error.message }, 500);
    }
    return;
  }
  if (url.pathname === "/api/research/reconstruct") {
    if (request.method !== "POST") {
      sendJson(
        response,
        { success: false, error: "POST an entry timestamp" },
        405,
      );
      return;
    }
    try {
      const body = await readJsonBody(request);
      const timestamp = String(body.timestamp || "").trim();
      if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(timestamp)) {
        sendJson(
          response,
          { success: false, error: "Entry timestamp must be UTC ISO-8601." },
          400,
        );
        return;
      }
      const args = [
        "reconstruct",
        "--timestamp",
        timestamp,
        "--database",
        "data/kalshi.db",
      ];
      if (body.contract) {
        const contract = String(body.contract).trim();
        if (!isSafeToken(contract)) {
          sendJson(
            response,
            { success: false, error: "Invalid contract ticker." },
            400,
          );
          return;
        }
        args.push("--contract", contract);
      }
      if (body.target != null && body.target !== "")
        args.push("--target", String(body.target));
      if (body.expiration) args.push("--expiration", String(body.expiration));
      if (body.symbol && isSafeToken(String(body.symbol))) {
        args.push("--symbol", String(body.symbol).toUpperCase());
      }
      const result = await runOracle(args, { timeoutMs: 120000 });
      sendJson(response, { success: true, ...result });
    } catch (error) {
      sendJson(response, { success: false, error: error.message }, 500);
    }
    return;
  }
  if (url.pathname === "/api/harvester/dossier") {
    try {
      const payload = await buildDossier({
        ticker: url.searchParams.get("ticker") || "",
        series: url.searchParams.get("series") || "",
      });
      sendJson(response, payload);
    } catch (error) {
      sendJson(response, { success: false, error: error.message }, 400);
    }
    return;
  }
  if (url.pathname === "/api/engine/status") {
    try {
      const result = await callMerlin("/", { method: "GET", timeoutMs: 4000 });
      sendJson(response, {
        connected: true,
        engine: merlinEngineUrl,
        status: result.status,
      });
    } catch (error) {
      sendJson(response, engineDownPayload(error), 503);
    }
    return;
  }
  if (url.pathname === "/api/engine/chart") {
    if (request.method !== "POST") {
      sendJson(
        response,
        { success: false, error: "POST a natal chart payload" },
        405,
      );
      return;
    }
    try {
      const input = natalInput(await readJsonBody(request));
      const missing = missingNatal(input);
      if (missing) {
        sendJson(response, { success: false, error: missing }, 400);
        return;
      }
      const result = await callMerlin("/api/calculate-birth-chart", {
        method: "POST",
        timeoutMs: 30000,
        body: {
          ...input,
          purpose: "landing-preview",
        },
      });
      if (!result.ok || result.payload?.success === false) {
        sendJson(
          response,
          {
            success: false,
            engine: merlinEngineUrl,
            error:
              result.payload?.error ||
              `Merlin chart calculation failed (${result.status})`,
          },
          result.status || 502,
        );
        return;
      }
      sendJson(response, {
        ...compactNatal(result.payload),
        engine: merlinEngineUrl,
      });
    } catch (error) {
      if (error instanceof SyntaxError) {
        sendJson(
          response,
          { success: false, error: "Request body must be JSON" },
          400,
        );
        return;
      }
      sendJson(response, engineDownPayload(error), 503);
    }
    return;
  }
  if (url.pathname === "/api/engine/transits") {
    if (request.method !== "POST") {
      sendJson(
        response,
        { success: false, error: "POST a natal chart payload" },
        405,
      );
      return;
    }
    try {
      const input = natalInput(await readJsonBody(request));
      const missing = missingNatal(input);
      if (missing) {
        sendJson(response, { success: false, error: missing }, 400);
        return;
      }
      const result = await callMerlin("/api/transits", {
        method: "POST",
        timeoutMs: 60000,
        body: input,
      });
      if (!result.ok || result.payload?.success === false) {
        sendJson(
          response,
          {
            success: false,
            engine: merlinEngineUrl,
            error:
              result.payload?.error ||
              `Merlin transit calculation failed (${result.status})`,
          },
          result.status || 502,
        );
        return;
      }
      sendJson(response, {
        ...compactTransits(result.payload),
        engine: merlinEngineUrl,
      });
    } catch (error) {
      if (error instanceof SyntaxError) {
        sendJson(
          response,
          { success: false, error: "Request body must be JSON" },
          400,
        );
        return;
      }
      sendJson(response, engineDownPayload(error), 503);
    }
    return;
  }
  if (url.pathname === "/api/astronomy") {
    try {
      const astronomy = await getAstronomy();
      if (!astronomy) {
        sendJson(
          response,
          {
            error:
              "Local Swiss adapter is unavailable. Use /api/engine/transits against the Merlin engine instead.",
          },
          503,
        );
        return;
      }
      const timestamp = url.searchParams.get("timestamp");
      const signal = astronomy.calculateTimeTrak(
        timestamp,
        url.searchParams.get("objectA") || "Saturn",
        url.searchParams.get("objectB") || "Pluto",
      );
      sendJson(response, {
        ...signal,
        astronomyVersion: astronomy.ASTRONOMY_VERSION,
      });
    } catch (error) {
      response.writeHead(400, {
        "Content-Type": "application/json; charset=utf-8",
      });
      response.end(JSON.stringify({ error: error.message }));
    }
    return;
  }
  const requestedPath = decodeURIComponent(url.pathname);
  const relativePath =
    requestedPath === "/" ? "index.html" : requestedPath.slice(1);
  const filePath = normalize(join(root, relativePath));

  if (!filePath.startsWith(root)) {
    response.writeHead(403);
    response.end("Forbidden");
    return;
  }

  try {
    const body = await readFile(filePath);
    response.writeHead(200, {
      "Content-Type":
        contentTypes[extname(filePath)] || "application/octet-stream",
    });
    response.end(body);
  } catch {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Not found");
  }
});

server.listen(port, () => {
  console.log(`Merlin Oracle running at http://localhost:${port}`);
  console.log(`Merlin engine proxy → ${merlinEngineUrl}`);
});
