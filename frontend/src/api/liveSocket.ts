import type { ApiCompoundProbabilities, TrackRoute } from "../types/race";
import { apiBaseUrl } from "./raceState";

export type LocationUpdate = {
  type: "location_update";
  driver_number: number;
  x: number | null;
  y: number | null;
  progress: number | null;
  route: TrackRoute;
  pit_lane_progress: number | null;
  timestamp: string | null;
};

export type DriverUpdate = {
  type: "driver_update";
  driver_number: number;
  position: number;
  current_lap: number;
  compound: string;
  tyre_age: number;
  last_lap_time: number;
  gap_to_leader: number | string | null;
  interval_ahead: number | null;
  interval_behind: number | null;
  pit_stops: number;
};

export type WeatherUpdate = {
  type: "weather_update";
  track_temperature: number | null;
  air_temperature: number | null;
  rainfall: boolean;
};

export type RaceControlUpdate = {
  type: "race_control_update";
  status: string;
  message: string;
};

export type PredictionUpdate = {
  type: "prediction_update";
  driver_number: number;
  lap_number: number;
  pit_within_3_laps: number;
  pit_within_5_laps: number;
  pit_within_7_laps: number;
  predicted_next_compound: string;
  compound_probabilities: ApiCompoundProbabilities | null;
};

export type LiveEvent =
  | LocationUpdate
  | DriverUpdate
  | WeatherUpdate
  | RaceControlUpdate
  | PredictionUpdate;

export type LiveSocketStatus = "connecting" | "open" | "reconnecting";

export type LiveSocketHandlers = {
  onEvent: (event: LiveEvent) => void;
  onStatus: (status: LiveSocketStatus) => void;
};

const MAX_RECONNECT_DELAY_MS = 8000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function toNullableNumber(value: unknown): number | null {
  return isNumber(value) ? value : null;
}

function toGap(value: unknown): number | string | null {
  if (isNumber(value)) return value;
  if (typeof value === "string") return value;
  if (value === null) return null;
  return "UNKNOWN";
}

function toProgress(value: unknown): number | null {
  if (!isNumber(value) || value < 0 || value >= 1) {
    return null;
  }
  return value;
}

function toPitLaneProgress(value: unknown): number | null {
  if (!isNumber(value) || value < 0 || value > 1) {
    return null;
  }
  return value;
}

function parseCompoundProbabilities(value: unknown): ApiCompoundProbabilities | null {
  if (value === null || !isRecord(value)) {
    return null;
  }
  const compounds = ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"] as const;
  for (const compound of compounds) {
    if (!isNumber(value[compound])) {
      return null;
    }
  }
  return value as unknown as ApiCompoundProbabilities;
}

function parseLocationUpdate(value: Record<string, unknown>): LocationUpdate | null {
  if (
    !isNumber(value.driver_number) ||
    (value.route !== "track" && value.route !== "pit_lane")
  ) {
    return null;
  }
  return {
    type: "location_update",
    driver_number: value.driver_number,
    x: isNumber(value.x) ? value.x : null,
    y: isNumber(value.y) ? value.y : null,
    progress: toProgress(value.progress),
    route: value.route,
    pit_lane_progress: toPitLaneProgress(value.pit_lane_progress),
    timestamp: typeof value.timestamp === "string" ? value.timestamp : null,
  };
}

function parseDriverUpdate(value: Record<string, unknown>): DriverUpdate | null {
  if (
    !isNumber(value.driver_number) ||
    !isNumber(value.position) ||
    !isNumber(value.tyre_age) ||
    !isNumber(value.last_lap_time)
  ) {
    return null;
  }
  return {
    type: "driver_update",
    driver_number: value.driver_number,
    position: value.position,
    current_lap: isNumber(value.current_lap) ? value.current_lap : 0,
    compound: typeof value.compound === "string" ? value.compound : "",
    tyre_age: value.tyre_age,
    last_lap_time: value.last_lap_time,
    gap_to_leader: toGap(value.gap_to_leader),
    interval_ahead: toNullableNumber(value.interval_ahead),
    interval_behind: toNullableNumber(value.interval_behind),
    pit_stops: isNumber(value.pit_stops) ? value.pit_stops : 0,
  };
}

function parseWeatherUpdate(value: Record<string, unknown>): WeatherUpdate | null {
  if (typeof value.rainfall !== "boolean") {
    return null;
  }
  return {
    type: "weather_update",
    track_temperature: isNumber(value.track_temperature) ? value.track_temperature : null,
    air_temperature: isNumber(value.air_temperature) ? value.air_temperature : null,
    rainfall: value.rainfall,
  };
}

function parseRaceControlUpdate(value: Record<string, unknown>): RaceControlUpdate | null {
  if (typeof value.status !== "string") {
    return null;
  }
  return {
    type: "race_control_update",
    status: value.status,
    message: typeof value.message === "string" ? value.message : "",
  };
}

function parsePredictionUpdate(value: Record<string, unknown>): PredictionUpdate | null {
  if (!isNumber(value.driver_number)) {
    return null;
  }
  return {
    type: "prediction_update",
    driver_number: value.driver_number,
    lap_number: isNumber(value.lap_number) ? value.lap_number : 0,
    pit_within_3_laps: isNumber(value.pit_within_3_laps) ? value.pit_within_3_laps : 0,
    pit_within_5_laps: isNumber(value.pit_within_5_laps) ? value.pit_within_5_laps : 0,
    pit_within_7_laps: isNumber(value.pit_within_7_laps) ? value.pit_within_7_laps : 0,
    predicted_next_compound:
      typeof value.predicted_next_compound === "string" ? value.predicted_next_compound : "UNKNOWN",
    compound_probabilities: parseCompoundProbabilities(value.compound_probabilities),
  };
}

export function parseLiveEvent(data: unknown): LiveEvent | null {
  if (typeof data !== "string") {
    return null;
  }
  let value: unknown;
  try {
    value = JSON.parse(data);
  } catch {
    return null;
  }
  if (!isRecord(value)) {
    return null;
  }
  switch (value.type) {
    case "location_update":
      return parseLocationUpdate(value);
    case "driver_update":
      return parseDriverUpdate(value);
    case "weather_update":
      return parseWeatherUpdate(value);
    case "race_control_update":
      return parseRaceControlUpdate(value);
    case "prediction_update":
      return parsePredictionUpdate(value);
    default:
      return null;
  }
}

export function socketUrl(path: string): string {
  const base = apiBaseUrl.trim();
  if (base) {
    try {
      const url = new URL(base);
      const protocol = url.protocol === "https:" ? "wss:" : "ws:";
      return `${protocol}//${url.host}${path}`;
    } catch {
      // Fall through to the same-origin dev proxy.
    }
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

export function openSocket(
  path: string,
  handlers: LiveSocketHandlers,
): { close: () => void } {
  let socket: WebSocket | null = null;
  let closed = false;
  let attempt = 0;
  let reconnectTimer: number | null = null;

  const clearReconnectTimer = () => {
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  const connect = () => {
    clearReconnectTimer();
    if (closed) {
      return;
    }
    socket = new WebSocket(socketUrl(path));

    socket.onopen = () => {
      attempt = 0;
      handlers.onStatus("open");
    };

    socket.onmessage = (message) => {
      const event = parseLiveEvent(message.data);
      if (event) {
        handlers.onEvent(event);
      }
    };

    socket.onerror = () => {
      socket?.close();
    };

    socket.onclose = () => {
      socket = null;
      if (closed) {
        return;
      }
      handlers.onStatus("reconnecting");
      const delay = Math.min(1000 * 2 ** attempt, MAX_RECONNECT_DELAY_MS);
      attempt += 1;
      reconnectTimer = window.setTimeout(connect, delay);
    };
  };

  connect();

  return {
    close() {
      closed = true;
      clearReconnectTimer();
      socket?.close();
      socket = null;
    },
  };
}
