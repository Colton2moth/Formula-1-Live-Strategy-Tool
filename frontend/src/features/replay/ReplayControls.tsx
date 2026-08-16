import { useEffect, useState } from "react";
import { Panel } from "../../components/Panel";
import { StatusChip } from "../../components/StatusChip";
import {
  MAX_SPEED,
  MIN_SPEED,
  SPEED_PRESETS,
  grandPrixName,
  sessionLabel,
  speedHelperText,
  useReplay,
} from "./useReplay";

type ReplayControlsProps = ReturnType<typeof useReplay>;

const STATUS_LABELS: Record<string, string> = {
  idle: "Idle",
  downloading: "Loading data…",
  running: "Playing",
  paused: "Paused",
  finished: "Finished",
  error: "Error",
};

const STATUS_TONES: Record<string, "neutral" | "green" | "amber" | "red"> = {
  idle: "neutral",
  downloading: "amber",
  running: "green",
  paused: "amber",
  finished: "neutral",
  error: "red",
};

const READINESS_LABELS: Record<string, string> = {
  ready: "Ready",
  not_ready: "Not ready",
  failed: "Preparation failed",
  unknown: "Unknown",
};

const READINESS_TONES: Record<string, "neutral" | "green" | "amber" | "red"> = {
  ready: "green",
  not_ready: "amber",
  failed: "red",
  unknown: "neutral",
};

type CustomSpeedInputProps = {
  speed: number;
  disabled: boolean;
  onCommit: (speed: number) => void;
};

function CustomSpeedInput({ speed, disabled, onCommit }: CustomSpeedInputProps) {
  const [text, setText] = useState(String(speed));
  const [invalid, setInvalid] = useState(false);

  useEffect(() => {
    setText(String(speed));
    setInvalid(false);
  }, [speed]);

  const commit = () => {
    const value = Number(text);
    if (!Number.isFinite(value) || value < MIN_SPEED || value > MAX_SPEED) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    onCommit(value);
  };

  return (
    <div className="replay-speed-custom">
      <label className="replay-speed-label" htmlFor="replay-speed-custom">
        Custom speed
      </label>
      <input
        id="replay-speed-custom"
        className={`replay-speed-input ${invalid ? "replay-speed-input--invalid" : ""}`}
        type="number"
        min={MIN_SPEED}
        max={MAX_SPEED}
        step={0.25}
        value={text}
        disabled={disabled}
        onChange={(event) => {
          setText(event.target.value);
          setInvalid(false);
        }}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") commit();
        }}
        aria-label="Custom replay speed"
      />
      {invalid ? (
        <div className="replay-speed-error">
          Enter a speed from {MIN_SPEED}× to {MAX_SPEED}×
        </div>
      ) : null}
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
  } = replay;

  const isIdle = status === "idle" || status === "error";
  const isFinished = status === "finished";
  const isRunning = status === "running";
  const isPaused = status === "paused";
  const isDownloading = status === "downloading";
  const readiness = selectedSession?.readiness ?? "unknown";
  const isReady = readiness === "ready";
  const canStart =
    (isIdle || isFinished) && !busy && !loadingSessions && selectedSession !== null && isReady;
  const canStop = (isRunning || isPaused || isFinished || isDownloading) && !busy;
  const speedEditable = isIdle || isRunning || isPaused;
  const playLabel = isFinished ? "Replay" : "Play";
  const idleHint = !selectedSession
    ? "Select a race and press Play."
    : isReady
      ? "Ready — press Play."
      : readiness === "failed"
        ? "Replay preparation failed for this race."
        : readiness === "not_ready"
          ? "This race has not been prepared for replay yet."
          : "Readiness could not be determined.";

  return (
    <Panel
      label="Replay Control"
      className="replay-panel"
      headerContent={
        <StatusChip label={STATUS_LABELS[status] ?? status} tone={STATUS_TONES[status] ?? "neutral"} />
      }
    >
      <div className="replay-panel-body">
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
              disabled={loadingSessions || years.length === 0 || !isIdle}
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
              Country / Grand Prix
            </label>
            <select
              id="replay-race"
              className="replay-select"
              value={sessionKey}
              onChange={(event) => selectRace(event.target.value)}
              disabled={loadingSessions || races.length === 0 || !isIdle}
            >
              {races.length === 0 ? (
                <option value="">{loadingSessions ? "Loading…" : "No races"}</option>
              ) : (
                races.map((session) => (
                  <option key={session.session_key} value={session.session_key}>
                    {sessionLabel(session)}
                    {session.readiness === "not_ready"
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
                disabled={!isIdle}
                aria-label="Session ID"
              />
              <button
                type="button"
                className="replay-session-id-button"
                onClick={submitSessionId}
                disabled={!isIdle}
              >
                Go
              </button>
            </div>
            {sessionIdError ? (
              <div className="replay-session-id-error">{sessionIdError}</div>
            ) : null}
          </div>
        </div>

        {selectedSession ? (
          <div className="replay-selected">
            <div className="replay-selected-name">{grandPrixName(selectedSession)}</div>
            <div className="replay-selected-meta">
              <span className="replay-selected-chip">{selectedSession.year}</span>
              {selectedSession.country_name ? (
                <span className="replay-selected-chip">{selectedSession.country_name}</span>
              ) : null}
              {selectedSession.circuit_short_name ? (
                <span className="replay-selected-chip">{selectedSession.circuit_short_name}</span>
              ) : null}
              <span className="replay-selected-chip">Session {selectedSession.session_key}</span>
              <StatusChip
                label={READINESS_LABELS[readiness] ?? readiness}
                tone={READINESS_TONES[readiness] ?? "neutral"}
              />
            </div>
          </div>
        ) : null}

        <div className="replay-speed" role="radiogroup" aria-label="Replay Speed">
          <div className="replay-speed-label">Replay Speed</div>
          <div className="replay-speed-options">
            {SPEED_PRESETS.map((value) => {
              const selected = value === speed;
              return (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  className={`replay-speed-option ${selected ? "replay-speed-option--selected" : ""}`}
                  onClick={() => setSpeed(value)}
                  disabled={!speedEditable}
                >
                  {value}×
                </button>
              );
            })}
          </div>
          <CustomSpeedInput speed={speed} disabled={!speedEditable} onCommit={setSpeed} />
          <div className="replay-speed-readout" aria-live="polite">
            Replay Speed: {speed}×
          </div>
          <div className="replay-speed-helper">{speedHelperText(speed)}</div>
        </div>

        <div className="replay-transport">
          <button
            type="button"
            className="replay-transport-button replay-transport-button--play"
            onClick={start}
            disabled={!canStart}
          >
            <span className="material-symbols-rounded replay-transport-icon" aria-hidden="true">
              {isFinished ? "replay" : "play_arrow"}
            </span>
            {playLabel}
          </button>
          <button
            type="button"
            className="replay-transport-button"
            onClick={pause}
            disabled={!isRunning || busy}
          >
            <span className="material-symbols-rounded replay-transport-icon" aria-hidden="true">
              pause
            </span>
            Pause
          </button>
          <button
            type="button"
            className="replay-transport-button"
            onClick={resume}
            disabled={!isPaused || busy}
          >
            <span className="material-symbols-rounded replay-transport-icon" aria-hidden="true">
              play_arrow
            </span>
            Resume
          </button>
          <button
            type="button"
            className="replay-transport-button replay-transport-button--stop"
            onClick={stop}
            disabled={!canStop}
          >
            <span className="material-symbols-rounded replay-transport-icon" aria-hidden="true">
              stop
            </span>
            Stop
          </button>
        </div>

        <div className="replay-status" aria-live="polite">
          {loadingSessions
            ? "Loading races…"
            : error ?? (status === "idle" ? idleHint : STATUS_LABELS[status])}
        </div>
      </div>
    </Panel>
  );
}
