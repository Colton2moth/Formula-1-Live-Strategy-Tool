import { useEffect, useState } from "react";
import { isApiError, toApiError } from "../../api/raceState";
import type { ApiError } from "../../api/raceState";
import { liveSource } from "../../hooks/useLiveState";
import type { DashboardSource } from "../../hooks/useLiveState";
import type { RaceState, TrackState } from "../../types/race";

export type RaceDataErrorVariant = "unavailable" | "server-error" | "invalid-data" | "timeout";

export function classifyError(error: unknown): RaceDataErrorVariant {
  if (isApiError(error)) {
    switch (error.type) {
      case "network":
        return "unavailable";
      case "invalid-data":
        return "invalid-data";
      case "timeout":
        return "timeout";
      case "http":
      case "unknown":
      default:
        return "server-error";
    }
  }
  if (error instanceof Error) {
    if (error.message.includes("Failed to fetch") || error.message.includes("NetworkError")) {
      return "unavailable";
    }
    if (error.message.includes("did not match the expected shape")) {
      return "invalid-data";
    }
  }
  return "server-error";
}

// 503 = no live session yet; 409 = no replay started yet. Both mean "data not
// available right now", so keep polling until the source is seeded.
const RETRYABLE_STATUSES = new Set([503, 409]);

export function useRaceData(reloadKey: number, source: DashboardSource | null = liveSource) {
  const [raceState, setRaceState] = useState<RaceState | null>(null);
  const [track, setTrack] = useState<TrackState | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    if (!source) {
      setRaceState(null);
      setTrack(null);
      setError(null);
      return;
    }

    const activeSource = source;
    let active = true;

    const retryDelay = (attempt: number) => Math.min(1000 * 2 ** attempt, 8000);

    async function loadTrack() {
      try {
        const trackResponse = await activeSource.fetchTrack();
        if (active) setTrack(trackResponse);
      } catch {
        // A missing track map must not block the rest of the dashboard.
        if (active) setTrack(null);
      }
    }

    async function load() {
      for (let attempt = 0; active; attempt += 1) {
        try {
          const raceStateResponse = await activeSource.fetchRaceState();
          if (!active) return;
          setRaceState(raceStateResponse);
          setError(null);
          await loadTrack();
          return;
        } catch (requestError: unknown) {
          if (!active) return;
          const apiError = toApiError(requestError);
          if (apiError.status !== null && RETRYABLE_STATUSES.has(apiError.status)) {
            await new Promise((resolve) => setTimeout(resolve, retryDelay(attempt)));
            continue;
          }
          apiError.attempts = attempt + 1;
          setError(apiError);
          return;
        }
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [reloadKey, source]);

  return { raceState, track, error };
}
