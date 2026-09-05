import type { TrackPoint } from "../../types/race";

export type SvgPoint = { x: number; y: number };

export const VIEW_WIDTH = 100;
export const VIEW_HEIGHT = 85;
export const START_FINISH_SQUARE_SIZE = 1.2;

const START_FINISH_SQUARE_COUNT = 12;
const START_FINISH_COLUMN_COUNT = 3;
const START_FINISH_OUTSIDE_OFFSET = 6;
const openPathMetrics = new WeakMap<TrackPoint[], { lengths: number[]; total: number }>();

export type StartFinishSquare = {
  row: number;
  column: number;
  x: number;
  y: number;
  isLight: boolean;
};

export function trackPath(points: TrackPoint[]): string {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");
}

export function displayPathPoint(points: TrackPoint[], progress: number): SvgPoint | null {
  if (!points.length) {
    return null;
  }
  const normalized = ((progress % 1) + 1) % 1;
  const position = normalized * points.length;
  const index = Math.floor(position) % points.length;
  const fraction = position - Math.floor(position);
  const a = points[index];
  const b = points[(index + 1) % points.length];
  return {
    x: a.x + (b.x - a.x) * fraction,
    y: a.y + (b.y - a.y) * fraction,
  };
}

export function openPathPoint(points: TrackPoint[], progress: number): SvgPoint | null {
  if (points.length < 2) {
    return points[0] ?? null;
  }
  let metrics = openPathMetrics.get(points);
  if (!metrics) {
    const lengths = points.slice(1).map((point, index) =>
      Math.hypot(point.x - points[index].x, point.y - points[index].y),
    );
    metrics = { lengths, total: lengths.reduce((sum, length) => sum + length, 0) };
    openPathMetrics.set(points, metrics);
  }
  const { lengths, total } = metrics;
  if (total === 0) {
    return points[0];
  }
  const target = Math.min(1, Math.max(0, progress)) * total;
  let travelled = 0;
  for (let index = 0; index < lengths.length; index += 1) {
    const length = lengths[index];
    if (target <= travelled + length || index === lengths.length - 1) {
      const fraction = length === 0 ? 0 : (target - travelled) / length;
      const a = points[index];
      const b = points[index + 1];
      return { x: a.x + (b.x - a.x) * fraction, y: a.y + (b.y - a.y) * fraction };
    }
    travelled += length;
  }
  return points[points.length - 1];
}

export function startFinishSquares(point: SvgPoint): StartFinishSquare[] {
  const squareCount = Math.max(
    2,
    START_FINISH_SQUARE_COUNT - (START_FINISH_SQUARE_COUNT % START_FINISH_COLUMN_COUNT),
  );
  const rowCount = squareCount / START_FINISH_COLUMN_COUNT;
  const markerLeft = point.x - START_FINISH_SQUARE_SIZE * (START_FINISH_COLUMN_COUNT / 2);
  const markerTop = point.y + START_FINISH_OUTSIDE_OFFSET;

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
