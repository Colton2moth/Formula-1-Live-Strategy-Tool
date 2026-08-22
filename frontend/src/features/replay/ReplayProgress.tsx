import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Panel } from "../../components/Panel";
import type { ReplayProgress as ReplayProgressState } from "./useReplay";

type ReplayProgressProps = {
  progress: ReplayProgressState;
  onSeek: (time: number) => void;
  onSeekLap: (lap: number) => void;
  canSeek: boolean;
};

function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) {
    return "--:--";
  }
  const total = Math.floor(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

export function ReplayProgress({ progress, onSeek, onSeekLap, canSeek }: ReplayProgressProps) {
  const { currentTime, totalDuration, currentLap, totalLaps } = progress;
  const [previewTime, setPreviewTime] = useState<number | null>(null);
  const [lapText, setLapText] = useState("1");
  const lapInputFocusedRef = useRef(false);

  const max = totalDuration && totalDuration > 0 ? totalDuration : 0;
  const displayed = Math.min(max, previewTime ?? currentTime ?? 0);
  const disabled = !canSeek || max <= 0;
  const lapTarget = Number(lapText);
  const maxLap = totalLaps ?? 0;
  const lapDisabled = !canSeek || maxLap <= 0;
  const lapValid =
    !lapDisabled && Number.isInteger(lapTarget) && lapTarget >= 1 && lapTarget <= maxLap;
  const timelineStyle = {
    "--replay-progress": `${max > 0 ? (displayed / max) * 100 : 0}%`,
  } as CSSProperties;

  useEffect(() => {
    if (!lapInputFocusedRef.current && currentLap !== null) {
      setLapText(String(Math.max(1, currentLap)));
    }
  }, [currentLap]);

  const commit = (value: number) => {
    setPreviewTime(null);
    if (!disabled && Number.isFinite(value)) {
      onSeek(Math.min(max, Math.max(0, value)));
    }
  };

  return (
    <Panel label="Replay Progress" className="replay-progress-panel" icon="timeline">
      <div className="replay-progress-body">
        <input
          type="range"
          className="replay-timeline"
          aria-label="Replay timeline"
          min={0}
          max={max}
          step={0.1}
          value={displayed}
          style={timelineStyle}
          disabled={disabled}
          onChange={(event) => setPreviewTime(Number(event.target.value))}
          onPointerUp={(event) => commit(Number((event.target as HTMLInputElement).value))}
          onKeyUp={(event) => commit(Number((event.target as HTMLInputElement).value))}
        />
        <div className="replay-progress-readouts">
          <div className="replay-progress-time">
            <span className="replay-progress-label">Elapsed</span>
            <span className="replay-progress-value">{formatDuration(displayed)}</span>
            <span className="replay-progress-divider">/</span>
            <span className="replay-progress-value">{formatDuration(max)}</span>
          </div>
          {totalLaps !== null && totalLaps > 0 ? (
            <div className="replay-progress-laps">
              <label className="replay-progress-label" htmlFor="replay-lap-target">
                Lap
              </label>
              <input
                id="replay-lap-target"
                className="replay-lap-input"
                type="number"
                min={1}
                max={totalLaps}
                step={1}
                value={lapText}
                disabled={lapDisabled}
                aria-invalid={lapText !== "" && !lapValid}
                onFocus={() => {
                  lapInputFocusedRef.current = true;
                }}
                onBlur={() => {
                  lapInputFocusedRef.current = false;
                }}
                onChange={(event) => setLapText(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && lapValid) onSeekLap(lapTarget);
                }}
              />
              <span className="replay-progress-divider">/</span>
              <span className="replay-progress-value">{totalLaps}</span>
              <button
                type="button"
                className="replay-lap-button"
                aria-label={`Jump to lap ${lapText || "number"}`}
                onClick={() => onSeekLap(lapTarget)}
                disabled={!lapValid}
              >
                <span className="material-symbols-rounded replay-lap-button-icon" aria-hidden="true">
                  arrow_forward
                </span>
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </Panel>
  );
}
