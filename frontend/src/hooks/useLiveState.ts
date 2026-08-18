import { useEffect, useMemo, useRef, useState } from "react";
import { openSocket } from "../api/liveSocket";
import type { LiveEvent, LiveSocketStatus } from "../api/liveSocket";
import {
  fetchRaceState,
  fetchReplayRaceState,
  fetchReplayTrack,
  fetchTrack,
} from "../api/raceState";
import type { ApiDriver, ApiPrediction, ApiSession, RaceState, TrackState } from "../types/race";

export type DriverLocation = { x: number; y: number };

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

export const replaySource: DashboardSource = {
  socketPath: "/ws/replay",
  fetchRaceState: fetchReplayRaceState,
  fetchTrack: fetchReplayTrack,
};

export type RaceStreamResult = {
  status: LiveSocketStatus;
  session: ApiSession | null;
  drivers: ApiDriver[];
  predictions: ReadonlyMap<number, ApiPrediction>;
  locations: ReadonlyMap<number, DriverLocation>;
};

function toPredictionMap(snapshot: RaceState | null): ReadonlyMap<number, ApiPrediction> {
  return new Map((snapshot?.predictions ?? []).map((prediction) => [prediction.driver_number, prediction]));
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
  const [seededSnapshot, setSeededSnapshot] = useState(snapshot);

  if (snapshot !== seededSnapshot) {
    setSeededSnapshot(snapshot);
    if (snapshot) {
      setSession(snapshot.session);
      setDrivers(snapshot.drivers);
      setPredictions(toPredictionMap(snapshot));
      setLocations(new Map());
    }
  }

  const hasConnectedRef = useRef(false);

  useEffect(() => {
    if (!snapshot) {
      return;
    }

    const applyEvent = (event: LiveEvent) => {
      switch (event.type) {
        case "location_update": {
          setLocations((prev) => {
            if (event.x === null || event.y === null) {
              if (!prev.has(event.driver_number)) {
                return prev;
              }
              const next = new Map(prev);
              next.delete(event.driver_number);
              return next;
            }
            const next = new Map(prev);
            next.set(event.driver_number, { x: event.x, y: event.y });
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

    const recoverSnapshot = async () => {
      try {
        const fresh = await source.fetchRaceState();
        setSession(fresh.session);
        setDrivers(fresh.drivers);
        setPredictions(toPredictionMap(fresh));
        setLocations(new Map());
      } catch {
        // Keep the last valid data visible until the next reconnect.
      }
    };

    const socket = openSocket(source.socketPath, {
      onEvent: applyEvent,
      onStatus: (next) => {
        setStatus(next);
        if (next === "open") {
          if (hasConnectedRef.current) {
            void recoverSnapshot();
          } else {
            hasConnectedRef.current = true;
          }
        }
      },
    });

    return () => {
      hasConnectedRef.current = false;
      socket.close();
    };
  }, [snapshot, source]);

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

  return { status, session: liveSession, drivers, predictions, locations };
}
