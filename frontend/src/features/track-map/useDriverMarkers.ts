import { useCallback, useEffect, useRef } from "react";
import type { DriverTrackProgress } from "../../hooks/useLiveState";
import type { TrackPoint } from "../../types/race";
import { displayPathPoint } from "./geometry";

// Cadence basis: cached replay location samples (2025 season) arrive at a
// median source gap of 0.24 s (~4 Hz); live streams at ~1 Hz. The render delay
// below is derived from the observed per-driver source cadence, not a fixed
// interval.
const DISCONTINUITY_LAP_DELTA = 0.1;
const NO_MOVEMENT_EPSILON = 1e-9;

// Fallback projection, used only when no future sample brackets the render time.
const PROJECTION_MAX_MS = 3000;
const PROJECTION_LEAD_SAMPLES = 2.5;
const PROJECTION_MAX_DELTA = 0.04;
const PROJECTION_SMOOTHING_TAU_MS = 75;
const PROJECTION_SMOOTHING_MAX_FRAME_MS = 100;
const RATE_SMOOTHING = 0.4;
const INTERVAL_SMOOTHING = 0.2;

// Delayed two-sample interpolation.
const MAX_HISTORY = 4;
const DELAY_FACTOR = 1.0;
const MIN_DELAY_MS = 80;
const MAX_DELAY_MS = 2000;
const SOURCE_RATE_SMOOTHING = 0.3;
const CADENCE_SMOOTHING = 0.3;

type Sample = {
  sourceTimeMs: number;
  progress: number;
};

type DriverMotion = {
  samples: Sample[];
  visualProgress: number;
  authoritativeProgress: number;
  anchorTime: number;
  estimatedProgressRate: number;
  sampleIntervalMs: number;
  sourceRate: number | null;
  cadenceMs: number;
};

function normalize(progress: number): number {
  const value = progress % 1;
  return value < 0 ? value + 1 : value;
}

function unwrapDelta(progress: number, authoritativeProgress: number): number {
  let delta = progress - normalize(authoritativeProgress);
  if (delta > 0.5) delta -= 1;
  if (delta < -0.5) delta += 1;
  return delta;
}

function createMotion(progress: number, sourceTimeMs: number, now: number): DriverMotion {
  return {
    samples: [{ sourceTimeMs, progress }],
    visualProgress: progress,
    authoritativeProgress: progress,
    anchorTime: now,
    estimatedProgressRate: 0,
    sampleIntervalMs: 0,
    sourceRate: null,
    cadenceMs: 0,
  };
}

function resetProgress(
  state: DriverMotion,
  progress: number,
  sourceTimeMs: number,
  now: number,
): void {
  state.samples = [{ sourceTimeMs, progress }];
  state.visualProgress = progress;
  state.authoritativeProgress = progress;
  state.anchorTime = now;
  state.estimatedProgressRate = 0;
  state.sampleIntervalMs = 0;
}

function advanceMotion(
  state: DriverMotion,
  progress: number,
  now: number,
  sourceTimeMs: number,
): void {
  const last = state.samples[state.samples.length - 1];
  if (last && sourceTimeMs <= last.sourceTimeMs) {
    return;
  }
  if (last) {
    const srcDelta = sourceTimeMs - last.sourceTimeMs;
    const localDelta = now - state.anchorTime;
    if (srcDelta > 0 && localDelta > 0) {
      const rate = srcDelta / localDelta;
      state.sourceRate =
        state.sourceRate === null
          ? rate
          : state.sourceRate * (1 - SOURCE_RATE_SMOOTHING) + rate * SOURCE_RATE_SMOOTHING;
      state.cadenceMs =
        state.cadenceMs === 0
          ? srcDelta
          : state.cadenceMs * (1 - CADENCE_SMOOTHING) + srcDelta * CADENCE_SMOOTHING;
    }
  }
  state.samples.push({ sourceTimeMs, progress });
  if (state.samples.length > MAX_HISTORY) {
    state.samples.shift();
  }

  const delta = unwrapDelta(progress, state.authoritativeProgress);
  if (Math.abs(delta) < NO_MOVEMENT_EPSILON) {
    state.anchorTime = now;
    state.estimatedProgressRate = 0;
    return;
  }
  if (delta < 0 || delta > DISCONTINUITY_LAP_DELTA) {
    resetProgress(state, progress, sourceTimeMs, now);
    return;
  }
  const elapsed = now - state.anchorTime;
  const instantRate = elapsed > 0 ? delta / elapsed : 0;
  state.estimatedProgressRate =
    state.estimatedProgressRate > 0
      ? state.estimatedProgressRate * (1 - RATE_SMOOTHING) + instantRate * RATE_SMOOTHING
      : instantRate;
  state.sampleIntervalMs =
    state.sampleIntervalMs > 0
      ? state.sampleIntervalMs * (1 - INTERVAL_SMOOTHING) + elapsed * INTERVAL_SMOOTHING
      : elapsed;
  state.authoritativeProgress += delta;
  state.anchorTime = now;
}

function delayMs(cadenceMs: number): number {
  return Math.min(MAX_DELAY_MS, Math.max(MIN_DELAY_MS, cadenceMs * DELAY_FACTOR));
}

function interpolate(samples: Sample[], renderTimeMs: number): number | null {
  for (let i = 0; i < samples.length; i += 1) {
    if (samples[i].sourceTimeMs > renderTimeMs) {
      const b = samples[i];
      const a = i > 0 ? samples[i - 1] : null;
      if (!a) {
        return null;
      }
      const span = b.sourceTimeMs - a.sourceTimeMs;
      if (span <= 0) {
        return null;
      }
      const factor = Math.min(1, Math.max(0, (renderTimeMs - a.sourceTimeMs) / span));
      return a.progress + unwrapDelta(b.progress, a.progress) * factor;
    }
  }
  return null;
}

function projectTarget(state: DriverMotion, now: number): number {
  const rate = state.estimatedProgressRate;
  const elapsed = now - state.anchorTime;
  if (rate <= 0 || elapsed <= 0) {
    return state.authoritativeProgress;
  }
  const timeDelta = rate * Math.min(elapsed, PROJECTION_MAX_MS);
  const lead = Math.min(
    rate * state.sampleIntervalMs * PROJECTION_LEAD_SAMPLES,
    PROJECTION_MAX_DELTA,
  );
  return state.authoritativeProgress + Math.min(timeDelta, lead);
}

function computeTarget(state: DriverMotion, now: number): number {
  const latest = state.samples[state.samples.length - 1];
  if (!latest || state.sourceRate === null) {
    return state.visualProgress;
  }
  const renderTimeMs =
    latest.sourceTimeMs + (now - state.anchorTime) * state.sourceRate - delayMs(state.cadenceMs);
  const interp = interpolate(state.samples, renderTimeMs);
  if (interp !== null) {
    return state.visualProgress + unwrapDelta(interp, state.visualProgress);
  }
  return projectTarget(state, now);
}

export function useDriverMarkers(
  displayPath: TrackPoint[],
  progress: ReadonlyMap<number, DriverTrackProgress>,
  resetGeneration = 0,
) {
  const displayPathRef = useRef(displayPath);
  displayPathRef.current = displayPath;

  const progressRef = useRef(progress);
  progressRef.current = progress;

  const statesRef = useRef<Map<number, DriverMotion>>(new Map());
  const elementsRef = useRef<Map<number, SVGGElement>>(new Map());
  const lastTransformRef = useRef<Map<number, string>>(new Map());
  const rafRef = useRef(0);

  const resetGenerationRef = useRef(resetGeneration);
  useEffect(() => {
    if (resetGenerationRef.current === resetGeneration) {
      return;
    }
    resetGenerationRef.current = resetGeneration;
    statesRef.current.clear();
  }, [resetGeneration]);

  useEffect(() => {
    if (progress.size === 0) {
      statesRef.current.clear();
      return;
    }
    const now = performance.now();
    const states = statesRef.current;
    for (const [number, entry] of progress) {
      if (!Number.isFinite(entry.progress)) {
        continue;
      }
      const sourceTimeMs = entry.sampleTimeMs ?? now;
      const state = states.get(number);
      if (!state) {
        states.set(number, createMotion(entry.progress, sourceTimeMs, now));
      } else {
        advanceMotion(state, entry.progress, now, sourceTimeMs);
      }
    }
    for (const number of states.keys()) {
      if (!progress.has(number)) {
        states.delete(number);
      }
    }
  }, [progress]);

  useEffect(() => {
    let prevFrameTime = 0;
    const frame = () => {
      rafRef.current = window.requestAnimationFrame(frame);

      const path = displayPathRef.current;
      if (!path.length) {
        return;
      }
      const elements = elementsRef.current;
      if (elements.size === 0) {
        return;
      }
      const now = performance.now();
      const frameDeltaMs = prevFrameTime > 0 ? now - prevFrameTime : 0;
      prevFrameTime = now;
      const alpha = 1 - Math.exp(
        -Math.min(frameDeltaMs, PROJECTION_SMOOTHING_MAX_FRAME_MS) / PROJECTION_SMOOTHING_TAU_MS,
      );
      const states = statesRef.current;
      const lastTransforms = lastTransformRef.current;
      for (const [number, element] of elements) {
        const state = states.get(number);
        if (!state) continue;
        const target = computeTarget(state, now);
        state.visualProgress += (target - state.visualProgress) * alpha;
        const point = displayPathPoint(path, state.visualProgress);
        if (!point) continue;
        const transform = `translate(${point.x}px, ${point.y}px)`;
        if (lastTransforms.get(number) !== transform) {
          lastTransforms.set(number, transform);
          element.style.transform = transform;
        }
      }
    };

    rafRef.current = window.requestAnimationFrame(frame);
    return () => window.cancelAnimationFrame(rafRef.current);
  }, []);

  const markerRefFactories = useRef<Map<number, (element: SVGGElement | null) => void>>(new Map());

  const registerMarker = useCallback((driverNumber: number) => {
    let factory = markerRefFactories.current.get(driverNumber);
    if (!factory) {
      factory = (element: SVGGElement | null) => {
        if (element) {
          elementsRef.current.set(driverNumber, element);
          const entry = progressRef.current.get(driverNumber);
          if (entry) {
            const point = displayPathPoint(displayPathRef.current, entry.progress);
            if (point) {
              element.style.transform = `translate(${point.x}px, ${point.y}px)`;
            }
          }
        } else {
          elementsRef.current.delete(driverNumber);
          lastTransformRef.current.delete(driverNumber);
          statesRef.current.delete(driverNumber);
        }
      };
      markerRefFactories.current.set(driverNumber, factory);
    }
    return factory;
  }, []);

  return { registerMarker };
}
