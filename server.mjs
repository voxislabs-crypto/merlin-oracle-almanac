import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { DatabaseSync } from "node:sqlite";
import {
  ASTRONOMY_VERSION,
  calculatePlanetPositions,
  calculateTimeTrak,
} from "./oracle/swiss-ephemeris.mjs";

const root = fileURLToPath(new URL(".", import.meta.url));
const port = Number(process.env.PORT || 8000);
const databasePath = join(root, "data", "kalshi.db");
const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
};

function databaseStatus() {
  try {
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
    const status = {
      markets: count("markets"),
      observations: count("market_observations"),
      results: count("market_results"),
      earliest_timestamp: bounds.earliest,
      latest_timestamp: bounds.latest,
      last_import: lastImport?.finished_at || null,
      database: "LOCAL / SQLITE",
    };
    database.close();
    return status;
  } catch {
    return {
      markets: 0,
      observations: 0,
      results: 0,
      earliest_timestamp: null,
      latest_timestamp: null,
      last_import: null,
      database: "LOCAL / EMPTY",
    };
  }
}

function databaseObservations(url) {
  try {
    const database = new DatabaseSync(databasePath, { readOnly: true });
    const limit = Math.min(Number(url.searchParams.get("limit") || 500), 5000);
    const rows = database
      .prepare(
        "SELECT ticker, timestamp, yes_price, no_price, yes_bid, yes_ask, volume, open_interest FROM market_observations ORDER BY timestamp LIMIT ?",
      )
      .all(limit);
    database.close();
    return rows.map((row) => {
      try {
        const signal = calculateTimeTrak(row.timestamp);
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

function sendJson(response, payload) {
  response.writeHead(200, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(JSON.stringify(payload));
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url, `http://${request.headers.host}`);
  if (url.pathname === "/api/vault/status") {
    sendJson(response, databaseStatus());
    return;
  }
  if (url.pathname === "/api/vault/observations") {
    sendJson(response, databaseObservations(url));
    return;
  }
  if (url.pathname === "/api/astronomy") {
    try {
      const timestamp = url.searchParams.get("timestamp");
      const signal = calculateTimeTrak(
        timestamp,
        url.searchParams.get("objectA") || "Saturn",
        url.searchParams.get("objectB") || "Pluto",
      );
      sendJson(response, { ...signal, astronomyVersion: ASTRONOMY_VERSION });
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
});
