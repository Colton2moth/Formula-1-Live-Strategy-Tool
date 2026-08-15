import { Panel } from "../../components/Panel";
import type { ReplayProgress as ReplayProgressState } from "./useReplay";

type ReplayProgressProps = {
  progress: ReplayProgressState;
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

export function ReplayProgress({ progress }: ReplayProgressProps) {
  const { currentTime, totalDuration, currentLap, totalLaps } = progress;
  const percent =
    totalDuration && totalDuration > 0 && currentTime !== null
      ? Math.min(100, Math.max(0, (currentTime / totalDuration) * 100))
      : 0;

  return (
    <Panel label="Replay Progress" className="replay-progress-panel">
      <div className="replay-progress-body">
        <div
          className="replay-progress-track"
          role="progressbar"
          aria-label="Replay progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(percent)}
        >
          <div className="replay-progress-fill" style={{ width: `${percent}%` }} />
        </div>
        <div className="replay-progress-readouts">
          <div className="replay-progress-time">
            <span className="replay-progress-value">{formatDuration(currentTime)}</span>
            <span className="replay-progress-divider">/</span>
            <span className="replay-progress-value">{formatDuration(totalDuration)}</span>
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
