import { Panel } from "../../components/Panel";
import { StatusChip } from "../../components/StatusChip";
import {
  SPEED_OPTIONS,
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
  preparing: "Preparing",
  failed: "Failed",
  unknown: "Unknown",
};

const READINESS_TONES: Record<string, "neutral" | "green" | "amber" | "red"> = {
  ready: "green",
  preparing: "amber",
  failed: "red",
  unknown: "neutral",
};

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
  const playLabel = isFinished ? "Replay" : "Play";
  const idleHint = !selectedSession
    ? "Select a race and press Play."
    : isReady
      ? "Ready — press Play."
      : readiness === "failed"
        ? "This race could not be prepared."
        : "This race is still being prepared.";

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
                    {session.readiness === "preparing"
                      ? " (preparing)"
                      : session.readiness === "failed"
                        ? " (failed)"
                        : ""}
                  </option>
                ))
              )}
            </select>
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
            {SPEED_OPTIONS.map((option) => {
              const selected = option.value === speed;
              return (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  className={`replay-speed-option ${selected ? "replay-speed-option--selected" : ""}`}
                  onClick={() => setSpeed(option.value)}
                  disabled={!isIdle}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
          <div className="replay-speed-readout" aria-live="polite">
            Replay Speed: {speed}×
          </div>
          <div className="replay-speed-helper">{speedHelperText(Number(speed))}</div>
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
