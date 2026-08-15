import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchReplaySessions,
  fetchReplayStatus,
  pauseReplay,
  resumeReplay,
  seekReplay,
  startReplay,
  stopReplay,
} from "../../api/replay";
import type { ReplaySessionOption, ReplayStatusValue } from "../../api/replay";

export const SPEED_OPTIONS = [
  { value: "1", label: "1×" },
  { value: "2", label: "2×" },
  { value: "5", label: "5×" },
  { value: "10", label: "10×" },
  { value: "20", label: "20×" },
] as const;

export type ReplaySpeedValue = (typeof SPEED_OPTIONS)[number]["value"];

function defaultSpeed(): ReplaySpeedValue {
  const env = import.meta.env.VITE_REPLAY_SPEED;
  const found = SPEED_OPTIONS.find((option) => option.value === String(env));
  return found ? found.value : "10";
}

export type ReplayProgress = {
  currentTime: number | null;
  totalDuration: number | null;
  currentLap: number | null;
  totalLaps: number | null;
};

const EMPTY_PROGRESS: ReplayProgress = {
  currentTime: 0,
  totalDuration: null,
  currentLap: null,
  totalLaps: null,
};

export function sessionLabel(session: ReplaySessionOption): string {
  return (
    session.country_name ??
    session.circuit_short_name ??
    session.location ??
    String(session.session_key)
  );
}

export function grandPrixName(session: ReplaySessionOption): string {
  const name =
    session.country_name ?? session.location ?? session.circuit_short_name ?? String(session.session_key);
  return `${name} Grand Prix`;
}

export function speedHelperText(speed: number): string {
  if (speed <= 1) {
    return "1× — real time. One minute of race time plays in one minute.";
  }
  return `${speed}× means 1 minute of race time plays in about ${Math.round(
    60 / speed,
  )} seconds.`;
}

export function useReplay(onSeeded: () => void) {
  const [sessions, setSessions] = useState<ReplaySessionOption[]>([]);
  const [year, setYear] = useState<string>("");
  const [sessionKey, setSessionKey] = useState<string>("");
  const [speed, setSpeed] = useState<ReplaySpeedValue>(defaultSpeed);
  const [status, setStatus] = useState<ReplayStatusValue>("idle");
  const [progress, setProgress] = useState<ReplayProgress>(EMPTY_PROGRESS);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState<boolean>(true);
  const seededRef = useRef(false);

  const years = useMemo(
    () => [...new Set(sessions.map((session) => session.year))].sort((a, b) => b - a),
    [sessions],
  );
  const races = useMemo(
    () =>
      sessions
        .filter((session) => String(session.year) === year)
        .sort((a, b) => sessionLabel(a).localeCompare(sessionLabel(b))),
    [sessions, year],
  );
  const selectedSession = useMemo(
    () => sessions.find((session) => String(session.session_key) === sessionKey) ?? null,
    [sessions, sessionKey],
  );

  useEffect(() => {
    let cancelled = false;
    fetchReplaySessions()
      .then((list) => {
        if (cancelled) return;
        setSessions(list);
        const sortedYears = [...new Set(list.map((s) => s.year))].sort((a, b) => b - a);
        if (sortedYears.length > 0) {
          const defaultYear = sortedYears[0];
          setYear(String(defaultYear));
          const first = list.find((s) => s.year === defaultYear);
          setSessionKey(first ? String(first.session_key) : "");
        }
      })
      .catch(() => {
        if (!cancelled) setError("Could not load race list");
      })
      .finally(() => {
        if (!cancelled) setLoadingSessions(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const active = status === "downloading" || status === "running" || status === "paused";

  useEffect(() => {
    if (!active) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const next = await fetchReplayStatus();
        if (cancelled) return;
        setStatus(next.status);
        setProgress({
          currentTime: next.current_time,
          totalDuration: next.total_duration,
          currentLap: next.current_lap,
          totalLaps: next.total_laps,
        });
        if (next.status === "error") {
          setError(next.error ?? "Replay failed");
          return;
        }
        if (
          (next.status === "running" || next.status === "finished") &&
          !seededRef.current
        ) {
          seededRef.current = true;
          onSeeded();
        }
      } catch {
        // Transient network error — retry on the next tick.
      }
    };

    poll();
    const timer = window.setInterval(poll, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [active, onSeeded]);

  const selectYear = useCallback(
    (nextYear: string) => {
      setYear(nextYear);
      const first = sessions.find((session) => String(session.year) === nextYear);
      setSessionKey(first ? String(first.session_key) : "");
    },
    [sessions],
  );

  const selectRace = useCallback((key: string) => {
    setSessionKey(key);
  }, []);

  const start = useCallback(async () => {
    const key = Number(sessionKey);
    if (!Number.isInteger(key) || key <= 0) {
      setError("Select a race");
      return;
    }
    setBusy(true);
    setError(null);
    seededRef.current = false;
    setProgress(EMPTY_PROGRESS);
    try {
      const next = await startReplay(key, Number(speed) || 10);
      setStatus(next.status);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Failed to start replay",
      );
    } finally {
      setBusy(false);
    }
  }, [sessionKey, speed]);

  const pause = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const next = await pauseReplay();
      setStatus(next.status);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Failed to pause replay",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  const resume = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const next = await resumeReplay();
      setStatus(next.status);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Failed to resume replay",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  const stop = useCallback(async () => {
    setBusy(true);
    setError(null);
    seededRef.current = false;
    try {
      const next = await stopReplay();
      setStatus(next.status);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Failed to stop replay",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  const seek = useCallback(async (lap: number) => {
    if (!Number.isInteger(lap) || lap < 0) {
      setError("Pick a lap to seek to");
      return;
    }
    setBusy(true);
    setError(null);
    seededRef.current = false;
    try {
      const next = await seekReplay(lap);
      setStatus(next.status);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Failed to seek replay",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  return {
    sessions,
    years,
    races,
    year,
    sessionKey,
    selectedSession,
    speed,
    setSpeed,
    status,
    progress,
    busy,
    error,
    loadingSessions,
    selectYear,
    selectRace,
    start,
    pause,
    resume,
    stop,
    seek,
  };
}
