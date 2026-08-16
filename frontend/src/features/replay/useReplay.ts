import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchReplaySessions,
  fetchReplayStatus,
  pauseReplay,
  resumeReplay,
  seekReplay,
  setReplaySpeed,
  startReplay,
  stopReplay,
} from "../../api/replay";
import type { ReplaySessionOption, ReplayStatusValue } from "../../api/replay";

export const SPEED_PRESETS = [1, 2, 5, 10, 20, 50, 100] as const;
export const MIN_SPEED = 0.25;
export const MAX_SPEED = 100;

function clampSpeed(value: number): number {
  if (!Number.isFinite(value)) return 10;
  return Math.min(MAX_SPEED, Math.max(MIN_SPEED, value));
}

function defaultSpeed(): number {
  const env = Number(import.meta.env.VITE_REPLAY_SPEED);
  return (SPEED_PRESETS as readonly number[]).includes(env) ? env : 10;
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
  if (speed <= 0) {
    return "";
  }
  if (speed === 1) {
    return "1× — real time. One minute of race time plays in one minute.";
  }
  const seconds = 60 / speed;
  const span =
    seconds >= 60
      ? `${(seconds / 60).toFixed(1)} minutes`
      : seconds >= 1
        ? `about ${Math.round(seconds)} second${Math.round(seconds) === 1 ? "" : "s"}`
        : "under a second";
  return `${speed}× means 1 minute of race time plays in ${span}.`;
}

export function useReplay(onSeeded: () => void) {
  const [sessions, setSessions] = useState<ReplaySessionOption[]>([]);
  const [year, setYear] = useState<string>("");
  const [sessionKey, setSessionKey] = useState<string>("");
  const [speed, setSpeedState] = useState<number>(defaultSpeed);
  const [status, setStatus] = useState<ReplayStatusValue>("idle");
  const [progress, setProgress] = useState<ReplayProgress>(EMPTY_PROGRESS);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState<boolean>(true);
  const [sessionIdInput, setSessionIdInput] = useState<string>("");
  const [sessionIdError, setSessionIdError] = useState<string | null>(null);
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

  const setSpeed = useCallback(
    (nextSpeed: number) => {
      const clamped = clampSpeed(nextSpeed);
      setSpeedState(clamped);
      if (status === "running" || status === "paused") {
        void setReplaySpeed(clamped)
          .then((result) => setStatus(result.status))
          .catch(() => setError("Failed to change replay speed"));
      }
    },
    [status],
  );

  const submitSessionId = useCallback(() => {
    const trimmed = sessionIdInput.trim();
    if (trimmed === "") {
      setSessionIdError("Enter a session ID");
      return;
    }
    const id = Number(trimmed);
    if (!Number.isInteger(id) || id <= 0) {
      setSessionIdError("Session ID must be a positive whole number");
      return;
    }
    const found = sessions.find((session) => session.session_key === id);
    if (!found) {
      setSessionIdError(`Session ${id} is not in the replay library`);
      return;
    }
    setSessionIdError(null);
    setSessionKey(String(id));
    setYear(String(found.year));
  }, [sessions, sessionIdInput]);

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

  const seek = useCallback(async (time: number) => {
    if (!Number.isFinite(time) || time < 0) {
      setError("Pick a time to seek to");
      return;
    }
    setBusy(true);
    setError(null);
    seededRef.current = false;
    try {
      const next = await seekReplay(time);
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
    sessionIdInput,
    setSessionIdInput,
    sessionIdError,
    submitSessionId,
    selectYear,
    selectRace,
    start,
    pause,
    resume,
    stop,
    seek,
  };
}
