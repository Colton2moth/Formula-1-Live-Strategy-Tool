import { useEffect, useState } from "react";
import { fetchTracks, toApiError } from "../../api/raceState";
import { ErrorScreen } from "../../components/ErrorScreen";
import { LoadingScreen } from "../../components/LoadingScreen";
import { classifyError } from "../dashboard/useRaceData";
import type { TrackState } from "../../types/race";
import {
  START_FINISH_SQUARE_SIZE,
  startFinishSquares,
  trackPath,
  VIEW_HEIGHT,
  VIEW_WIDTH,
} from "../track-map/geometry";

type PreviewState =
  | { status: "loading" }
  | { status: "error"; error: unknown }
  | { status: "ready"; tracks: TrackState[] };

export function TrackMapPreviews() {
  const [state, setState] = useState<PreviewState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    fetchTracks()
      .then((tracks) => {
        if (active) setState({ status: "ready", tracks });
      })
      .catch((requestError: unknown) => {
        if (active) {
          setState({ status: "error", error: requestError });
        }
      });
    return () => {
      active = false;
    };
  }, []);

  if (state.status === "loading") {
    return <LoadingScreen variant="loading" />;
  }

  if (state.status === "error") {
    return <ErrorScreen variant={classifyError(state.error)} error={toApiError(state.error)} />;
  }

  return (
    <main className="dashboard-shell">
      <div className="track-previews">
        <div role="heading" aria-level={1} className="track-previews-heading">
          Track Map Previews
        </div>
        <div className="track-previews-grid">
          {state.tracks.map((track) => (
            <TrackPreviewCard key={track.circuit_key} track={track} />
          ))}
        </div>
      </div>
    </main>
  );
}

type PitLaneStatus = "available" | "missing" | "invalid";

const PIT_LANE_LABELS: Record<PitLaneStatus, string> = {
  available: "available",
  missing: "missing",
  invalid: "invalid",
};

function TrackPreviewCard({ track }: { track: TrackState }) {
  const pathValid = Array.isArray(track.display_path) && track.display_path.length >= 2;
  const startFinishValid = typeof track.start_finish?.angle_deg === "number";
  const pitLane = pitLaneStatus(track);

  return (
    <div className="track-preview-card">
      <div className="track-preview-header">
        <div className="track-preview-title">
          <span className="track-preview-name">{track.circuit_name}</span>
          {track.country_name && <span className="track-preview-country">{track.country_name}</span>}
        </div>
        <span className="track-preview-key">Circuit key {track.circuit_key}</span>
      </div>

      {pathValid ? (
        <TrackPreviewSvg track={track} />
      ) : (
        <div className="track-preview-unavailable">Unavailable: invalid circuit path</div>
      )}

      <div className="track-preview-statuses">
        <span className={`track-preview-pit track-preview-pit--${pitLane}`}>
          Pit lane: {PIT_LANE_LABELS[pitLane]}
        </span>
        <span className="track-preview-note">
          {track.display_path.length} pts · rot {track.rotation}°
        </span>
        {!startFinishValid && <span className="track-preview-note">Start/finish: missing</span>}
      </div>
    </div>
  );
}

function TrackPreviewSvg({ track }: { track: TrackState }) {
  const squares = startFinishSquares(track.start_finish);

  return (
    <div className="track-preview-frame">
      <svg
        viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
        className="track-preview-svg"
        role="img"
        aria-label={`${track.circuit_name} circuit map preview`}
      >
        <path d={trackPath(track.display_path)} className="track-preview-road" />
        {track.pit_lane?.path?.length ? (
          <path d={trackPath(track.pit_lane.path)} className="track-preview-pit-lane" />
        ) : null}
        <g
          aria-label="Start finish line"
          transform={`rotate(${track.start_finish.angle_deg}, ${track.start_finish.x}, ${track.start_finish.y})`}
        >
          <line
            className="track-preview-start-finish-line"
            x1={track.start_finish.x}
            x2={track.start_finish.x}
            y1={track.start_finish.y - START_FINISH_SQUARE_SIZE * 1.5}
            y2={track.start_finish.y + START_FINISH_SQUARE_SIZE * 1.5}
          />
          {squares.map((square) => (
            <rect
              key={`${square.row}-${square.column}`}
              className={`track-preview-start-finish-square track-preview-start-finish-square--${square.isLight ? "light" : "dark"}`}
              x={square.x}
              y={square.y}
              width={START_FINISH_SQUARE_SIZE}
              height={START_FINISH_SQUARE_SIZE}
            />
          ))}
        </g>
      </svg>
    </div>
  );
}

function pitLaneStatus(track: TrackState): PitLaneStatus {
  const lane = track.pit_lane;
  if (!lane || !Array.isArray(lane.path) || lane.path.length === 0) {
    return "missing";
  }
  if (lane.path.length < 2) {
    return "invalid";
  }
  return "available";
}
