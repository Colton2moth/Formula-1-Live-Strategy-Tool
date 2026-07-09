import { Panel } from "../../components/Panel";
import type { ApiDriver, TrackPoint, TrackState } from "../../types/race";

type TrackMapProps = {
  track: TrackState;
  drivers: ApiDriver[];
  selectedDriver: ApiDriver | null;
  onSelectDriver: (driverNumber: number) => void;
};

export function TrackMap({ track, drivers, selectedDriver, onSelectDriver }: TrackMapProps) {
  const mapPath = trackPath(track.path);
  const selectedDriverLastName = selectedDriver ? driverLastName(selectedDriver.name).toUpperCase() : "NONE";

  return (
    <Panel label="Track map">
      <div className="track-map-frame">
        <svg viewBox="0 0 100 80" className="track-map-svg" role="img" aria-label={`${track.circuit_name} circuit map with selectable driver markers`}>
          <path d={mapPath} fill="none" stroke="var(--color-track)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
          <path d={mapPath} fill="none" stroke="var(--color-f1-red)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="7 9" />
          {drivers.map((driver, index) => {
            const marker = markerPoint(track.path, index, drivers.length);
            const isSelected = driver.driver_number === selectedDriver?.driver_number;
            return (
              <g key={driver.driver_number} role="button" tabIndex={0} className="track-map-marker" aria-label={`${isSelected ? "Unselect" : "Select"} ${driver.acronym} marker`} onClick={() => onSelectDriver(driver.driver_number)} onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") onSelectDriver(driver.driver_number);
              }}>
                <circle cx={marker.x} cy={marker.y} r={isSelected ? 2.4 : 2} fill={`#${driver.team_colour}`} stroke={isSelected ? "white" : "var(--color-bg)"} strokeWidth="0.8" />
                <text x={marker.x + 3.2} y={marker.y + 1} fill="white" fontSize="3.2" fontWeight="700">{driver.acronym}</text>
              </g>
            );
          })}
        </svg>
        <div className="track-map-selected-chip">
          <span className="track-map-selected-label">Selected </span>
          <span className="track-map-selected-value">{selectedDriverLastName}</span>
        </div>
      </div>
    </Panel>
  );
}

function driverLastName(name: string) {
  return name.trim().split(/\s+/).pop() ?? name;
}

function trackPath(points: TrackPoint[]) {
  const scaledPoints = points.map((point) => ({ x: point.x * 100, y: point.y * 80 }));
  if (scaledPoints.length < 3) {
    return scaledPoints.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  }

  const first = scaledPoints[0];
  const last = scaledPoints[scaledPoints.length - 1];
  const isClosed = first.x === last.x && first.y === last.y;
  const pathPoints = isClosed ? scaledPoints.slice(0, -1) : scaledPoints;
  const start = isClosed ? midpoint(pathPoints[pathPoints.length - 1], pathPoints[0]) : pathPoints[0];
  const segments = [`M ${start.x} ${start.y}`];

  pathPoints.forEach((point, index) => {
    const next = pathPoints[index + 1];
    if (!next) return;
    const end = midpoint(point, next);
    segments.push(`Q ${point.x} ${point.y} ${end.x} ${end.y}`);
  });

  if (isClosed) {
    const end = midpoint(pathPoints[pathPoints.length - 1], pathPoints[0]);
    segments.push(`Q ${pathPoints[pathPoints.length - 1].x} ${pathPoints[pathPoints.length - 1].y} ${end.x} ${end.y}`);
  }

  return segments.join(" ");
}

function midpoint(a: { x: number; y: number }, b: { x: number; y: number }) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

function markerPoint(points: TrackPoint[], index: number, total: number) {
  if (points.length === 0) {
    return { x: 50, y: 40 };
  }
  const pathIndex = Math.floor((index / Math.max(total, 1)) * (points.length - 1));
  const point = points[pathIndex] ?? points[0];
  return { x: point.x * 100, y: point.y * 80 };
}
