import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import type { ReplayProgress as ReplayProgressState } from "./useReplay";

type ReplayProgressProps = {
  progress: ReplayProgressState;
  onSeek: (time: number) => void;
  onSeekLap: (lap: number) => void;
  canSeek: boolean;
  seeking: boolean;
  leading?: ReactNode;
  trailing?: ReactNode;
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

const SEEK_KEYS = new Set(["ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"]);

export function ReplayProgress({
  progress,
  onSeek,
  onSeekLap,
  canSeek,
  seeking,
  leading,
  trailing,
}: ReplayProgressProps) {
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
    <div className="replay-toolbar">
      <div className="replay-toolbar-primary">
        {leading}
        <div className="replay-timeline-wrap">
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
            onKeyUp={(event) => {
              if (SEEK_KEYS.has(event.key)) {
                commit(Number((event.target as HTMLInputElement).value));
              }
            }}
          />
          {previewTime !== null && !disabled ? (
            <span className="replay-preview-time">{formatDuration(previewTime)}</span>
          ) : null}
        </div>
        <div className="replay-time-readout">
          <span className="replay-time-value">{formatDuration(displayed)}</span>
          <span className="replay-time-divider">/</span>
          <span className="replay-time-value">{formatDuration(max)}</span>
          {seeking ? <span className="replay-seeking">Seeking…</span> : null}
        </div>
      </div>

      <div className="replay-toolbar-secondary">
        

        {totalLaps !== null && totalLaps > 0 ? (
          <div className="replay-lap-seek">
            <label className="replay-lap-label" htmlFor="replay-lap-target">
              Lap:
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
            <span className="replay-lap-divider">/</span>
            <span className="replay-lap-total">{totalLaps}</span>
            <button
              type="button"
              className="replay-lap-button"
              onClick={() => onSeekLap(lapTarget)}
              disabled={!lapValid || seeking}
            >
              {seeking ? "Seeking…" : "Go to lap"}
            </button>
          </div>
        ) : null}

        {trailing}
      </div>
    </div>
  );
}
