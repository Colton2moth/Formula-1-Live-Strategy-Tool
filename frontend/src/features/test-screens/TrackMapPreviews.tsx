import { useEffect, useState } from "react";
import { fetchTracks } from "../../api/raceState";
import { ErrorScreen } from "../../components/ErrorScreen";
import { LoadingScreen } from "../../components/LoadingScreen";
import { classifyError } from "../dashboard/useRaceData";
import type { TrackState } from "../../types/race";
import {
  buildTrackGeometry,
  isPointValid,
  START_FINISH_SQUARE_SIZE,
  VIEW_HEIGHT,
  VIEW_WIDTH,
} from "../track-map/geometry";

type PreviewState =
  | { status: "loading" }
  | { status: "error"; message: string }
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
          setState({
            status: "error",
            message: requestError instanceof Error ? requestError.message : "Unable to load tracks.",
          });
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
    return <ErrorScreen variant={classifyError(state.message)} message={state.message} />;
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
  const pathValid = Array.isArray(track.path) && track.path.length >= 2 && track.path.every(isPointValid);
  const startFinishValid = isPointValid(track.start_finish);
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
        {!startFinishValid && <span className="track-preview-note">Start/finish: missing</span>}
      </div>
    </div>
  );
}

function TrackPreviewSvg({ track }: { track: TrackState }) {
  const geometry = buildTrackGeometry(track);

  return (
    <div className="track-preview-frame">
      <svg
        viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
        className="track-preview-svg"
        role="img"
        aria-label={`${track.circuit_name} circuit map preview`}
      >
        <path d={geometry.mapPath} className="track-preview-road" />
        {geometry.pitLanePath && <path d={geometry.pitLanePath} className="track-preview-pit-lane" />}
        {geometry.startFinish && (
          <g
            aria-label="Start finish line"
            transform={`rotate(${geometry.startFinishRotation}, ${geometry.startFinish.x}, ${geometry.startFinish.y})`}
          >
            <line
              className="track-preview-start-finish-line"
              x1={geometry.startFinish.x}
              x2={geometry.startFinish.x}
              y1={geometry.startFinish.y - START_FINISH_SQUARE_SIZE * 1.5}
              y2={geometry.startFinish.y + START_FINISH_SQUARE_SIZE * 1.5}
            />
            {geometry.startFinishSquares.map((square) => (
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
        )}
      </svg>
    </div>
  );
}

function pitLaneStatus(track: TrackState): PitLaneStatus {
  const lane = track.pit_lane;
  if (!Array.isArray(lane) || lane.length === 0) {
    return "missing";
  }
  if (lane.length < 2 || !lane.every(isPointValid)) {
    return "invalid";
  }
  return "available";
}
