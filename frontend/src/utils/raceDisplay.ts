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

export function formatGap(value: number | string | null) {
  if (value === null) {
    return "Leader";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? `+${value.toFixed(3)}` : "Unknown";
  }
  if (typeof value === "string") {
    if (value === "UNKNOWN") {
      return "Unknown";
    }
    if (/^\+\d+\s+LAPS?$/i.test(value.trim())) {
      return value.trim().toUpperCase();
    }
    return "Unknown";
  }
  return "Unknown";
}

export function formatUpdatedAt(value: string) {
  const updatedAt = new Date(value);
  const hours = String(updatedAt.getHours()).padStart(2, "0");
  const minutes = String(updatedAt.getMinutes()).padStart(2, "0");
  const seconds = String(updatedAt.getSeconds()).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}
