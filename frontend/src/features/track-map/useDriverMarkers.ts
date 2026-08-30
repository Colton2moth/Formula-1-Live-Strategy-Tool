import { useCallback, useEffect, useRef } from "react";
import type { DriverTrackProgress } from "../../hooks/useLiveState";
import type { TrackPoint } from "../../types/race";
import { displayPathPoint } from "./geometry";

// Cadence basis: cached replay location samples (2025 season) arrive at a
// median gap of 0.24 s (~4 Hz), p90 0.38 s, p95 0.42 s, p99 0.52 s, with the
// longest normal gap ~1.9 s, no gaps over 2 s, and effectively no duplicate
// timestamps. Live location streams at ~1 Hz. The backend caps each accepted
// update at 2% of a lap and suppresses backwards corrections under 0.5%.
const DISCONTINUITY_LAP_DELTA = 0.1;
const PROJECTION_MAX_MS = 1500;
const PROJECTION_LEAD_SAMPLES = 1.5;
const PROJECTION_MAX_DELTA = 0.02;
const PROJECTION_SMOOTHING_TAU_MS = 75;
const PROJECTION_SMOOTHING_MAX_FRAME_MS = 100;
const RATE_SMOOTHING = 0.4;
const REANCHOR_GAP_MS = 2000;
const INTERVAL_SMOOTHING = 0.2;

type DriverMotion = {
  authoritativeProgress: number;
  anchorTime: number;
  visualProgress: number;
  previousProgress: number | null;
  previousTime: number | null;
  estimatedProgressRate: number;
  sampleIntervalMs: number;
  lastSampleTime: number;
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

function createMotion(progress: number, now: number): DriverMotion {
  return {
    authoritativeProgress: progress,
    anchorTime: now,
    visualProgress: progress,
    previousProgress: null,
    previousTime: null,
    estimatedProgressRate: 0,
    sampleIntervalMs: 0,
    lastSampleTime: now,
  };
}

function resetMotion(state: DriverMotion, progress: number, now: number): void {
  state.authoritativeProgress = progress;
  state.anchorTime = now;
  state.visualProgress = progress;
  state.previousProgress = null;
  state.previousTime = null;
  state.estimatedProgressRate = 0;
  state.sampleIntervalMs = 0;
  state.lastSampleTime = now;
}

function advanceMotion(state: DriverMotion, progress: number, now: number): void {
  const delta = unwrapDelta(progress, state.authoritativeProgress);
  if (delta === 0) {
    state.anchorTime = now;
    state.lastSampleTime = now;
    state.estimatedProgressRate = 0;
    return;
  }
  if (delta < 0 || delta > DISCONTINUITY_LAP_DELTA) {
    resetMotion(state, state.authoritativeProgress + delta, now);
    return;
  }
  const sinceLastSample = now - state.lastSampleTime;
  if (sinceLastSample > REANCHOR_GAP_MS) {
    resetMotion(state, state.authoritativeProgress + delta, now);
    return;
  }
  const elapsed = now - state.anchorTime;
  state.previousProgress = state.authoritativeProgress;
  state.previousTime = state.anchorTime;
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
  state.lastSampleTime = now;
}

function projectMotion(state: DriverMotion, now: number, frameDeltaMs: number): void {
  const alpha = 1 - Math.exp(
    -Math.min(frameDeltaMs, PROJECTION_SMOOTHING_MAX_FRAME_MS) / PROJECTION_SMOOTHING_TAU_MS,
  );
  const rate = state.estimatedProgressRate;
  const elapsed = now - state.anchorTime;
  let target = state.authoritativeProgress;
  if (rate > 0 && elapsed > 0) {
    const timeDelta = rate * Math.min(elapsed, PROJECTION_MAX_MS);
    const lead = Math.min(
      rate * state.sampleIntervalMs * PROJECTION_LEAD_SAMPLES,
      PROJECTION_MAX_DELTA,
    );
    target = state.authoritativeProgress + Math.min(timeDelta, lead);
  }
  state.visualProgress += (target - state.visualProgress) * alpha;
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
      const state = states.get(number);
      if (!state) {
        states.set(number, createMotion(entry.progress, now));
      } else {
        advanceMotion(state, entry.progress, now);
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
      const states = statesRef.current;
      const lastTransforms = lastTransformRef.current;
      for (const [number, element] of elements) {
        const state = states.get(number);
        if (!state) continue;
        projectMotion(state, now, frameDeltaMs);
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
