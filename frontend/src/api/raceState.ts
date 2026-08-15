import type { ApiPrediction, RaceState, TrackState } from "../types/race";

export const apiBaseUrl: string = import.meta.env.VITE_API_BASE_URL ?? "";

export interface ApiRequestError extends Error {
  status: number;
}

export function isApiRequestError(error: unknown): error is ApiRequestError {
  return error instanceof Error && typeof (error as ApiRequestError).status === "number";
}

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

function assertPrediction(value: unknown): ApiPrediction {
  if (!isRecord(value) || typeof value.driver_number !== "number") {
    throw new Error("Prediction response did not match the expected shape.");
  }
  return value as ApiPrediction;
}

export async function fetchJson<T>(path: string, parse: (value: unknown) => T): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`);
  if (!response.ok) {
    throw Object.assign(new Error(`Request failed: ${response.status}`), {
      status: response.status,
    });
  }
  return parse(await response.json());
}

export async function postJson<T>(path: string, body: unknown, parse: (value: unknown) => T): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw Object.assign(new Error(`Request failed: ${response.status}`), {
      status: response.status,
    });
  }
  return parse(await response.json());
}

export function fetchRaceState() {
  return fetchJson("/api/race-state", assertRaceState);
}

export function fetchTrack() {
  return fetchJson("/api/track", assertTrackState);
}

export function fetchDriverPrediction(driverNumber: number) {
  return fetchJson(`/api/drivers/${driverNumber}/prediction`, assertPrediction);
}