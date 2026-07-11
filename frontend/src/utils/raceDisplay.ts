export const tyreColors: Record<string, string> = {
  HARD: "#f5f5f5",
  MEDIUM: "#ffd447",
  SOFT: "#ff3b3b",
  INTERMEDIATE: "#43d65d",
  WET: "#3a7dff",
};

export function formatLapTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remaining = (seconds - minutes * 60).toFixed(3).padStart(6, "0");
  return `${minutes}:${remaining}`;
}

export function formatGap(value: number | null) {
  if (value === null || value === 0) {
    return "Leader";
  }
  return `+${value.toFixed(3)}`;
}

export function formatUpdatedAt(value: string) {
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
