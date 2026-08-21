import type { TrackState } from "../../types/race";

export type SvgPoint = { x: number; y: number };
export type Bounds = { minX: number; minY: number; maxX: number; maxY: number };
export type Transform = { scale: number; offsetX: number; offsetY: number };

export type StartFinishSquare = {
  row: number;
  column: number;
  x: number;
  y: number;
  isLight: boolean;
};

export type TrackGeometry = {
  rotation: number;
  rawBounds: Bounds;
  transform: Transform;
  mapPath: string;
  pitLanePath: string | null;
  startFinish: SvgPoint | null;
  startFinishSquares: StartFinishSquare[];
  startFinishRotation: number;
};

export const VIEW_WIDTH = 100;
export const VIEW_HEIGHT = 85;
export const START_FINISH_SQUARE_SIZE = 1.2;

const PADDING = 6;
const START_FINISH_SQUARE_COUNT = 12;
const START_FINISH_COLUMN_COUNT = 3;
const START_FINISH_OUTSIDE_OFFSET = 6;

export function isPointValid(point: unknown): point is SvgPoint {
  if (typeof point !== "object" || point === null) {
    return false;
  }
  const candidate = point as { x?: unknown; y?: unknown };
  return (
    typeof candidate.x === "number" &&
    Number.isFinite(candidate.x) &&
    typeof candidate.y === "number" &&
    Number.isFinite(candidate.y)
  );
}

export function buildTrackGeometry(track: TrackState): TrackGeometry {
  const rotation = finiteRotation(track.rotation);
  const orientedPath = track.path.map((point) => applyOrientation(point, rotation));
  const orientedPitLane = (track.pit_lane ?? []).map((point) => applyOrientation(point, rotation));
  const rawBounds = boundsOf([...orientedPath, ...orientedPitLane]);
  const transform = buildTransform(rawBounds);
  const displayPoints = smoothTrackPoints(orientedPath.map((point) => applyTransform(point, transform)));
  const mapPath = trackPath(displayPoints);
  const pitLanePath =
    track.pit_lane && track.pit_lane.length > 1
      ? trackPath(orientedPitLane.map((point) => applyTransform(point, transform)))
      : null;
  const startFinish = isPointValid(track.start_finish)
    ? applyTransform(applyOrientation(track.start_finish, rotation), transform)
    : null;
  const startFinishSquares = startFinish ? startFinishMarkerSquares(startFinish) : [];
  const startFinishRotation = startFinish
    ? startFinishMarkerRotation(displayPoints, startFinish)
    : 0;

  return { rotation, rawBounds, transform, mapPath, pitLanePath, startFinish, startFinishSquares, startFinishRotation };
}

export function applyTransform(point: SvgPoint, transform: Transform): SvgPoint {
  return { x: point.x * transform.scale + transform.offsetX, y: point.y * transform.scale + transform.offsetY };
}

// FastF1 `CircuitInfo.rotation` is a counter-clockwise rotation in Y-up
// cartesian space. SVG is Y-down, so the rotated Y coordinate is negated to
// keep the circuit in the official F1 orientation.
export function applyOrientation(point: SvgPoint, rotationDeg: number): SvgPoint {
  const radians = (rotationDeg * Math.PI) / 180;
  const cos = Math.cos(radians);
  const sin = Math.sin(radians);
  return {
    x: point.x * cos - point.y * sin,
    y: -point.x * sin - point.y * cos,
  };
}

function finiteRotation(rotation: unknown): number {
  return typeof rotation === "number" && Number.isFinite(rotation) ? rotation : 0;
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
