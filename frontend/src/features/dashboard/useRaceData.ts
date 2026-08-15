import { useEffect, useState } from "react";
import { fetchRaceState, fetchTrack, isApiRequestError } from "../../api/raceState";
import type { RaceState, TrackState } from "../../types/race";

export type RaceDataErrorVariant = "unavailable" | "server-error" | "invalid-data";

export function classifyError(message: string): RaceDataErrorVariant {
  if (message.includes("Failed to fetch") || message.includes("NetworkError")) {
    return "unavailable";
  }
  if (message.startsWith("Request failed:")) {
    return "server-error";
  }
  if (message.includes("did not match the expected shape")) {
    return "invalid-data";
  }
  return "server-error";
}

export function useRaceData(reloadKey: number) {
  const [raceState, setRaceState] = useState<RaceState | null>(null);
  const [track, setTrack] = useState<TrackState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const retryDelay = (attempt: number) => Math.min(1000 * 2 ** attempt, 8000);

    async function load() {
      for (let attempt = 0; active; attempt += 1) {
        try {
          const [raceStateResponse, trackResponse] = await Promise.all([
            fetchRaceState(),
            fetchTrack(),
          ]);
          if (!active) return;
          setRaceState(raceStateResponse);
          setTrack(trackResponse);
          return;
        } catch (requestError: unknown) {
          if (!active) return;
          if (isApiRequestError(requestError) && requestError.status === 503) {
            await new Promise((resolve) => setTimeout(resolve, retryDelay(attempt)));
            continue;
          }
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Unable to load race data.",
          );
          return;
        }
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [reloadKey]);

  return { raceState, track, error };
}
