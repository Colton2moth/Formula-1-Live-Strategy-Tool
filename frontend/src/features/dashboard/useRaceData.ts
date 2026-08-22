import { useEffect, useState } from "react";
import { isApiError, toApiError } from "../../api/raceState";
import type { ApiError } from "../../api/raceState";
import { liveSource } from "../../hooks/useLiveState";
import type { DashboardSource } from "../../hooks/useLiveState";
import { ACTIVITY_IDS, ACTIVITY_MESSAGES, useActivity } from "../activity/useActivity";
import type { RaceState, TrackState } from "../../types/race";

export type RaceDataErrorVariant = "unavailable" | "server-error" | "invalid-data" | "timeout";

export type ResourceStatus = "loading" | "ready" | "error";

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

const MAX_RETRY_DELAY_MS = 8000;

function retryDelay(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, MAX_RETRY_DELAY_MS);
}

export function useRaceData(
  reloadKey: number,
  source: DashboardSource | null = liveSource,
  reportActivity = true,
) {
  const [raceState, setRaceState] = useState<RaceState | null>(null);
  const [track, setTrack] = useState<TrackState | null>(null);
  const [raceStateStatus, setRaceStateStatus] = useState<ResourceStatus>("loading");
  const [trackStatus, setTrackStatus] = useState<ResourceStatus>("loading");
  const [raceStateError, setRaceStateError] = useState<ApiError | null>(null);
  const [trackError, setTrackError] = useState<ApiError | null>(null);
  const activity = useActivity();

  useEffect(() => {
    if (!source) {
      setRaceState(null);
      setTrack(null);
      setRaceStateStatus("loading");
      setTrackStatus("loading");
      setRaceStateError(null);
      setTrackError(null);
      return;
    }

    const activeSource = source;
    let active = true;

    // Keep previously successful data visible while a reload is in flight, but
    // reset the resource to loading so callers can distinguish "refreshing"
    // from "settled".
    setRaceStateStatus("loading");
    setTrackStatus("loading");
    setRaceStateError(null);
    setTrackError(null);

    async function loadRaceState() {
      for (let attempt = 0; active; attempt += 1) {
        if (reportActivity) {
          activity.set(ACTIVITY_IDS.raceState, ACTIVITY_MESSAGES.raceState);
        }
        try {
          const response = await activeSource.fetchRaceState();
          if (!active) return;
          setRaceState(response);
          setRaceStateStatus("ready");
          setRaceStateError(null);
          if (reportActivity) {
            activity.clear(ACTIVITY_IDS.raceState);
          }
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
          setRaceStateStatus("error");
          setRaceStateError(apiError);
          return;
        }
      }
    }

    async function loadTrack() {
      for (let attempt = 0; active; attempt += 1) {
        if (reportActivity) {
          activity.set(ACTIVITY_IDS.track, ACTIVITY_MESSAGES.track);
        }
        try {
          const response = await activeSource.fetchTrack();
          if (!active) return;
          setTrack(response);
          setTrackStatus("ready");
          setTrackError(null);
          if (reportActivity) {
            activity.clear(ACTIVITY_IDS.track);
          }
          return;
        } catch (requestError: unknown) {
          if (!active) return;
          if (reportActivity) {
            activity.clear(ACTIVITY_IDS.track);
          }
          const apiError = toApiError(requestError);
          if (apiError.status !== null && RETRYABLE_STATUSES.has(apiError.status)) {
            if (reportActivity) {
              activity.set(ACTIVITY_IDS.retryTrack, ACTIVITY_MESSAGES.retryTrack, "amber");
            }
            await new Promise((resolve) => setTimeout(resolve, retryDelay(attempt)));
            if (!active) return;
            if (reportActivity) {
              activity.clear(ACTIVITY_IDS.retryTrack);
            }
            continue;
          }
          apiError.attempts = attempt + 1;
          setTrackStatus("error");
          setTrackError(apiError);
          return;
        }
      }
    }

    void loadRaceState();
    void loadTrack();

    return () => {
      active = false;
      if (reportActivity) {
        activity.clear(ACTIVITY_IDS.raceState);
        activity.clear(ACTIVITY_IDS.track);
        activity.clear(ACTIVITY_IDS.retryRaceState);
        activity.clear(ACTIVITY_IDS.retryTrack);
      }
    };
  }, [reloadKey, source, activity, reportActivity]);

  return { raceState, track, raceStateStatus, trackStatus, raceStateError, trackError };
}
