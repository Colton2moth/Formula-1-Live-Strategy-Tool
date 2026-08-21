import { useEffect, useState } from "react";
import { isApiError, toApiError } from "../../api/raceState";
import type { ApiError } from "../../api/raceState";
import { liveSource } from "../../hooks/useLiveState";
import type { DashboardSource } from "../../hooks/useLiveState";
import { ACTIVITY_IDS, ACTIVITY_MESSAGES, useActivity } from "../activity/useActivity";
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

export function useRaceData(
  reloadKey: number,
  source: DashboardSource | null = liveSource,
  reportActivity = true,
) {
  const [raceState, setRaceState] = useState<RaceState | null>(null);
  const [track, setTrack] = useState<TrackState | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const activity = useActivity();

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
      if (reportActivity) {
        activity.set(ACTIVITY_IDS.track, ACTIVITY_MESSAGES.track);
      }
      try {
        const trackResponse = await activeSource.fetchTrack();
        if (active) setTrack(trackResponse);
      } catch {
        // A missing track map must not block the rest of the dashboard.
        if (active) setTrack(null);
      } finally {
        if (active && reportActivity) {
          activity.clear(ACTIVITY_IDS.track);
        }
      }
    }

    async function load() {
      // Track loads in parallel with race-state so both operations are visible
      // from the start; a missing track map never blocks the dashboard.
      const trackRequest = loadTrack();

      for (let attempt = 0; active; attempt += 1) {
        if (reportActivity) {
          activity.set(ACTIVITY_IDS.raceState, ACTIVITY_MESSAGES.raceState);
        }
        try {
          const raceStateResponse = await activeSource.fetchRaceState();
          if (!active) return;
          setRaceState(raceStateResponse);
          setError(null);
          if (reportActivity) {
            activity.clear(ACTIVITY_IDS.raceState);
          }
          await trackRequest;
          return;
        } catch (requestError: unknown) {
          if (!active) return;
          if (reportActivity) {
            activity.clear(ACTIVITY_IDS.raceState);
          }
          const apiError = toApiError(requestError);
          if (apiError.status !== null && RETRYABLE_STATUSES.has(apiError.status)) {
            if (reportActivity) {
              activity.set(ACTIVITY_IDS.retryRaceState, ACTIVITY_MESSAGES.retryRaceState, "amber");
            }
            await new Promise((resolve) => setTimeout(resolve, retryDelay(attempt)));
            if (!active) return;
            if (reportActivity) {
              activity.clear(ACTIVITY_IDS.retryRaceState);
            }
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
      if (reportActivity) {
        activity.clear(ACTIVITY_IDS.raceState);
        activity.clear(ACTIVITY_IDS.track);
        activity.clear(ACTIVITY_IDS.retryRaceState);
      }
    };
  }, [reloadKey, source, activity, reportActivity]);

  return { raceState, track, error };
}
