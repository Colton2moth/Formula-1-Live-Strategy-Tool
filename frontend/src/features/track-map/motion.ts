// Pure timing and interpolation helpers for driver-marker motion.
//
// Live and replay both render each driver from a history of authoritative,
// timestamped samples. This module holds the dependency-free math (no React,
// no `import.meta`, no DOM) so it can be unit-tested in isolation.

export type MotionSample = {
  sourceTimeMs: number;
  progress: number;
};

export type TimingStats = {
  cadenceMs: number;
  jitterMs: number;
};

export type SourceCursor = {
  sourceTimeMs: number | null;
  underrun: boolean;
};

// Live adaptive-buffer policy. A normal ~1 Hz live feed (cadence ~1000 ms,
// low jitter) lands around 1.5 s of render delay; bursty delivery pushes it up
// to LIVE_MAX_DELAY_MS without ever growing unbounded. This stays well below
// replay's fixed five-second buffer.
export const LIVE_MIN_DELAY_MS = 800;
export const LIVE_MAX_DELAY_MS = 2500;
export const LIVE_DELAY_FACTOR = 1.5;
export const LIVE_JITTER_GAIN = 1.5;
export const LIVE_HISTORY_WINDOW_MS = 6000;

// Bounded extrapolation used only when the live buffer genuinely underruns.
export const EXTRAPOLATE_MAX_MS = 2000;
export const EXTRAPOLATE_MAX_DELTA = 0.04;

const CADENCE_SMOOTHING = 0.3;
const JITTER_SMOOTHING = 0.2;
const RATE_SMOOTHING = 0.4;

export const NO_MOVEMENT_EPSILON = 1e-9;

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function normalize(progress: number): number {
  const value = progress % 1;
  return value < 0 ? value + 1 : value;
}

export function forwardDeltaFor(
  route: "track" | "pit_lane",
  previousProgress: number,
  progress: number,
): number {
  const rawDiff = progress - previousProgress;
  if (Math.abs(rawDiff) < NO_MOVEMENT_EPSILON) {
    return 0;
  }
  return route === "track" ? (rawDiff + 1) % 1 : rawDiff;
}

export type SampleVerdict = "ok" | "duplicate" | "out-of-order";

export function validateSample(
  previousSourceTimeMs: number | null,
  sourceTimeMs: number,
): SampleVerdict {
  if (previousSourceTimeMs === null) {
    return "ok";
  }
  if (sourceTimeMs < previousSourceTimeMs) {
    return "out-of-order";
  }
  if (sourceTimeMs === previousSourceTimeMs) {
    return "duplicate";
  }
  return "ok";
}

export function updateTimingStats(
  stats: TimingStats,
  sourceGapMs: number,
): TimingStats {
  if (sourceGapMs <= 0) {
    return stats;
  }
  const cadenceMs =
    stats.cadenceMs === 0
      ? sourceGapMs
      : stats.cadenceMs * (1 - CADENCE_SMOOTHING) + sourceGapMs * CADENCE_SMOOTHING;
  const deviation = Math.abs(sourceGapMs - cadenceMs);
  const jitterMs =
    stats.jitterMs * (1 - JITTER_SMOOTHING) + deviation * JITTER_SMOOTHING;
  return { cadenceMs, jitterMs };
}

export function adaptiveLiveDelayMs(stats: TimingStats): number {
  const raw =
    stats.cadenceMs * LIVE_DELAY_FACTOR + stats.jitterMs * LIVE_JITTER_GAIN;
  return clamp(raw, LIVE_MIN_DELAY_MS, LIVE_MAX_DELAY_MS);
}

export function updateProgressRate(
  prevRate: number,
  delta: number,
  sourceGapMs: number,
): number {
  if (sourceGapMs <= 0) {
    return prevRate;
  }
  const instant = delta / sourceGapMs;
  return prevRate <= 0
    ? instant
    : prevRate * (1 - RATE_SMOOTHING) + instant * RATE_SMOOTHING;
}

export function interpolateProgress(
  samples: readonly MotionSample[],
  sourceTimeMs: number,
): number | null {
  for (let i = 0; i < samples.length; i += 1) {
    if (samples[i].sourceTimeMs > sourceTimeMs) {
      const b = samples[i];
      const a = i > 0 ? samples[i - 1] : null;
      if (!a) {
        return null;
      }
      const span = b.sourceTimeMs - a.sourceTimeMs;
      if (span <= 0) {
        return null;
      }
      const factor = clamp((sourceTimeMs - a.sourceTimeMs) / span, 0, 1);
      return a.progress + (b.progress - a.progress) * factor;
    }
  }
  return null;
}

export function advanceSourceCursor(
  cursor: SourceCursor,
  latestSourceTimeMs: number,
  bufferMs: number,
  rate: number,
  frameDeltaMs: number,
  minSourceTimeMs: number,
): SourceCursor {
  const safeMaximum = latestSourceTimeMs - bufferMs;
  if (cursor.sourceTimeMs === null) {
    const start = Math.max(minSourceTimeMs, safeMaximum);
    return { sourceTimeMs: start, underrun: safeMaximum < minSourceTimeMs };
  }
  if (safeMaximum < cursor.sourceTimeMs) {
    return { sourceTimeMs: cursor.sourceTimeMs, underrun: true };
  }
  const desired = cursor.sourceTimeMs + Math.max(0, frameDeltaMs) * rate;
  return { sourceTimeMs: Math.min(desired, safeMaximum), underrun: false };
}

export function boundedExtrapolate(opts: {
  latestProgress: number;
  progressRate: number;
  elapsedMs: number;
  visualProgress: number;
}): number {
  const { latestProgress, progressRate, elapsedMs, visualProgress } = opts;
  if (progressRate <= 0) {
    return Math.max(latestProgress, visualProgress);
  }
  const cappedElapsed = clamp(elapsedMs, 0, EXTRAPOLATE_MAX_MS);
  const extrapolated = latestProgress + progressRate * cappedElapsed;
  const ceiling = latestProgress + EXTRAPOLATE_MAX_DELTA;
  const target = Math.min(extrapolated, ceiling);
  // Never move backward around the track while recovering from extrapolation.
  return Math.max(target, visualProgress);
}
