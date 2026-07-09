import { Panel } from "../../components/Panel";
import type { ApiDriver, TrackPoint, TrackState } from "../../types/race";

type TrackMapProps = {
  track: TrackState;
  drivers: ApiDriver[];
  selectedDriver: ApiDriver | null;
  onSelectDriver: (driverNumber: number) => void;
};

type SvgPoint = { x: number; y: number };

export function TrackMap({ track, drivers, selectedDriver, onSelectDriver }: TrackMapProps) {
  const centeredTrack = centerTrackPoints(track.path);
  const mapPath = trackPath(centeredTrack.points);
  const startFinish = applyCenterOffset(scalePoint(track.start_finish), centeredTrack);
  const selectedDriverLastName = selectedDriver ? driverLastName(selectedDriver.name).toUpperCase() : "NONE";

  return (
    <Panel label="Track map">
      <div className="track-map-frame">
        <svg viewBox="0 0 100 80" className="track-map-svg" role="img" aria-label={`${track.circuit_name} circuit map with selectable driver markers`}>
          <path d={mapPath} fill="none" stroke="var(--color-track)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          <path d={mapPath} fill="none" stroke="var(--color-panel-alt)" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" strokeOpacity="1" />
          <g aria-label="Start finish line">
            <rect x={startFinish.x - 1.2} y={startFinish.y - 3.2} width="1.2" height="1.6" fill="white" />
            <rect x={startFinish.x} y={startFinish.y - 3.2} width="1.2" height="1.6" fill="var(--color-bg)" />
            <rect x={startFinish.x - 1.2} y={startFinish.y - 1.6} width="1.2" height="1.6" fill="var(--color-bg)" />
            <rect x={startFinish.x} y={startFinish.y - 1.6} width="1.2" height="1.6" fill="white" />
          </g>
          {drivers.map((driver, index) => {
            const marker = markerPoint(centeredTrack.points, index, drivers.length);
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

function trackPath(points: SvgPoint[]) {
  if (points.length < 3) {
    return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  }

  const first = points[0];
  const last = points[points.length - 1];
  const isClosed = first.x === last.x && first.y === last.y;
  const pathPoints = isClosed ? points.slice(0, -1) : points;
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

function scalePoint(point: TrackPoint) {
  return { x: point.x * 100, y: point.y * 80 };
}

function centerTrackPoints(points: TrackPoint[]) {
  const scaledPoints = points.map(scalePoint);
  if (scaledPoints.length === 0) {
    return { points: scaledPoints, offsetX: 0, offsetY: 0 };
  }

  const bounds = boundsOf(scaledPoints);
  const offsetX = 50 - (bounds.minX + bounds.maxX) / 2;
  const offsetY = 40 - (bounds.minY + bounds.maxY) / 2;
  return {
    points: scaledPoints.map((point) => applyCenterOffset(point, { offsetX, offsetY })),
    offsetX,
    offsetY,
  };
}

function applyCenterOffset(point: SvgPoint, offset: { offsetX: number; offsetY: number }) {
  return { x: point.x + offset.offsetX, y: point.y + offset.offsetY };
}

function boundsOf(points: SvgPoint[]) {
  return points.reduce(
    (bounds, point) => ({
      minX: Math.min(bounds.minX, point.x),
      maxX: Math.max(bounds.maxX, point.x),
      minY: Math.min(bounds.minY, point.y),
      maxY: Math.max(bounds.maxY, point.y),
    }),
    { minX: points[0].x, maxX: points[0].x, minY: points[0].y, maxY: points[0].y },
  );
}

function markerPoint(points: SvgPoint[], index: number, total: number) {
  if (points.length === 0) {
    return { x: 50, y: 40 };
  }
  const pathIndex = Math.floor((index / Math.max(total, 1)) * (points.length - 1));
  const point = points[pathIndex] ?? points[0];
  return point;
}
