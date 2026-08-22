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

export type ReplayCreated = ReplayStatus & {
  replay_id: string;
};

export type ReplayReadiness =
  | "ready"
  | "partial"
  | "cancelled"
  | "not_ready"
  | "failed"
  | "unknown";

export type ReplaySessionOption = {
  session_key: number;
  year: number;
  country_name: string | null;
  location: string | null;
  circuit_short_name: string | null;
  date_start: string | null;
  readiness: ReplayReadiness;
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

function assertReplayCreated(value: unknown): ReplayCreated {
  if (!isRecord(value) || typeof value.replay_id !== "string") {
    throw new Error("Replay create response did not match the expected shape.");
  }
  return { ...assertReplayStatus(value), replay_id: value.replay_id };
}

function assertReplaySessions(value: unknown): ReplaySessionOption[] {
  if (!Array.isArray(value)) {
    throw new Error("Replay sessions response did not match the expected shape.");
  }
  return value.map((session) => {
    if (!isRecord(session)) {
      throw new Error("Replay sessions response did not match the expected shape.");
    }
    const readiness =
      session.readiness === "ready" ||
      session.readiness === "partial" ||
      session.readiness === "cancelled" ||
      session.readiness === "not_ready" ||
      session.readiness === "failed"
        ? session.readiness
        : "unknown";
    return {
      session_key: session.session_key as number,
      year: session.year as number,
      country_name: typeof session.country_name === "string" ? session.country_name : null,
      location: typeof session.location === "string" ? session.location : null,
      circuit_short_name:
        typeof session.circuit_short_name === "string" ? session.circuit_short_name : null,
      date_start: typeof session.date_start === "string" ? session.date_start : null,
      readiness,
    };
  });
}

export function fetchReplaySessions() {
  return fetchJson("/api/replay/sessions", assertReplaySessions);
}

export function createReplay(sessionKey: number, speed: number) {
  return postJson("/api/replays", { session_key: sessionKey, speed }, assertReplayCreated);
}

export function fetchReplayStatus(replayId: string) {
  return fetchJson(`/api/replays/${replayId}/status`, assertReplayStatus);
}

export function pauseReplay(replayId: string) {
  return postJson(`/api/replays/${replayId}/pause`, {}, assertReplayStatus);
}

export function seekReplay(replayId: string, time: number) {
  return postJson(`/api/replays/${replayId}/seek`, { time }, assertReplayStatus);
}

export function seekReplayLap(replayId: string, lap: number) {
  return postJson(`/api/replays/${replayId}/seek`, { lap }, assertReplayStatus);
}

export function setReplaySpeed(replayId: string, speed: number) {
  return postJson(`/api/replays/${replayId}/speed`, { speed }, assertReplayStatus);
}

export function resumeReplay(replayId: string) {
  return postJson(`/api/replays/${replayId}/resume`, {}, assertReplayStatus);
}

export function stopReplay(replayId: string) {
  return postJson(`/api/replays/${replayId}/stop`, {}, assertReplayStatus);
}
