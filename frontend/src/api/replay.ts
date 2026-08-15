import { fetchJson, postJson } from "./raceState";

export type ReplayStatusValue =
  | "idle"
  | "downloading"
  | "running"
  | "paused"
  | "finished"
  | "error";

export type ReplayStatus = {
  status: ReplayStatusValue;
  running: boolean;
  session_key: number | null;
  speed: number | null;
  error: string | null;
  current_time: number | null;
  total_duration: number | null;
  current_lap: number | null;
  total_laps: number | null;
};

export type ReplaySessionOption = {
  session_key: number;
  year: number;
  country_name: string | null;
  location: string | null;
  circuit_short_name: string | null;
  date_start: string | null;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toNullableNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function assertReplayStatus(value: unknown): ReplayStatus {
  if (!isRecord(value) || typeof value.status !== "string" || typeof value.running !== "boolean") {
    throw new Error("Replay status response did not match the expected shape.");
  }
  return {
    status: value.status as ReplayStatusValue,
    running: value.running,
    session_key: typeof value.session_key === "number" ? value.session_key : null,
    speed: toNullableNumber(value.speed),
    error: typeof value.error === "string" ? value.error : null,
    current_time: toNullableNumber(value.current_time),
    total_duration: toNullableNumber(value.total_duration),
    current_lap: toNullableNumber(value.current_lap),
    total_laps: toNullableNumber(value.total_laps),
  };
}

function assertReplaySessions(value: unknown): ReplaySessionOption[] {
  if (!Array.isArray(value)) {
    throw new Error("Replay sessions response did not match the expected shape.");
  }
  return value as ReplaySessionOption[];
}

export function fetchReplaySessions() {
  return fetchJson("/api/replay/sessions", assertReplaySessions);
}

export function fetchReplayStatus() {
  return fetchJson("/api/replay/status", assertReplayStatus);
}

export function startReplay(sessionKey: number, speed: number) {
  return postJson("/api/replay/start", { session_key: sessionKey, speed }, assertReplayStatus);
}

export function pauseReplay() {
  return postJson("/api/replay/pause", {}, assertReplayStatus);
}

export function seekReplay(lap: number) {
  return postJson("/api/replay/seek", { lap }, assertReplayStatus);
}

export function resumeReplay() {
  return postJson("/api/replay/resume", {}, assertReplayStatus);
}

export function stopReplay() {
  return postJson("/api/replay/stop", {}, assertReplayStatus);
}
