import type { RaceState, TrackState } from "../types/race";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function assertRaceState(value: unknown): RaceState {
  if (!isRecord(value) || !isRecord(value.session) || !Array.isArray(value.drivers) || !Array.isArray(value.predictions)) {
    throw new Error("Race state response did not match the expected shape.");
  }
  return value as RaceState;
}

function assertTrackState(value: unknown): TrackState {
  if (!isRecord(value) || !Array.isArray(value.path)) {
    throw new Error("Track response did not match the expected shape.");
  }
  return value as TrackState;
}

async function fetchJson<T>(path: string, parse: (value: unknown) => T): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return parse(await response.json());
}

export function fetchRaceState() {
  return fetchJson("/api/race-state", assertRaceState);
}

export function fetchTrack() {
  return fetchJson("/api/track", assertTrackState);
}