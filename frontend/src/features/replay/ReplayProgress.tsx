import { useState } from "react";
import { Panel } from "../../components/Panel";
import type { ReplayProgress as ReplayProgressState } from "./useReplay";

type ReplayProgressProps = {
  progress: ReplayProgressState;
  onSeek: (time: number) => void;
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

export function ReplayProgress({ progress, onSeek, canSeek }: ReplayProgressProps) {
  const { currentTime, totalDuration, currentLap, totalLaps } = progress;
  const [previewTime, setPreviewTime] = useState<number | null>(null);

  const max = totalDuration && totalDuration > 0 ? totalDuration : 0;
  const displayed = Math.min(max, previewTime ?? currentTime ?? 0);
  const disabled = !canSeek || max <= 0;

  const commit = (value: number) => {
    setPreviewTime(null);
    if (!disabled && Number.isFinite(value)) {
      onSeek(Math.min(max, Math.max(0, value)));
    }
  };

  return (
    <Panel label="Replay Progress" className="replay-progress-panel">
      <div className="replay-progress-body">
        <input
          type="range"
          className="replay-timeline"
          aria-label="Replay timeline"
          min={0}
          max={max}
          step={0.1}
          value={displayed}
          disabled={disabled}
          onChange={(event) => setPreviewTime(Number(event.target.value))}
          onPointerUp={(event) => commit(Number((event.target as HTMLInputElement).value))}
          onKeyUp={(event) => commit(Number((event.target as HTMLInputElement).value))}
        />
        <div className="replay-progress-readouts">
          <div className="replay-progress-time">
            <span className="replay-progress-value">{formatDuration(displayed)}</span>
            <span className="replay-progress-divider">/</span>
            <span className="replay-progress-value">{formatDuration(max)}</span>
          </div>
          {totalLaps !== null && totalLaps > 0 ? (
            <div className="replay-progress-laps">
              Lap <span className="replay-progress-value">{currentLap ?? 0}</span>
              <span className="replay-progress-divider">/</span>
              <span className="replay-progress-value">{totalLaps}</span>
            </div>
          ) : null}
        </div>
      </div>
    </Panel>
  );
}
