import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const sweph = require("sweph");
const PLANETS = {
  Sun: 0,
  Moon: 1,
  Mercury: 2,
  Venus: 3,
  Mars: 4,
  Jupiter: 5,
  Saturn: 6,
  Uranus: 7,
  Neptune: 8,
  Pluto: 9,
};
export const ASTRONOMY_VERSION = "swiss-ephemeris-sweph-2.10.3-8";
export const TIMETRAK_VERSION = "TimeTrak_Experimental_Swiss_v0";

export function toJulianDay(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime()))
    throw new Error(`Invalid timestamp: ${timestamp}`);
  const year = date.getUTCFullYear();
  const month = date.getUTCMonth() + 1;
  const day = date.getUTCDate();
  const hour =
    date.getUTCHours() +
    date.getUTCMinutes() / 60 +
    date.getUTCSeconds() / 3600;
  const a = Math.floor((14 - month) / 12);
  const y = year + 4800 - a;
  const m = month + 12 * a - 3;
  const jdn =
    day +
    Math.floor((153 * m + 2) / 5) +
    365 * y +
    Math.floor(y / 4) -
    Math.floor(y / 100) +
    Math.floor(y / 400) -
    32045;
  return jdn + (hour - 12) / 24;
}

export function calculatePlanetPositions(timestamp) {
  const julianDay = toJulianDay(timestamp);
  const flag =
    (sweph.constants?.SEFLG_SWIEPH || 2) |
    (sweph.constants?.SEFLG_SPEED || 256);
  return Object.fromEntries(
    Object.entries(PLANETS).map(([name, planet]) => {
      const result = sweph.calc_ut(julianDay, planet, flag);
      if (result.error && result.flag < 0)
        throw new Error(`Swiss Ephemeris failed for ${name}: ${result.error}`);
      return [
        name,
        {
          longitude: result.data?.[0] || 0,
          latitude: result.data?.[1] || 0,
          distance: result.data?.[2] || 0,
          speedLongitude: result.data?.[5] || 0,
        },
      ];
    }),
  );
}

function separation(first, second) {
  const distance = Math.abs(first - second) % 360;
  return Math.min(distance, 360 - distance);
}

const ASPECTS = [
  [0, "conjunction"],
  [60, "sextile"],
  [90, "square"],
  [120, "trine"],
  [180, "opposition"],
];

export function calculateTimeTrak(
  timestamp,
  objectA = "Saturn",
  objectB = "Pluto",
  maxOrb = 8,
) {
  const positions = calculatePlanetPositions(timestamp);
  const distance = separation(
    positions[objectA].longitude,
    positions[objectB].longitude,
  );
  const [target, aspect] = ASPECTS.reduce((best, candidate) =>
    Math.abs(distance - candidate[0]) < Math.abs(distance - best[0])
      ? candidate
      : best,
  );
  const orb = Math.abs(distance - target);
  const intensity =
    Math.round(Math.max(0, Math.min(100, (1 - orb / maxOrb) * 100)) * 100) /
    100;
  const durationHours = Math.round(Math.max(1, (maxOrb - orb) * 6) * 100) / 100;
  const peak = new Date(timestamp);
  const onset = new Date(peak.getTime() - durationHours * 30 * 60 * 1000);
  return {
    timestamp: peak.toISOString(),
    objectA,
    objectB,
    aspect,
    orb: Math.round(orb * 10000) / 10000,
    direction: orb < maxOrb / 2 ? "applying" : "separating",
    intensity,
    onset: onset.toISOString(),
    peak: peak.toISOString(),
    durationHours,
    positions,
    astronomyVersion: ASTRONOMY_VERSION,
    calculationVersion: TIMETRAK_VERSION,
  };
}
