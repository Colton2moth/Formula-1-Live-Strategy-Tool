import { useMemo, type CSSProperties } from "react";
import { Panel } from "../../components/Panel";
import type { ApiDriver, ApiSession, TrackState } from "../../types/race";

type TrackMapProps = {
  track: TrackState;
  session: ApiSession;
  drivers: ApiDriver[];
  selectedDriver: ApiDriver | null;
  onSelectDriver: (driverNumber: number) => void;
};

type SvgPoint = { x: number; y: number };
type Bounds = { minX: number; minY: number; maxX: number; maxY: number };
type Transform = { scale: number; offsetX: number; offsetY: number };

const VIEW_WIDTH = 100;
const VIEW_HEIGHT = 85;
const PADDING = 6;

const START_FINISH_SQUARE_COUNT = 12;
const START_FINISH_SQUARE_SIZE = 1.2;
const START_FINISH_COLUMN_COUNT = 3;
const START_FINISH_OUTSIDE_OFFSET = 6;

function buildTrackGeometry(track: TrackState) {
  const rawBounds = boundsOf(track.path);
  const transform = buildTransform(rawBounds);
  const displayPoints = smoothTrackPoints(track.path.map((point) => applyTransform(point, transform)));
  const mapPath = trackPath(displayPoints);
  const startFinish = applyTransform(track.start_finish, transform);
  const startFinishSquares = startFinishMarkerSquares(startFinish);
  const startFinishRotation = startFinishMarkerRotation(displayPoints, startFinish);

  return { rawBounds, transform, mapPath, startFinish, startFinishSquares, startFinishRotation };
}

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
          {drivers.map((driver) => {
            if (driver.x === null || driver.y === null) {
              return null;
            }
            if (!isOnTrack({ x: driver.x, y: driver.y }, geometry.rawBounds)) {
              return null;
            }
            const marker = applyTransform({ x: driver.x, y: driver.y }, geometry.transform);
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

function buildTransform(bounds: Bounds): Transform {
  const width = Math.max(bounds.maxX - bounds.minX, 1);
  const height = Math.max(bounds.maxY - bounds.minY, 1);
  const scale = Math.min((VIEW_WIDTH - PADDING * 2) / width, (VIEW_HEIGHT - PADDING * 2) / height);
  return {
    scale,
    offsetX: (VIEW_WIDTH - width * scale) / 2 - bounds.minX * scale,
    offsetY: (VIEW_HEIGHT - height * scale) / 2 - bounds.minY * scale,
  };
}

function applyTransform(point: SvgPoint, transform: Transform): SvgPoint {
  return { x: point.x * transform.scale + transform.offsetX, y: point.y * transform.scale + transform.offsetY };
}

function boundsOf(points: SvgPoint[]): Bounds {
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

function clampProgress(progress: number) {
  return Math.min(Math.max(progress, 0), 1);
}

function distance(a: SvgPoint, b: SvgPoint) {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

function interpolate(a: SvgPoint, b: SvgPoint, progress: number) {
  return { x: a.x + (b.x - a.x) * progress, y: a.y + (b.y - a.y) * progress };
}
