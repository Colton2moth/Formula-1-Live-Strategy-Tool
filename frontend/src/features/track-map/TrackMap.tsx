import type { CSSProperties } from "react";
import { Panel } from "../../components/Panel";
import type { ApiDriver, ApiSession, TrackState } from "../../types/race";
import type { DriverLocation } from "../../hooks/useLiveState";
import { START_FINISH_SQUARE_SIZE, startFinishSquares, trackPath } from "./geometry";

type TrackMapProps = {
  track: TrackState | null;
  session: ApiSession;
  drivers: ApiDriver[];
  locations: ReadonlyMap<number, DriverLocation>;
  selectedDriver: ApiDriver | null;
  onSelectDriver: (driverNumber: number) => void;
};

export function TrackMap({ track, session, drivers, locations, selectedDriver, onSelectDriver }: TrackMapProps) {
  const label = `${session.meeting_name.toUpperCase()} | ${session.session_name.toUpperCase()}`;
  const mapPath = track ? trackPath(track.display_path) : "";
  const pitLanePath = track?.pit_lane?.path?.length ? trackPath(track.pit_lane.path) : null;
  const squares = track ? startFinishSquares(track.start_finish) : [];

  return (
    <Panel label={label} className="track-map-panel">
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
            {pitLanePath && <path d={pitLanePath} className="track-map-pit-lane" />}
            <path d={mapPath} className="track-map-road" />
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
            {drivers.map((driver) => {
              const location = locations.get(driver.driver_number);
              if (!location) {
                return null;
              }
              const isSelected = driver.driver_number === selectedDriver?.driver_number;
              const markerStyle = {
                "--driver-colour": `#${driver.team_colour}`,
                transform: `translate(${location.map_x}px, ${location.map_y}px)`,
              } as CSSProperties;

              return (
                <g
                  key={driver.driver_number}
                  role="button"
                  tabIndex={0}
                  className={`track-map-marker ${isSelected ? "track-map-marker--selected" : ""}`}
                  aria-label={`${isSelected ? "Unselect" : "Select"} ${driver.acronym} marker`}
                  style={markerStyle}
                  onClick={() => onSelectDriver(driver.driver_number)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") onSelectDriver(driver.driver_number);
                  }}
                >
                  <circle className="track-map-marker-dot" cx={0} cy={0} />
                  <text className="track-map-marker-label" x={3} y={1}>
                    {driver.acronym}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      ) : (
        <div className="track-map-frame track-map-frame--unavailable">
          <div className="track-map-unavailable">
            <span className="track-map-unavailable-title">Circuit map unavailable</span>
            <span className="track-map-unavailable-copy">Track geometry is being rebuilt.</span>
          </div>
        </div>
      )}
    </Panel>
  );
}
