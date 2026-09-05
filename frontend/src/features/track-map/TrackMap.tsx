import { useState, type CSSProperties } from "react";
import { Panel } from "../../components/Panel";
import type { ApiDriver, ApiSession, TrackState } from "../../types/race";
import type { DriverTrackProgress } from "../../hooks/useLiveState";
import type { ResourceStatus } from "../dashboard/useRaceData";
import { START_FINISH_SQUARE_SIZE, startFinishSquares, trackPath } from "./geometry";
import { useDriverMarkers } from "./useDriverMarkers";
import type { MarkerAnimationMode } from "./useDriverMarkers";

type TrackMapProps = {
  track: TrackState | null;
  trackStatus: ResourceStatus;
  session: ApiSession;
  drivers: ApiDriver[];
  progress: ReadonlyMap<number, DriverTrackProgress>;
  resetGeneration: number;
  animationMode?: MarkerAnimationMode;
  selectedDriver: ApiDriver | null;
  onSelectDriver: (driverNumber: number) => void;
};

export function TrackMap({ track, trackStatus, session, drivers, progress, resetGeneration, animationMode = { type: "live" }, selectedDriver, onSelectDriver }: TrackMapProps) {
  const [showTrack, setShowTrack] = useState(true);
  const [showPitLane, setShowPitLane] = useState(true);
  const [showDriverNames, setShowDriverNames] = useState(true);

  const displayPath = track?.display_path ?? [];
  const pitLanePoints = track?.pit_lane?.path ?? [];
  const hasPitLane = pitLanePoints.length > 0;
  const { registerMarker } = useDriverMarkers(
    displayPath,
    pitLanePoints,
    progress,
    resetGeneration,
    animationMode,
  );
  const label = `${session.meeting_name.toUpperCase()} | ${session.session_name.toUpperCase()}`;
  const mapPath = track ? trackPath(track.display_path) : "";
  const pitLanePath = pitLanePoints.length ? trackPath(pitLanePoints) : null;
  const squares = track ? startFinishSquares(track.start_finish) : [];

  return (
    <Panel label={label} className="track-map-panel" icon="map">
      {track ? (
        <div className="track-map-frame">
          <div className="track-map-info" aria-hidden="true">
            <div className="track-map-info-name">{track.circuit_name}</div>
            {track.country_name && (
              <div className="track-map-info-country">{track.country_name}</div>
            )}
          </div>
          <svg
            viewBox="0 0 100 85"
            className="track-map-svg"
            role="img"
            aria-label={`${track.circuit_name} circuit map with selectable driver markers`}
          >
            {showPitLane && pitLanePath && <path d={pitLanePath} className="track-map-pit-lane" />}
            {showTrack && <path d={mapPath} className="track-map-road" />}
            {showTrack && (
              <g
                aria-label="Start finish line"
                transform={`rotate(${track.start_finish.angle_deg}, ${track.start_finish.x}, ${track.start_finish.y})`}
              >
                <line
                  className="track-map-start-finish-line"
                  x1={track.start_finish.x}
                  x2={track.start_finish.x}
                  y1={track.start_finish.y - START_FINISH_SQUARE_SIZE * 1.5}
                  y2={track.start_finish.y + START_FINISH_SQUARE_SIZE * 1.5}
                />
                {squares.map((square) => (
                  <rect
                    key={`${square.row}-${square.column}`}
                    className={`track-map-start-finish-square track-map-start-finish-square--${square.isLight ? "light" : "dark"}`}
                    x={square.x}
                    y={square.y}
                    width={START_FINISH_SQUARE_SIZE}
                    height={START_FINISH_SQUARE_SIZE}
                  />
                ))}
              </g>
            )}
            {drivers.map((driver) => {
              const entry = progress.get(driver.driver_number);
              if (!entry) {
                return null;
              }
              const routeVisible = entry.route === "track" ? showTrack : showPitLane;
              const isSelected = driver.driver_number === selectedDriver?.driver_number;
              const markerStyle = {
                "--driver-colour": `#${driver.team_colour}`,
              } as CSSProperties;

              return (
                <g
                  key={driver.driver_number}
                  ref={registerMarker(driver.driver_number)}
                  role="button"
                  tabIndex={0}
                  className={`track-map-marker ${isSelected ? "track-map-marker--selected" : ""} ${routeVisible ? "" : "track-map-marker--hidden"}`}
                  aria-label={`${isSelected ? "Unselect" : "Select"} ${driver.acronym} marker`}
                  style={markerStyle}
                  onClick={() => onSelectDriver(driver.driver_number)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") onSelectDriver(driver.driver_number);
                  }}
                >
                  <circle className="track-map-marker-dot" cx={0} cy={0} />
                  {showDriverNames ? (
                    <text className="track-map-marker-label" x={3} y={1}>
                      {driver.acronym}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </svg>
          <div className="track-map-controls" role="group" aria-label="Map display options">
            <button
              type="button"
              className={`track-map-toggle ${showTrack ? "track-map-toggle--active" : ""}`}
              aria-pressed={showTrack}
              onClick={() => setShowTrack((value) => !value)}
            >
              <span className="track-map-toggle-indicator" aria-hidden="true" />
              Track
            </button>
            <button
              type="button"
              className={`track-map-toggle ${showPitLane && hasPitLane ? "track-map-toggle--active" : ""}`}
              aria-pressed={showPitLane && hasPitLane}
              aria-label={hasPitLane ? undefined : "Pit Lane unavailable for this circuit"}
              title={hasPitLane ? undefined : "Pit lane not available for this circuit"}
              onClick={() => setShowPitLane((value) => !value)}
              disabled={!hasPitLane}
            >
              <span className="track-map-toggle-indicator" aria-hidden="true" />
              Pit Lane
            </button>
            <button
              type="button"
              className={`track-map-toggle ${showDriverNames ? "track-map-toggle--active" : ""}`}
              aria-pressed={showDriverNames}
              onClick={() => setShowDriverNames((value) => !value)}
            >
              <span className="track-map-toggle-indicator" aria-hidden="true" />
              Driver Names
            </button>
          </div>
        </div>
      ) : trackStatus === "loading" ? (
        <div className="track-map-frame track-map-frame--unavailable">
          <div className="track-map-unavailable">
            <span className="track-map-unavailable-title">Loading circuit map</span>
            <span className="track-map-unavailable-copy">Fetching track geometry.</span>
          </div>
        </div>
      ) : (
        <div className="track-map-frame track-map-frame--unavailable">
          <div className="track-map-unavailable">
            <span className="track-map-unavailable-title">Circuit map unavailable</span>
            <span className="track-map-unavailable-copy">Track data could not be loaded.</span>
          </div>
        </div>
      )}
    </Panel>
  );
}
