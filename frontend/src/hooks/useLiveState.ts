import { useEffect, useMemo, useRef, useState } from "react";
import { openSocket } from "../api/liveSocket";
import type { LiveEvent, LiveSocketStatus } from "../api/liveSocket";
import {
  fetchRaceState,
  fetchReplayRaceState,
  fetchReplayTrack,
  fetchTrack,
} from "../api/raceState";
import { ACTIVITY_IDS, ACTIVITY_MESSAGES, useActivity } from "../features/activity/useActivity";
import type { ApiDriver, ApiPrediction, ApiSession, RaceState, TrackState } from "../types/race";

export type DriverLocation = { map_x: number; map_y: number };

export type DashboardSource = {
  socketPath: string;
  fetchRaceState: () => Promise<RaceState>;
  fetchTrack: () => Promise<TrackState>;
};

export const liveSource: DashboardSource = {
  socketPath: "/ws/live",
  fetchRaceState,
  fetchTrack,
};

export function replaySourceFor(replayId: string): DashboardSource {
  return {
    socketPath: `/ws/replays/${replayId}`,
    fetchRaceState: () => fetchReplayRaceState(replayId),
    fetchTrack: () => fetchReplayTrack(replayId),
  };
}

export type RaceStreamResult = {
  status: LiveSocketStatus;
  session: ApiSession | null;
  drivers: ApiDriver[];
  predictions: ReadonlyMap<number, ApiPrediction>;
  locations: ReadonlyMap<number, DriverLocation>;
  refreshing: boolean;
  stale: boolean;
};

function toPredictionMap(snapshot: RaceState | null): ReadonlyMap<number, ApiPrediction> {
  return new Map((snapshot?.predictions ?? []).map((prediction) => [prediction.driver_number, prediction]));
}

const MAX_RECOVERY_DELAY_MS = 8000;

function recoveryDelay(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, MAX_RECOVERY_DELAY_MS);
}

export function useRaceStream(
  snapshot: RaceState | null,
  source: DashboardSource,
): RaceStreamResult {
  const [session, setSession] = useState<ApiSession | null>(snapshot?.session ?? null);
  const [drivers, setDrivers] = useState<ApiDriver[]>(snapshot?.drivers ?? []);
  const [predictions, setPredictions] = useState<ReadonlyMap<number, ApiPrediction>>(() => toPredictionMap(snapshot));
  const [locations, setLocations] = useState<ReadonlyMap<number, DriverLocation>>(() => new Map());
  const [status, setStatus] = useState<LiveSocketStatus>("connecting");
  const [refreshing, setRefreshing] = useState(false);
  const [stale, setStale] = useState(false);
  const [seededSnapshot, setSeededSnapshot] = useState(snapshot);
  const activity = useActivity();

  if (snapshot !== seededSnapshot) {
    setSeededSnapshot(snapshot);
    if (snapshot) {
      setSession(snapshot.session);
      setDrivers(snapshot.drivers);
      setPredictions(toPredictionMap(snapshot));
      setLocations(new Map());
      setStale(false);
    }
  }

  const hasConnectedRef = useRef(false);
  const recoveryTimerRef = useRef<number | null>(null);
  const recoveryAttemptRef = useRef(0);
  const recoveryGenerationRef = useRef(0);

  useEffect(() => {
    if (!snapshot) {
      return;
    }

    const applyEvent = (event: LiveEvent) => {
      switch (event.type) {
        case "location_update": {
          setLocations((prev) => {
            if (event.map_x === null || event.map_y === null) {
              if (!prev.has(event.driver_number)) {
                return prev;
              }
              const next = new Map(prev);
              next.delete(event.driver_number);
              return next;
            }
            const next = new Map(prev);
            next.set(event.driver_number, { map_x: event.map_x, map_y: event.map_y });
            return next;
          });
          break;
        }
        case "driver_update": {
          setDrivers((prev) =>
            prev.map((driver) =>
              driver.driver_number === event.driver_number
                ? {
                    ...driver,
                    position: event.position,
                    current_lap: event.current_lap,
                    compound: event.compound,
                    tyre_age: event.tyre_age,
                    last_lap_time: event.last_lap_time,
                    gap_to_leader: event.gap_to_leader,
                    interval_ahead: event.interval_ahead,
                    interval_behind: event.interval_behind,
                    pit_stops: event.pit_stops,
                  }
                : driver,
            ),
          );
          break;
        }
        case "weather_update": {
          setSession((prev) =>
            prev
              ? {
                  ...prev,
                  track_temperature: event.track_temperature ?? prev.track_temperature,
                  air_temperature: event.air_temperature ?? prev.air_temperature,
                  rainfall: event.rainfall,
                }
              : prev,
          );
          break;
        }
        case "race_control_update": {
          setSession((prev) => (prev ? { ...prev, race_control_status: event.status } : prev));
          break;
        }
        case "prediction_update": {
          setPredictions((prev) => {
            const next = new Map(prev);
            next.set(event.driver_number, {
              driver_number: event.driver_number,
              pit_within_3_laps: event.pit_within_3_laps,
              pit_within_5_laps: event.pit_within_5_laps,
              pit_within_7_laps: event.pit_within_7_laps,
              predicted_next_compound: event.predicted_next_compound,
              compound_probabilities: event.compound_probabilities,
              updated_at: new Date().toISOString(),
            });
            return next;
          });
          break;
        }
      }
    };

    const clearRecoveryTimer = () => {
      if (recoveryTimerRef.current !== null) {
        window.clearTimeout(recoveryTimerRef.current);
        recoveryTimerRef.current = null;
      }
    };

    const recoverSnapshot = async () => {
      const generation = ++recoveryGenerationRef.current;
      setRefreshing(true);
      activity.set(ACTIVITY_IDS.snapshotRefresh, ACTIVITY_MESSAGES.snapshotRefresh);
      try {
        const fresh = await source.fetchRaceState();
        // Ignore stale fetches — WS events may have arrived while we waited.
        if (generation !== recoveryGenerationRef.current) {
          return;
        }
        setSession(fresh.session);
        setDrivers(fresh.drivers);
        setPredictions(toPredictionMap(fresh));
        // Keep live map positions; clearing here caused cars to vanish on reconnect.
        setStale(false);
        recoveryAttemptRef.current = 0;
        activity.clear(ACTIVITY_IDS.snapshotRefresh);
      } catch {
        // Keep the last valid data visible, but mark it stale and retry the
        // REST resync with capped backoff until it succeeds or the socket
        // reconnects again.
        setStale(true);
        recoveryAttemptRef.current += 1;
        activity.set(ACTIVITY_IDS.snapshotRefresh, ACTIVITY_MESSAGES.snapshotStale, "amber");
        recoveryTimerRef.current = window.setTimeout(
          () => void recoverSnapshot(),
          recoveryDelay(recoveryAttemptRef.current - 1),
        );
      } finally {
        setRefreshing(false);
      }
    };

    activity.set(ACTIVITY_IDS.socket, ACTIVITY_MESSAGES.socketConnecting);

    const socket = openSocket(source.socketPath, {
      onEvent: applyEvent,
      onStatus: (next) => {
        setStatus(next);
        if (next === "open") {
          activity.clear(ACTIVITY_IDS.socket);
          if (hasConnectedRef.current) {
            clearRecoveryTimer();
            recoveryAttemptRef.current = 0;
            void recoverSnapshot();
          } else {
            hasConnectedRef.current = true;
          }
        } else if (next === "reconnecting") {
          clearRecoveryTimer();
          activity.set(ACTIVITY_IDS.socket, ACTIVITY_MESSAGES.socketReconnecting, "amber");
        }
      },
    });

    return () => {
      hasConnectedRef.current = false;
      clearRecoveryTimer();
      socket.close();
      activity.clear(ACTIVITY_IDS.socket);
      activity.clear(ACTIVITY_IDS.snapshotRefresh);
    };
  }, [snapshot, source, activity]);

  const liveSession = useMemo<ApiSession | null>(() => {
    if (!session) {
      return null;
    }
    const liveLap = drivers.reduce((max, driver) => Math.max(max, driver.current_lap), 0);
    if (liveLap <= session.current_lap) {
      return session;
    }
    return { ...session, current_lap: liveLap };
  }, [session, drivers]);

  return { status, session: liveSession, drivers, predictions, locations, refreshing, stale };
}
