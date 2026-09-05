import { useMemo } from "react";
import { Panel } from "../../components/Panel";
import { StatusChip } from "../../components/StatusChip";
import type { ReplaySessionOption } from "../../api/replay";
import {
  SPEED_PRESETS,
  grandPrixName,
  sessionLabel,
  speedHelperText,
  useReplay,
} from "./useReplay";
import { ReplayProgress } from "./ReplayProgress";

type ReplayControlsProps = ReturnType<typeof useReplay> & { canSeek: boolean };

const STATUS_LABELS: Record<string, string> = {
  idle: "Ready to play",
  downloading: "Loading replay",
  running: "Playing",
  paused: "Paused",
  finished: "Finished",
  error: "Error",
};

const STATUS_TONES: Record<string, "neutral" | "green" | "amber" | "red"> = {
  idle: "green",
  downloading: "amber",
  running: "green",
  paused: "amber",
  finished: "neutral",
  error: "red",
};

const READINESS_LABELS: Record<string, string> = {
  ready: "Ready",
  partial: "Partial location data",
  cancelled: "Cancelled",
  not_ready: "Not ready",
  failed: "Preparation failed",
  unknown: "Unknown",
};

const READINESS_TONES: Record<string, "neutral" | "green" | "amber" | "red"> = {
  ready: "green",
  partial: "amber",
  cancelled: "neutral",
  not_ready: "amber",
  failed: "red",
  unknown: "neutral",
};

function RaceSummary({ session }: { session: ReplaySessionOption }) {
  const readiness = session.readiness ?? "unknown";
  return (
    <div className="replay-summary">
      <span className="replay-summary-name">{grandPrixName(session)}</span>
      {session.circuit_short_name ? (
        <>
          <span className="replay-summary-sep">·</span>
          <span className="replay-summary-circuit">{session.circuit_short_name}</span>
        </>
      ) : null}
      <StatusChip
        label={READINESS_LABELS[readiness] ?? readiness}
        tone={READINESS_TONES[readiness] ?? "neutral"}
      />
    </div>
  );
}

export function ReplayControls(replay: ReplayControlsProps) {
  const {
    years,
    races,
    year,
    sessionKey,
    selectedSession,
    speed,
    setSpeed,
    status,
    replayId,
    progress,
    busy,
    pendingAction,
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
    seekLap,
    canSeek,
  } = replay;

  const isActive = replayId !== null;
  const isRunning = status === "running";
  const isPaused = status === "paused";
  const isFinished = status === "finished";
  const isDownloading = status === "downloading";
  const isIdle = status === "idle" || status === "error";
  const readiness = selectedSession?.readiness ?? "unknown";
  const isPlayable = readiness === "ready" || readiness === "partial";
  const canStart =
    (isIdle || isFinished) &&
    !busy &&
    !loadingSessions &&
    selectedSession !== null &&
    isPlayable;
  const speedEditable = isIdle || isRunning || isPaused;

  const statusChip = useMemo(() => {
    if (status === "idle") {
      return selectedSession && isPlayable
        ? { label: "Ready to play", tone: "green" as const }
        : null;
    }
    return {
      label: STATUS_LABELS[status] ?? status,
      tone: STATUS_TONES[status] ?? ("neutral" as const),
    };
  }, [status, selectedSession, isPlayable]);

  const primary = useMemo(() => {
    if (isDownloading) {
      return {
        icon: "progress_activity",
        label: "Loading Replay",
        onClick: start,
        disabled: true,
      };
    }
    if (isRunning) {
      return {
        icon: "pause",
        label: pendingAction === "pause" ? "Pausing…" : "Pause",
        onClick: pause,
        disabled: busy,
      };
    }
    if (isPaused) {
      return {
        icon: "play_arrow",
        label: pendingAction === "resume" ? "Resuming…" : "Resume",
        onClick: resume,
        disabled: busy,
      };
    }
    if (isFinished) {
      return {
        icon: "replay",
        label: pendingAction === "start" ? "Replaying…" : "Replay from Start",
        onClick: start,
        disabled: busy,
      };
    }
    return {
      icon: "play_arrow",
      label: pendingAction === "start" ? "Starting…" : "Start Replay",
      onClick: start,
      disabled: !canStart,
    };
  }, [isDownloading, isRunning, isPaused, isFinished, pendingAction, busy, canStart, start, pause, resume]);

  return (
    <Panel
      label="Replay"
      icon="replay"
      className="replay-panel"
      headerContent={
        statusChip ? (
          <span aria-live="polite">
            <StatusChip label={statusChip.label} tone={statusChip.tone} />
          </span>
        ) : null
      }
    >
      <div className="replay-body">
        {!isActive ? (
          <div className="replay-select-mode">
            <div className="replay-picker">
              <div className="replay-field">
                <label className="replay-field-label" htmlFor="replay-year">
                  Year
                </label>
                <select
                  id="replay-year"
                  className="replay-select"
                  value={year}
                  onChange={(event) => selectYear(event.target.value)}
                  disabled={loadingSessions || years.length === 0}
                >
                  {years.length === 0 ? (
                    <option value="">{loadingSessions ? "Loading…" : "No races"}</option>
                  ) : (
                    years.map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))
                  )}
                </select>
              </div>
              <div className="replay-field">
                <label className="replay-field-label" htmlFor="replay-race">
                  Grand Prix
                </label>
                <select
                  id="replay-race"
                  className="replay-select"
                  value={sessionKey}
                  onChange={(event) => selectRace(event.target.value)}
                  disabled={loadingSessions || races.length === 0}
                >
                  {races.length === 0 ? (
                    <option value="">{loadingSessions ? "Loading…" : "No races"}</option>
                  ) : (
                    races.map((session) => (
                      <option key={session.session_key} value={session.session_key}>
                        {sessionLabel(session)}
                        {session.readiness === "cancelled"
                          ? " (cancelled)"
                          : session.readiness === "partial"
                            ? " (partial)"
                            : session.readiness === "not_ready"
                              ? " (not ready)"
                              : session.readiness === "failed"
                                ? " (failed)"
                                : ""}
                      </option>
                    ))
                  )}
                </select>
              </div>
              <div className="replay-field">
                <label className="replay-field-label" htmlFor="replay-speed">
                  Speed:
                </label>
                <select
                  id="replay-speed"
                  className="replay-select"
                  value={speed}
                  onChange={(event) => setSpeed(Number(event.target.value))}
                  disabled={!speedEditable || busy}
                  title={speedHelperText(speed)}
                >
                  {SPEED_PRESETS.map((value) => (
                    <option key={value} value={value}>
                      {value}×
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                className="replay-play-button"
                onClick={primary.onClick}
                disabled={primary.disabled}
              >
                <span className="material-symbols-rounded replay-play-icon" aria-hidden="true">
                  {primary.icon}
                </span>
                <span>{primary.label}</span>
              </button>
            </div>

            {selectedSession ? <RaceSummary session={selectedSession} /> : null}

            <details className="replay-advanced">
              <summary className="replay-advanced-summary">Advanced</summary>
              <div className="replay-advanced-body">
                <label className="replay-field-label" htmlFor="replay-session-id">
                  Session ID
                </label>
                <div className="replay-session-id-row">
                  <input
                    id="replay-session-id"
                    className="replay-session-id-input"
                    type="text"
                    inputMode="numeric"
                    placeholder="e.g. 9963"
                    value={sessionIdInput}
                    onChange={(event) => setSessionIdInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") submitSessionId();
                    }}
                    aria-label="Session ID"
                  />
                  <button
                    type="button"
                    className="replay-session-id-button"
                    onClick={submitSessionId}
                  >
                    Select Session
                  </button>
                </div>
                {sessionIdError ? (
                  <div className="replay-session-id-error">{sessionIdError}</div>
                ) : null}
              </div>
            </details>
          </div>
        ) : (
          <div className="replay-active-mode">
            <div className="replay-active-race">
              {selectedSession ? <RaceSummary session={selectedSession} /> : null}
            </div>

            <ReplayProgress
              progress={progress}
              onSeek={seek}
              onSeekLap={seekLap}
              canSeek={canSeek}
              seeking={pendingAction === "seek"}
              leading={
                <button
                  type="button"
                  className="replay-play-button"
                  onClick={primary.onClick}
                  disabled={primary.disabled}
                >
                  <span className="material-symbols-rounded replay-play-icon" aria-hidden="true">
                    {primary.icon}
                  </span>
                  <span>{primary.label}</span>
                </button>
              }
              trailing={
                <>
                  <label className="replay-speed" htmlFor="replay-speed-active">
                    <span className="replay-speed-label">Speed:</span>
                    <select
                      id="replay-speed-active"
                      className="replay-select"
                      value={speed}
                      onChange={(event) => setSpeed(Number(event.target.value))}
                      disabled={!speedEditable || busy || pendingAction === "speed"}
                      title={speedHelperText(speed)}
                      aria-label="Replay speed"
                    >
                      {SPEED_PRESETS.map((value) => (
                        <option key={value} value={value}>
                          {value}×
                        </option>
                      ))}
                    </select>
                  </label>

                  <button
                    type="button"
                    className="replay-end-button"
                    onClick={stop}
                    disabled={busy}
                  >
                    <span className="material-symbols-rounded replay-end-icon" aria-hidden="true">
                      stop
                    </span>
                    <span>{pendingAction === "stop" ? "Ending…" : "End Replay"}</span>
                  </button>
                </>
              }
            />
          </div>
        )}

        {error ? (
          <div className="replay-error" role="alert">
            {error}
          </div>
        ) : null}
      </div>
    </Panel>
  );
}
