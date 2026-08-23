import { useCallback, useEffect, useRef } from "react";
import type { DriverTrackProgress } from "../../hooks/useLiveState";
import type { TrackPoint } from "../../types/race";
import { displayPathPoint } from "./geometry";

const DISCONTINUITY_LAP_DELTA = 0.1;
const MIN_INTERPOLATION_MS = 1;
const MAX_INTERPOLATION_MS = 1000;

type MarkerAnim = {
  visual: number;
  target: number;
  confirmed: number;
  from: number;
  startTime: number;
  duration: number;
  lastArrival: number;
};

function normalize(progress: number): number {
  const value = progress % 1;
  return value < 0 ? value + 1 : value;
}

function unwrapDelta(progress: number, target: number): number {
  let delta = progress - normalize(target);
  if (delta > 0.5) delta -= 1;
  if (delta < -0.5) delta += 1;
  return delta;
}

function snapState(state: MarkerAnim, target: number, confirmed: number, now: number): void {
  state.visual = target;
  state.target = target;
  state.confirmed = confirmed;
  state.from = target;
  state.startTime = now;
  state.duration = 0;
  state.lastArrival = now;
}

export function useDriverMarkers(
  displayPath: TrackPoint[],
  progress: ReadonlyMap<number, DriverTrackProgress>,
) {
  const displayPathRef = useRef(displayPath);
  displayPathRef.current = displayPath;

  const progressRef = useRef(progress);
  progressRef.current = progress;

  const statesRef = useRef<Map<number, MarkerAnim>>(new Map());
  const elementsRef = useRef<Map<number, SVGGElement>>(new Map());
  const lastTransformRef = useRef<Map<number, string>>(new Map());
  const rafRef = useRef(0);

  useEffect(() => {
    if (progress.size === 0) {
      statesRef.current.clear();
      return;
    }
    const now = performance.now();
    const states = statesRef.current;
    for (const [number, entry] of progress) {
      const p = entry.progress;
      const state = states.get(number);
      if (!state) {
        states.set(number, {
          visual: p,
          target: p,
          confirmed: p,
          from: p,
          startTime: now,
          duration: 0,
          lastArrival: now,
        });
        continue;
      }
      if (state.confirmed === p) {
        continue;
      }
      const delta = unwrapDelta(p, state.target);
      if (delta < -DISCONTINUITY_LAP_DELTA || delta > DISCONTINUITY_LAP_DELTA) {
        snapState(state, state.target + delta, p, now);
        continue;
      }
      if (delta < 0) {
        continue;
      }
      state.from = state.visual;
      state.target = state.target + delta;
      state.confirmed = p;
      const interval = now - state.lastArrival;
      state.duration = Math.min(Math.max(interval, MIN_INTERPOLATION_MS), MAX_INTERPOLATION_MS);
      state.startTime = now;
      state.lastArrival = now;
    }
  }, [progress]);

  useEffect(() => {
    const frame = (now: number) => {
      rafRef.current = window.requestAnimationFrame(frame);

      const path = displayPathRef.current;
      if (!path.length) {
        return;
      }
      const elements = elementsRef.current;
      if (elements.size === 0) {
        return;
      }
      const states = statesRef.current;
      const lastTransforms = lastTransformRef.current;
      for (const [number, element] of elements) {
        const state = states.get(number);
        if (!state) continue;
        const elapsed = now - state.startTime;
        const t = state.duration > 0 ? Math.min(1, elapsed / state.duration) : 1;
        const visual = state.from + (state.target - state.from) * t;
        state.visual = visual;
        const point = displayPathPoint(path, visual);
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
        }
      };
      markerRefFactories.current.set(driverNumber, factory);
    }
    return factory;
  }, []);

  return { registerMarker };
}
