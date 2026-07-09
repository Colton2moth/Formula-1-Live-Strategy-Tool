import { Panel } from "../../components/Panel";
import type { ApiDriver, TrackPoint, TrackState } from "../../types/race";

type TrackMapProps = {
  track: TrackState;
  drivers: ApiDriver[];
  selectedDriver: ApiDriver | null;
  onSelectDriver: (driverNumber: number) => void;
};

type SvgPoint = { x: number; y: number };

const START_FINISH_SQUARE_COUNT = 8;
const START_FINISH_SQUARE_SIZE = 1.2;
const START_FINISH_COLUMN_COUNT = 2;
const START_FINISH_OUTSIDE_OFFSET = 6;

export function TrackMap({ track, drivers, selectedDriver, onSelectDriver }: TrackMapProps) {
  const centeredTrack = centerTrackPoints(track.path);
  const displayPoints = smoothTrackPoints(centeredTrack.points);
  const mapPath = trackPath(displayPoints);
  const startFinish = applyCenterOffset(scalePoint(track.start_finish), centeredTrack);
  const startFinishSquares = startFinishMarkerSquares(startFinish);
  const startFinishRotation = startFinishMarkerRotation(displayPoints, startFinish);
  const selectedDriverLastName = selectedDriver ? driverLastName(selectedDriver.name).toUpperCase() : "NONE";

  return (
    <Panel label="Track map">
      <div className="track-map-frame">
        <svg
          viewBox="0 0 100 80"
          className="track-map-svg"
          role="img"
          aria-label={`${track.circuit_name} circuit map with selectable driver markers`}
        >
          <path
            d={mapPath}
            fill="none"
            stroke="var(--color-track)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d={mapPath}
            fill="none"
            stroke="var(--color-panel-alt)"
            strokeWidth="1"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeOpacity="1"
          />
          <g
            aria-label="Start finish line"
            transform={`rotate(${startFinishRotation}, ${startFinish.x}, ${startFinish.y})`}
          >
            <line
              x1={startFinish.x}
              x2={startFinish.x}
              y1={startFinish.y - START_FINISH_SQUARE_SIZE * 1.5}
              y2={startFinish.y + START_FINISH_SQUARE_SIZE * 1.5}
              stroke="var(--color-f1-red)"
              strokeWidth="1"
              strokeLinecap="square"
            />
            {startFinishSquares.map((square) => (
              <rect
                key={`${square.row}-${square.column}`}
                className="track-map-start-finish-square"
                x={square.x}
                y={square.y}
                width={START_FINISH_SQUARE_SIZE}
                height={START_FINISH_SQUARE_SIZE}
                fill={square.isLight ? "white" : "var(--color-bg)"}
              />
            ))}
          </g>
          {drivers.map((driver) => {
            const marker = pointAtTrackProgress(displayPoints, driver.track_progress);
            const isSelected = driver.driver_number === selectedDriver?.driver_number;
            return (
              <g
                key={driver.driver_number}
                role="button"
                tabIndex={0}
                className="track-map-marker"
                aria-label={`${isSelected ? "Unselect" : "Select"} ${driver.acronym} marker`}
                onClick={() => onSelectDriver(driver.driver_number)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") onSelectDriver(driver.driver_number);
                }}
              >
                <circle
                  cx={marker.x}
                  cy={marker.y}
                  r={isSelected ? 2.4 : 2}
                  fill={`#${driver.team_colour}`}
                  stroke={isSelected ? "white" : "var(--color-bg)"}
                  strokeWidth="0.8"
                />
                <text x={marker.x + 3.2} y={marker.y + 1} fill="white" fontSize="3.2" fontWeight="700">
                  {driver.acronym}
                </text>
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

function startFinishMarkerSquares(startFinish: SvgPoint) {
  const squareCount = evenSquareCount(START_FINISH_SQUARE_COUNT);
  const rowCount = squareCount / START_FINISH_COLUMN_COUNT;
  const markerLeft = startFinish.x - START_FINISH_SQUARE_SIZE * (START_FINISH_COLUMN_COUNT / 2);
  const markerTop = startFinish.y + START_FINISH_OUTSIDE_OFFSET;

  return Array.from({ length: squareCount }, (_, index) => {
    const row = Math.floor(index / START_FINISH_COLUMN_COUNT);
    const column = index % START_FINISH_COLUMN_COUNT;
    return {
      row,
      column,
      x: markerLeft + column * START_FINISH_SQUARE_SIZE,
      y: markerTop + row * START_FINISH_SQUARE_SIZE - (rowCount * START_FINISH_SQUARE_SIZE) / 2,
      isLight: (row + column) % 2 === 0,
    };
  });
}

function evenSquareCount(squareCount: number) {
  return Math.max(2, squareCount - (squareCount % START_FINISH_COLUMN_COUNT));
}

function startFinishMarkerRotation(points: SvgPoint[], startFinish: SvgPoint) {
  const segment = nearestSegment(points, startFinish);
  if (!segment) {
    return 0;
  }

  return radiansToDegrees(Math.atan2(segment.end.y - segment.start.y, segment.end.x - segment.start.x));
}

function nearestSegment(points: SvgPoint[], point: SvgPoint) {
  let nearest: { start: SvgPoint; end: SvgPoint; distance: number } | null = null;

  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    if (distance(start, end) === 0) {
      continue;
    }

    const projected = projectPointToSegment(point, start, end);
    const projectedDistance = distance(point, projected);
    if (!nearest || projectedDistance < nearest.distance) {
      nearest = { start, end, distance: projectedDistance };
    }
  }

  return nearest;
}

function projectPointToSegment(point: SvgPoint, start: SvgPoint, end: SvgPoint) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const segmentLengthSquared = dx * dx + dy * dy;
  if (segmentLengthSquared === 0) {
    return start;
  }

  const progress = clampProgress(((point.x - start.x) * dx + (point.y - start.y) * dy) / segmentLengthSquared);
  return { x: start.x + dx * progress, y: start.y + dy * progress };
}

function radiansToDegrees(radians: number) {
  return (radians * 180) / Math.PI;
}
function driverLastName(name: string) {
  return name.trim().split(/\s+/).pop() ?? name;
}

function trackPath(points: SvgPoint[]) {
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
}

function smoothTrackPoints(points: SvgPoint[]) {
  if (points.length < 4) {
    return points;
  }

  let smoothed = points;
  for (let pass = 0; pass < 5; pass += 1) {
    smoothed = smoothTrackPass(smoothed);
  }

  return smoothed;
}

function smoothTrackPass(points: SvgPoint[]) {
  const isClosed = samePoint(points[0], points[points.length - 1]);
  const pathPoints = isClosed ? points.slice(0, -1) : points;
  if (pathPoints.length < 3) {
    return points;
  }

  const smoothed: SvgPoint[] = [pathPoints[0]];
  const finalIndex = isClosed ? pathPoints.length : pathPoints.length - 1;
  for (let index = 0; index < finalIndex; index += 1) {
    const current = pathPoints[index];
    const next = pathPoints[(index + 1) % pathPoints.length];
    smoothed.push(interpolate(current, next, 0.225), interpolate(current, next, 0.75));
  }

  smoothed.push(isClosed ? pathPoints[0] : pathPoints[pathPoints.length - 1]);
  return smoothed;
}

function samePoint(a: SvgPoint, b: SvgPoint) {
  return a.x === b.x && a.y === b.y;
}

function pointAtTrackProgress(points: SvgPoint[], progress: number) {
  if (points.length === 0) {
    return { x: 50, y: 40 };
  }
  if (points.length === 1) {
    return points[0];
  }

  const totalLength = pathLength(points);
  if (totalLength === 0) {
    return points[0];
  }

  let remainingDistance = totalLength * clampProgress(progress);
  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    const segmentLength = distance(start, end);
    if (remainingDistance <= segmentLength) {
      return interpolate(start, end, remainingDistance / segmentLength);
    }
    remainingDistance -= segmentLength;
  }

  return points[points.length - 1];
}

function clampProgress(progress: number) {
  return Math.min(Math.max(progress, 0), 1);
}

function pathLength(points: SvgPoint[]) {
  return points.slice(1).reduce((total, point, index) => total + distance(points[index], point), 0);
}

function distance(a: SvgPoint, b: SvgPoint) {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

function interpolate(a: SvgPoint, b: SvgPoint, progress: number) {
  return { x: a.x + (b.x - a.x) * progress, y: a.y + (b.y - a.y) * progress };
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
