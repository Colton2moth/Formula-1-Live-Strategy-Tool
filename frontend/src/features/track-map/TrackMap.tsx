import { useMemo, type CSSProperties } from "react";
import { Panel } from "../../components/Panel";
import type { ApiDriver, ApiSession, TrackState } from "../../types/race";
import {
  applyOrientation,
  applyTransform,
  buildTrackGeometry,
  START_FINISH_SQUARE_SIZE,
  type Bounds,
  type SvgPoint,
} from "./geometry";

type TrackMapProps = {
  track: TrackState;
  session: ApiSession;
  drivers: ApiDriver[];
  selectedDriver: ApiDriver | null;
  onSelectDriver: (driverNumber: number) => void;
};

export function TrackMap({ track, session, drivers, selectedDriver, onSelectDriver }: TrackMapProps) {
  const geometry = useMemo(() => buildTrackGeometry(track), [track]);

  return (
    <Panel label={`${session.meeting_name.toUpperCase()} | ${track.circuit_name.toUpperCase()} | ${session.session_name.toUpperCase()}`} className="track-map-panel">
      <div className="track-map-frame">
        <svg
          viewBox="0 0 100 85"
          className="track-map-svg"
          role="img"
          aria-label={`${track.circuit_name} circuit map with selectable driver markers`}
        >
          <path d={geometry.mapPath} className="track-map-road" />
          {geometry.pitLanePath && <path d={geometry.pitLanePath} className="track-map-pit-lane" />}
          {geometry.startFinish && (
            <g
              aria-label="Start finish line"
              transform={`rotate(${geometry.startFinishRotation}, ${geometry.startFinish.x}, ${geometry.startFinish.y})`}
            >
              <line
                className="track-map-start-finish-line"
                x1={geometry.startFinish.x}
                x2={geometry.startFinish.x}
                y1={geometry.startFinish.y - START_FINISH_SQUARE_SIZE * 1.5}
                y2={geometry.startFinish.y + START_FINISH_SQUARE_SIZE * 1.5}
              />
              {geometry.startFinishSquares.map((square) => (
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
            if (driver.x === null || driver.y === null) {
              return null;
            }
            const oriented = applyOrientation({ x: driver.x, y: driver.y }, geometry.rotation);
            if (!isOnTrack(oriented, geometry.rawBounds)) {
              return null;
            }
            const marker = applyTransform(oriented, geometry.transform);
            const isSelected = driver.driver_number === selectedDriver?.driver_number;
            const markerStyle = {
              "--driver-colour": `#${driver.team_colour}`,
              transform: `translate(${marker.x}px, ${marker.y}px)`,
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
    </Panel>
  );
}

function isOnTrack(point: SvgPoint, bounds: Bounds) {
  const marginX = Math.max((bounds.maxX - bounds.minX) * 0.02, 1);
  const marginY = Math.max((bounds.maxY - bounds.minY) * 0.02, 1);
  return (
    point.x >= bounds.minX - marginX &&
    point.x <= bounds.maxX + marginX &&
    point.y >= bounds.minY - marginY &&
    point.y <= bounds.maxY + marginY
  );
}
