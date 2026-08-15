import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchReplaySessions,
  fetchReplayStatus,
  startReplay,
  stopReplay,
} from "../api/raceState";
import type { ReplaySessionOption } from "../api/raceState";

const DEFAULT_SPEED: string = import.meta.env.VITE_REPLAY_SPEED ?? "10";

const STATUS_LABELS: Record<string, string> = {
  idle: "Idle",
  downloading: "Loading data…",
  running: "Running",
  finished: "Finished",
  error: "Error",
};

type ReplayControlsProps = {
  onReload: () => void;
};

function sessionLabel(session: ReplaySessionOption): string {
  return (
    session.country_name ??
    session.circuit_short_name ??
    session.location ??
    String(session.session_key)
  );
}

export function ReplayControls({ onReload }: ReplayControlsProps) {
  const [sessions, setSessions] = useState<ReplaySessionOption[]>([]);
  const [year, setYear] = useState<string>("");
  const [sessionKey, setSessionKey] = useState<string>("");
  const [speed, setSpeed] = useState<string>(DEFAULT_SPEED);
  const [status, setStatus] = useState<string>("idle");
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState<boolean>(true);
  const reloadedRef = useRef(false);

  const years = useMemo(
    () => [...new Set(sessions.map((session) => session.year))].sort((a, b) => b - a),
    [sessions],
  );
  const countries = useMemo(
    () =>
      sessions
        .filter((session) => String(session.year) === year)
        .sort((a, b) => sessionLabel(a).localeCompare(sessionLabel(b))),
    [sessions, year],
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

  // While the replay is downloading or running, poll its status so we know when
  // data is actually in LIVE_STATE. The first time it is seeded (running or
  // finished) we refetch the race snapshot so the whole UI switches to the
  // replayed session instead of showing the previous live/bootstrap data.
  useEffect(() => {
    if (status !== "downloading" && status !== "running") {
      return;
    }
    let cancelled = false;

    const poll = async () => {
      try {
        const next = await fetchReplayStatus();
        if (cancelled) return;
        setStatus(next.status);
        if (next.status === "error") {
          setError(next.error ?? "Replay failed");
          return;
        }
        if (
          (next.status === "running" || next.status === "finished") &&
          !reloadedRef.current
        ) {
          reloadedRef.current = true;
          onReload();
        }
      } catch {
        // Transient network error — retry on the next tick.
      }
    };

    poll();
    const timer = window.setInterval(poll, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [status, onReload]);

  const onYearChange = (nextYear: string) => {
    setYear(nextYear);
    const first = sessions.find((session) => String(session.year) === nextYear);
    setSessionKey(first ? String(first.session_key) : "");
  };

  const onStart = async () => {
    const key = Number(sessionKey);
    if (!Number.isInteger(key) || key <= 0) {
      setError("Select a race");
      return;
    }
    setBusy(true);
    setError(null);
    reloadedRef.current = false;
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
  };

  const onStop = async () => {
    setBusy(true);
    setError(null);
    reloadedRef.current = false;
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
  };

  return (
    <div className="replay-controls">
      <span className="replay-controls-label">Replay</span>
      <select
        className="replay-controls-select replay-controls-select--year"
        value={year}
        onChange={(event) => onYearChange(event.target.value)}
        disabled={loadingSessions || years.length === 0}
        aria-label="Replay year"
      >
        {years.map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </select>
      <select
        className="replay-controls-select replay-controls-select--country"
        value={sessionKey}
        onChange={(event) => setSessionKey(event.target.value)}
        disabled={loadingSessions || countries.length === 0}
        aria-label="Replay race"
      >
        {countries.map((session) => (
          <option key={session.session_key} value={session.session_key}>
            {sessionLabel(session)}
          </option>
        ))}
      </select>
      <input
        className="replay-controls-input replay-controls-input--speed"
        type="number"
        inputMode="decimal"
        step="1"
        placeholder="Speed"
        value={speed}
        onChange={(event) => setSpeed(event.target.value)}
        aria-label="Replay speed"
      />
      <button
        className="replay-controls-button"
        type="button"
        onClick={onStart}
        disabled={busy || loadingSessions}
      >
        {busy ? "Starting…" : "Start"}
      </button>
      <button
        className="replay-controls-button replay-controls-button--stop"
        type="button"
        onClick={onStop}
        disabled={busy}
      >
        Stop
      </button>
      <span className="replay-controls-status" aria-live="polite">
        {loadingSessions ? "Loading races…" : error ?? STATUS_LABELS[status] ?? status}
      </span>
    </div>
  );
}
