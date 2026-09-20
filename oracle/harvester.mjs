import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));
const kalshiBase = "https://api.elections.kalshi.com/trade-api/v2";
const TOKEN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/;

export function isSafeToken(value) {
  return TOKEN.test(String(value || ""));
}

export async function loadRegistry() {
  const text = await readFile(
    join(root, "oracle", "harvester", "registry.json"),
    "utf8",
  );
  return JSON.parse(text);
}

function pythonCandidates() {
  if (process.env.ORACLE_PYTHON) return [process.env.ORACLE_PYTHON];
  return process.platform === "win32"
    ? ["python", "py"]
    : ["python3", "python"];
}

export function runOracle(args, { timeoutMs = 120000 } = {}) {
  const argv = ["oracle.py", ...args];
  const bins = pythonCandidates();
  return new Promise((resolve, reject) => {
    const tryBin = (index) => {
      const bin = bins[index];
      if (!bin) {
        reject(
          new Error(
            "Python was not found. Install Python 3 or set ORACLE_PYTHON.",
          ),
        );
        return;
      }
      const childArgs = bin === "py" ? ["-3", ...argv] : argv;
      const child = spawn(bin, childArgs, {
        cwd: root,
        windowsHide: true,
      });
      let stdout = "";
      let stderr = "";
      let spawned = false;
      const timer = setTimeout(() => {
        child.kill();
        reject(new Error("Python command timed out."));
      }, timeoutMs);
      child.once("spawn", () => {
        spawned = true;
      });
      child.stdout.on("data", (chunk) => {
        stdout += chunk;
      });
      child.stderr.on("data", (chunk) => {
        stderr += chunk;
      });
      child.on("error", (error) => {
        clearTimeout(timer);
        if (!spawned && bins[index + 1]) {
          tryBin(index + 1);
          return;
        }
        reject(error);
      });
      child.on("close", (code) => {
        clearTimeout(timer);
        if (code !== 0) {
          reject(
            new Error(
              (stderr || stdout).trim() || `python exited with code ${code}`,
            ),
          );
          return;
        }
        const text = stdout.trim();
        try {
          resolve(JSON.parse(text));
        } catch {
          resolve({ success: true, raw: text });
        }
      });
    };
    tryBin(0);
  });
}

function dollarsToCents(value) {
  if (value == null || value === "") return null;
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return number <= 1.5 ? Math.round(number * 10000) / 100 : number;
}

function compactMarket(market) {
  const last = dollarsToCents(
    market.last_price_dollars ||
      market.yes_ask_dollars ||
      market.yes_bid_dollars,
  );
  return {
    ticker: market.ticker,
    event: market.event_ticker || null,
    title:
      market.title || market.subtitle || market.yes_sub_title || market.ticker,
    subtitle: market.yes_sub_title || market.subtitle || "",
    status: market.status || "",
    result: market.result || "",
    yes_bid: dollarsToCents(market.yes_bid_dollars),
    yes_ask: dollarsToCents(market.yes_ask_dollars),
    last_price: last,
    open_time: market.open_time || null,
    close_time: market.close_time || null,
    volume: market.volume_fp || market.volume_24h_fp || null,
  };
}

async function kalshiGet(path, params = {}) {
  const url = new URL(`${kalshiBase}/${path.replace(/^\//, "")}`);
  for (const [key, value] of Object.entries(params)) {
    if (value != null && value !== "") url.searchParams.set(key, String(value));
  }
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = { error: text.slice(0, 240) };
  }
  if (!response.ok) {
    const error = new Error(payload?.error || `Kalshi ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

export async function listKalshiMarkets({
  series,
  historical = false,
  cursor,
  limit = 40,
} = {}) {
  if (series && !isSafeToken(series)) {
    throw new Error("Series ticker contains invalid characters.");
  }
  const path = historical ? "historical/markets" : "markets";
  const payload = await kalshiGet(path, {
    series_ticker: series || undefined,
    limit,
    cursor: cursor || undefined,
  });
  const markets = Array.isArray(payload.markets)
    ? payload.markets.map(compactMarket)
    : [];
  return {
    source: "kalshi",
    historical: Boolean(historical),
    series: series || null,
    cursor: payload.cursor || null,
    markets,
  };
}

export async function searchPolymarket(query) {
  const q = String(query || "")
    .trim()
    .slice(0, 120);
  if (!q) return { source: "polymarket", status: "empty", markets: [] };
  const url = new URL("https://gamma-api.polymarket.com/public-search");
  url.searchParams.set("q", q);
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    return {
      source: "polymarket",
      status: "error",
      error: `Polymarket search failed (${response.status})`,
      markets: [],
    };
  }
  const payload = await response.json();
  const rows = []
    .concat(payload.markets || [], payload.events || [])
    .slice(0, 8)
    .map((item) => ({
      id: item.id || item.slug || item.conditionId,
      question: item.question || item.title || item.slug,
      slug: item.slug || null,
      outcomePrices: item.outcomePrices || null,
    }));
  return {
    source: "polymarket",
    status: rows.length ? "search" : "empty",
    markets: rows,
  };
}

export async function buildDossier({ ticker, series }) {
  const registry = await loadRegistry();
  let kalshi = null;
  if (ticker) {
    if (!isSafeToken(ticker))
      throw new Error("Market ticker contains invalid characters.");
    try {
      const payload = await kalshiGet(`markets/${ticker}`);
      kalshi = compactMarket(payload.market || payload);
    } catch {
      try {
        const payload = await kalshiGet(`historical/markets/${ticker}`);
        kalshi = compactMarket(payload.market || payload);
      } catch (error) {
        kalshi = { error: error.message };
      }
    }
  }
  const question = kalshi?.title || kalshi?.subtitle || ticker || series || "";
  const polymarket = question
    ? await searchPolymarket(question)
    : { source: "polymarket", status: "empty", markets: [] };
  return {
    question,
    ticker: ticker || null,
    series: series || kalshi?.event || null,
    kalshi,
    polymarket,
    sources: registry.sources.map((source) => ({
      id: source.id,
      name: source.name,
      type: source.type,
      status: source.status,
    })),
  };
}
