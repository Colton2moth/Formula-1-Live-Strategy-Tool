import type { ApiPrediction, RaceState, TrackState } from "../types/race";

export const apiBaseUrl: string = import.meta.env.VITE_API_BASE_URL ?? "";

export type ApiErrorType = "network" | "http" | "invalid-data" | "timeout" | "unknown";

export class ApiError extends Error {
  readonly type: ApiErrorType;
  readonly method: string | null;
  readonly path: string | null;
  readonly status: number | null;
  readonly statusText: string | null;
  readonly serverDetail: string | null;
  readonly timestamp: string;
  attempts: number;

  constructor(init: {
    type: ApiErrorType;
    message: string;
    method?: string | null;
    path?: string | null;
    status?: number | null;
    statusText?: string | null;
    serverDetail?: string | null;
    attempts?: number;
  }) {
    super(init.message);
    this.name = "ApiError";
    this.type = init.type;
    this.method = init.method ?? null;
    this.path = init.path ?? null;
    this.status = init.status ?? null;
    this.statusText = init.statusText ?? null;
    this.serverDetail = init.serverDetail ?? null;
    this.timestamp = new Date().toISOString();
    this.attempts = init.attempts ?? 1;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function toApiError(error: unknown): ApiError {
  if (isApiError(error)) return error;
  const message = error instanceof Error ? error.message : "Unable to load race data.";
  return new ApiError({ type: "unknown", message });
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
  if (!isRecord(value) || !Array.isArray(value.display_path)) {
    throw new Error("Track response did not match the expected shape.");
  }
  return value as TrackState;
}

function assertTracks(value: unknown): TrackState[] {
  if (!Array.isArray(value)) {
    throw new Error("Tracks response did not match the expected shape.");
  }
  return value as TrackState[];
}

function assertPrediction(value: unknown): ApiPrediction {
  if (!isRecord(value) || typeof value.driver_number !== "number") {
    throw new Error("Prediction response did not match the expected shape.");
  }
  return value as ApiPrediction;
}

const MAX_ERROR_TEXT_LENGTH = 300;

function limitLength(text: string): string {
  return text.length <= MAX_ERROR_TEXT_LENGTH ? text : `${text.slice(0, MAX_ERROR_TEXT_LENGTH)}…`;
}

function normalizeErrorText(text: string): string {
  const collapsed = text
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return limitLength(collapsed);
}

function readJsonDetail(text: string): string | null {
  try {
    const parsed: unknown = JSON.parse(text);
    if (!isRecord(parsed)) {
      return null;
    }
    if (typeof parsed.detail === "string" && parsed.detail.trim()) {
      return limitLength(parsed.detail.trim());
    }
    if (typeof parsed.message === "string" && parsed.message.trim()) {
      return limitLength(parsed.message.trim());
    }
    return null;
  } catch {
    return null;
  }
}

async function readErrorDetail(response: Response): Promise<string | null> {
  let text: string;
  try {
    text = await response.text();
  } catch {
    return null;
  }
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }
  return readJsonDetail(trimmed) ?? normalizeErrorText(trimmed);
}

async function requestJson<T>(
  method: string,
  path: string,
  body: unknown,
  parse: (value: unknown) => T,
): Promise<T> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, init);
  } catch (error) {
    throw new ApiError({
      type: "network",
      method,
      path,
      message: error instanceof Error ? error.message : "Network request failed.",
    });
  }

  if (!response.ok) {
    throw new ApiError({
      type: "http",
      method,
      path,
      message: `Request failed: ${response.status}`,
      status: response.status,
      statusText: response.statusText,
      serverDetail: await readErrorDetail(response),
    });
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new ApiError({
      type: "invalid-data",
      method,
      path,
      message: "Response body was not valid JSON.",
      status: response.status,
      statusText: response.statusText,
    });
  }

  try {
    return parse(data);
  } catch (error) {
    throw new ApiError({
      type: "invalid-data",
      method,
      path,
      message: error instanceof Error ? error.message : "Response did not match the expected shape.",
      status: response.status,
      statusText: response.statusText,
    });
  }
}

export async function fetchJson<T>(path: string, parse: (value: unknown) => T): Promise<T> {
  return requestJson("GET", path, undefined, parse);
}

export async function postJson<T>(path: string, body: unknown, parse: (value: unknown) => T): Promise<T> {
  return requestJson("POST", path, body, parse);
}

export function fetchRaceState() {
  return fetchJson("/api/race-state", assertRaceState);
}

export function fetchReplayRaceState(replayId: string) {
  return fetchJson(`/api/replays/${replayId}/race-state`, assertRaceState);
}

export function fetchTrack() {
  return fetchJson("/api/track", assertTrackState);
}

export function fetchReplayTrack(replayId: string) {
  return fetchJson(`/api/replays/${replayId}/track`, assertTrackState);
}

export function fetchTracks() {
  return fetchJson("/api/tracks", assertTracks);
}

export function fetchDriverPrediction(driverNumber: number) {
  return fetchJson(`/api/drivers/${driverNumber}/prediction`, assertPrediction);
}
