import { useEffect, useRef, useState } from "react";
import { fetchReplayStatus, startReplay, stopReplay } from "../api/raceState";

const DEFAULT_SESSION_KEY: string = import.meta.env.VITE_REPLAY_SESSION_KEY ?? "";
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

export function ReplayControls({ onReload }: ReplayControlsProps) {
  const [sessionKey, setSessionKey] = useState<string>(DEFAULT_SESSION_KEY);
  const [speed, setSpeed] = useState<string>(DEFAULT_SPEED);
  const [status, setStatus] = useState<string>("idle");
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const reloadedRef = useRef(false);

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

  const onStart = async () => {
    const key = Number(sessionKey);
    if (!Number.isInteger(key) || key <= 0) {
      setError("Enter a valid session key");
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
      <input
        className="replay-controls-input"
        type="number"
        inputMode="numeric"
        placeholder="Session key"
        value={sessionKey}
        onChange={(event) => setSessionKey(event.target.value)}
        aria-label="Replay session key"
      />
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
        disabled={busy}
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
        {error ?? STATUS_LABELS[status] ?? status}
      </span>
    </div>
  );
}
