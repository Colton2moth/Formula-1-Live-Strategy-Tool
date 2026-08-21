import type { TrackPoint } from "../../types/race";

export type SvgPoint = { x: number; y: number };

export const VIEW_WIDTH = 100;
export const VIEW_HEIGHT = 85;
export const START_FINISH_SQUARE_SIZE = 1.2;

const START_FINISH_SQUARE_COUNT = 12;
const START_FINISH_COLUMN_COUNT = 3;
const START_FINISH_OUTSIDE_OFFSET = 6;

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
