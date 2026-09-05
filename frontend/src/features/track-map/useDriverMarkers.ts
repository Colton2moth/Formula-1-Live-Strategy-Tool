import { useCallback, useEffect, useRef } from "react";
import type { DriverTrackProgress } from "../../hooks/useLiveState";
import type { TrackPoint, TrackRoute } from "../../types/race";
import { displayPathPoint, openPathPoint } from "./geometry";
import type { SvgPoint } from "./geometry";

export type MarkerAnimationMode =
  | { type: "live" }
  | { type: "replay"; speed: number; playing: boolean };

// Cadence basis: cached replay location samples (2025 season) arrive at a
// median source gap of 0.24 s (~4 Hz); live streams at ~1 Hz. The render delay
// below is derived from the observed per-driver source cadence, not a fixed
// interval.
//
// Forward-motion continuity: incoming progress is normalized 0..1, so a
// long-gap sample can legitimately advance more than half a lap. Movement is
// resolved forward-only and rejected only when it implies a faster lap than
// MIN_PLAUSIBLE_LAP_MS — an anomaly guard, not a lap-time prediction model.
const MIN_PLAUSIBLE_LAP_MS = 30000;
const PROGRESS_GAP_SLACK = 0.05;
const NO_MOVEMENT_EPSILON = 1e-9;

// Fallback projection, used only by the live path when no future sample
// brackets the render time. Replay never projects.
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

// Replay renders from a deliberately buffered, monotonic source-time cursor
// instead of guessing. The buffer is race/source time (not wall time) and
// exceeds the ~3.4 s source gap observed between coalesced replay samples so a
// future bracketing sample normally exists. The history window covers the
// buffer plus the largest observed gap so the immediate predecessor sample is
// retained.
const REPLAY_BUFFER_MS = 5000;
const REPLAY_HISTORY_WINDOW_MS = 10000;
const ROUTE_TRANSITION_MS = 750;
const PIT_VISUAL_MAX_PROGRESS_PER_MS = 0.0001;

type Sample = {
  sourceTimeMs: number;
  progress: number;
};

type DriverMotion = {
  route: TrackRoute;
  samples: Sample[];
  visualProgress: number;
  authoritativeProgress: number;
  anchorTime: number;
  estimatedProgressRate: number;
  sampleIntervalMs: number;
  sourceRate: number | null;
  cadenceMs: number;
  lastPoint: SvgPoint | null;
  transition: { from: SvgPoint; startedAt: number } | null;
  pendingRoute: DriverMotion | null;
};

type ReplayClock = {
  sourceTimeMs: number | null;
  underrun: boolean;
};

function normalize(progress: number): number {
  const value = progress % 1;
  return value < 0 ? value + 1 : value;
}

function sampleHistory(samples: Sample[]): { sourceTimeMs: number; progress: number }[] {
  return samples.map((sample) => ({ sourceTimeMs: sample.sourceTimeMs, progress: sample.progress }));
}

function motionLog(kind: "implausible" | "out-of-order", payload: Record<string, unknown>): void {
  if (!import.meta.env.DEV) {
    return;
  }
  console.warn(`[track-motion] ${kind}`, payload);
}

function replayLog(kind: string, payload: Record<string, unknown>): void {
  if (!import.meta.env.DEV) {
    return;
  }
  console.warn(`[track-replay] ${kind}`, payload);
}

function activeProgress(entry: DriverTrackProgress): number | null {
  return entry.route === "pit_lane" ? entry.pitLaneProgress : entry.progress;
}

function routePoint(
  trackPath: TrackPoint[],
  pitLanePath: TrackPoint[],
  route: TrackRoute,
  progress: number,
): SvgPoint | null {
  return route === "pit_lane"
    ? openPathPoint(pitLanePath, progress)
    : displayPathPoint(trackPath, progress);
}

function createMotion(
  route: TrackRoute,
  progress: number,
  sourceTimeMs: number,
  now: number,
  transitionFrom: SvgPoint | null = null,
): DriverMotion {
  return {
    route,
    samples: [{ sourceTimeMs, progress }],
    visualProgress: progress,
    authoritativeProgress: progress,
    anchorTime: now,
    estimatedProgressRate: 0,
    sampleIntervalMs: 0,
    sourceRate: null,
    cadenceMs: 0,
    lastPoint: transitionFrom,
    transition: transitionFrom ? { from: transitionFrom, startedAt: now } : null,
    pendingRoute: null,
  };
}

function advanceMotion(
  driverNumber: number,
  state: DriverMotion,
  progress: number,
  now: number,
  sourceTimeMs: number,
  historyWindowMs: number | null,
): void {
  const last = state.samples[state.samples.length - 1];
  if (last && sourceTimeMs < last.sourceTimeMs) {
    motionLog("out-of-order", {
      driverNumber,
      sourceTimeMs,
      previousSourceTimeMs: last.sourceTimeMs,
      history: sampleHistory(state.samples),
    });
    return;
  }
  if (last && sourceTimeMs === last.sourceTimeMs) {
    return;
  }

  const previousProgress =
    state.route === "track" ? normalize(state.authoritativeProgress) : state.authoritativeProgress;
  const rawDiff = progress - previousProgress;
  const forwardDelta =
    Math.abs(rawDiff) < NO_MOVEMENT_EPSILON
      ? 0
      : state.route === "track"
        ? (rawDiff + 1) % 1
        : rawDiff;

  const sourceGapMs = last ? sourceTimeMs - last.sourceTimeMs : 0;
  const maxPlausible =
    state.route === "track"
      ? Math.min(1, sourceGapMs / MIN_PLAUSIBLE_LAP_MS + PROGRESS_GAP_SLACK)
      : 1;
  if (forwardDelta < 0 || forwardDelta > maxPlausible) {
    motionLog("implausible", {
      driverNumber,
      previousProgress: state.authoritativeProgress,
      incomingProgress: progress,
      forwardDelta,
      maxPlausible,
      sourceTimeMs,
      previousSourceTimeMs: last?.sourceTimeMs ?? null,
      history: sampleHistory(state.samples),
    });
    return;
  }

  if (last) {
    const localDelta = now - state.anchorTime;
    if (sourceGapMs > 0 && localDelta > 0) {
      const rate = sourceGapMs / localDelta;
      state.sourceRate =
        state.sourceRate === null
          ? rate
          : state.sourceRate * (1 - SOURCE_RATE_SMOOTHING) + rate * SOURCE_RATE_SMOOTHING;
      state.cadenceMs =
        state.cadenceMs === 0
          ? sourceGapMs
          : state.cadenceMs * (1 - CADENCE_SMOOTHING) + sourceGapMs * CADENCE_SMOOTHING;
    }
  }

  const newUnwrapped = state.authoritativeProgress + forwardDelta;
  state.samples.push({ sourceTimeMs, progress: newUnwrapped });
  if (historyWindowMs !== null) {
    const cutoff = sourceTimeMs - historyWindowMs;
    while (state.samples.length > 1 && state.samples[0].sourceTimeMs < cutoff) {
      state.samples.shift();
    }
  } else if (state.samples.length > MAX_HISTORY) {
    state.samples.shift();
  }

  if (forwardDelta === 0) {
    state.anchorTime = now;
    state.estimatedProgressRate = 0;
    return;
  }
  const elapsed = now - state.anchorTime;
  const instantRate = elapsed > 0 ? forwardDelta / elapsed : 0;
  state.estimatedProgressRate =
    state.estimatedProgressRate > 0
      ? state.estimatedProgressRate * (1 - RATE_SMOOTHING) + instantRate * RATE_SMOOTHING
      : instantRate;
  state.sampleIntervalMs =
    state.sampleIntervalMs > 0
      ? state.sampleIntervalMs * (1 - INTERVAL_SMOOTHING) + elapsed * INTERVAL_SMOOTHING
      : elapsed;
  state.authoritativeProgress = newUnwrapped;
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
      return a.progress + (b.progress - a.progress) * factor;
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

function computeLiveTarget(state: DriverMotion, now: number): number {
  const latest = state.samples[state.samples.length - 1];
  if (!latest || state.sourceRate === null) {
    return state.visualProgress;
  }
  const renderTimeMs =
    latest.sourceTimeMs + (now - state.anchorTime) * state.sourceRate - delayMs(state.cadenceMs);
  const interp = interpolate(state.samples, renderTimeMs);
  if (interp !== null) {
    return interp;
  }
  return projectTarget(state, now);
}

function computeReplayTarget(state: DriverMotion, renderSourceTimeMs: number | null): number {
  if (renderSourceTimeMs === null) {
    return state.visualProgress;
  }
  const interp = interpolate(state.samples, renderSourceTimeMs);
  if (interp !== null) {
    return interp;
  }
  const first = state.samples[0];
  const last = state.samples[state.samples.length - 1];
  if (!first || !last) {
    return state.visualProgress;
  }
  if (renderSourceTimeMs <= first.sourceTimeMs) {
    return first.progress;
  }
  return last.progress;
}

function setReplayUnderrun(clock: ReplayClock, underrun: boolean): void {
  if (clock.underrun === underrun) {
    return;
  }
  clock.underrun = underrun;
  replayLog(underrun ? "buffer-underrun" : "buffer-restored", {
    sourceTimeMs: clock.sourceTimeMs,
  });
}

function advanceReplayClock(
  clock: ReplayClock,
  latestSourceTimeMs: number | null,
  speed: number,
  playing: boolean,
  frameDeltaMs: number,
): void {
  if (!playing || latestSourceTimeMs === null) {
    return;
  }
  const safeMaximum = latestSourceTimeMs - REPLAY_BUFFER_MS;
  if (clock.sourceTimeMs === null) {
    clock.sourceTimeMs = Math.max(0, safeMaximum);
    setReplayUnderrun(clock, safeMaximum < 0);
    return;
  }
  if (safeMaximum < clock.sourceTimeMs) {
    setReplayUnderrun(clock, true);
    return;
  }
  setReplayUnderrun(clock, false);
  const desired = clock.sourceTimeMs + frameDeltaMs * speed;
  clock.sourceTimeMs = Math.min(desired, safeMaximum);
}

export function useDriverMarkers(
  displayPath: TrackPoint[],
  pitLanePath: TrackPoint[],
  progress: ReadonlyMap<number, DriverTrackProgress>,
  resetGeneration = 0,
  animationMode: MarkerAnimationMode = { type: "live" },
) {
  const displayPathRef = useRef(displayPath);
  displayPathRef.current = displayPath;

  const pitLanePathRef = useRef(pitLanePath);
  pitLanePathRef.current = pitLanePath;

  const progressRef = useRef(progress);
  progressRef.current = progress;

  const modeRef = useRef(animationMode);
  modeRef.current = animationMode;

  const statesRef = useRef<Map<number, DriverMotion>>(new Map());
  const elementsRef = useRef<Map<number, SVGGElement>>(new Map());
  const lastTransformRef = useRef<Map<number, string>>(new Map());
  const rafRef = useRef(0);
  const renderClockRef = useRef<ReplayClock>({ sourceTimeMs: null, underrun: false });
  const latestSourceTimeRef = useRef<number | null>(null);

  const resetGenerationRef = useRef(resetGeneration);
  useEffect(() => {
    if (resetGenerationRef.current === resetGeneration) {
      return;
    }
    resetGenerationRef.current = resetGeneration;
    statesRef.current.clear();
    renderClockRef.current = { sourceTimeMs: null, underrun: false };
    latestSourceTimeRef.current = null;
  }, [resetGeneration]);

  useEffect(() => {
    if (progress.size === 0) {
      statesRef.current.clear();
      renderClockRef.current = { sourceTimeMs: null, underrun: false };
      latestSourceTimeRef.current = null;
      return;
    }
    const now = performance.now();
    const states = statesRef.current;
    const historyWindowMs = modeRef.current.type === "replay" ? REPLAY_HISTORY_WINDOW_MS : null;
    let maxSourceTime = 0;
    for (const [number, entry] of progress) {
      const incomingProgress = activeProgress(entry);
      if (incomingProgress === null || !Number.isFinite(incomingProgress)) {
        continue;
      }
      const sourceTimeMs = entry.sampleTimeMs ?? now;
      if (sourceTimeMs > maxSourceTime) {
        maxSourceTime = sourceTimeMs;
      }
      const state = states.get(number);
      if (!state) {
        states.set(number, createMotion(entry.route, incomingProgress, sourceTimeMs, now));
      } else if (state.route !== entry.route) {
        const routeState = state.pendingRoute?.route === entry.route ? state.pendingRoute : null;
        const lastSample = (routeState ?? state).samples[(routeState ?? state).samples.length - 1];
        if (lastSample && sourceTimeMs <= lastSample.sourceTimeMs) {
          continue;
        }
        if (modeRef.current.type === "replay") {
          if (routeState) {
            advanceMotion(
              number,
              routeState,
              incomingProgress,
              now,
              sourceTimeMs,
              historyWindowMs,
            );
          } else {
            state.pendingRoute = createMotion(entry.route, incomingProgress, sourceTimeMs, now);
          }
        } else {
          const transitionFrom =
            state.lastPoint ??
            routePoint(
              displayPathRef.current,
              pitLanePathRef.current,
              state.route,
              state.visualProgress,
            );
          states.set(
            number,
            createMotion(entry.route, incomingProgress, sourceTimeMs, now, transitionFrom),
          );
        }
      } else {
        advanceMotion(number, state, incomingProgress, now, sourceTimeMs, historyWindowMs);
      }
    }
    if (maxSourceTime > 0) {
      latestSourceTimeRef.current =
        latestSourceTimeRef.current === null
          ? maxSourceTime
          : Math.max(latestSourceTimeRef.current, maxSourceTime);
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
      const pitPath = pitLanePathRef.current;
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
      const mode = modeRef.current;
      let renderSourceTimeMs: number | null = null;
      if (mode.type === "replay") {
        advanceReplayClock(
          renderClockRef.current,
          latestSourceTimeRef.current,
          mode.speed,
          mode.playing,
          frameDeltaMs,
        );
        renderSourceTimeMs = renderClockRef.current.sourceTimeMs;
      }
      const states = statesRef.current;
      const lastTransforms = lastTransformRef.current;
      for (const [number, element] of elements) {
        let state = states.get(number);
        if (!state) continue;
        const pending = state.pendingRoute;
        const pendingStart = pending?.samples[0]?.sourceTimeMs;
        if (
          mode.type === "replay" &&
          renderSourceTimeMs !== null &&
          pending &&
          pendingStart !== undefined &&
          renderSourceTimeMs >= pendingStart
        ) {
          const transitionFrom =
            state.lastPoint ?? routePoint(path, pitPath, state.route, state.visualProgress);
          pending.lastPoint = transitionFrom;
          pending.transition = transitionFrom ? { from: transitionFrom, startedAt: now } : null;
          states.set(number, pending);
          state = pending;
        }
        const target =
          mode.type === "replay"
            ? computeReplayTarget(state, renderSourceTimeMs)
            : computeLiveTarget(state, now);
        const visualDelta = (target - state.visualProgress) * alpha;
        if (state.route === "pit_lane") {
          const speed = mode.type === "replay" ? mode.speed : 1;
          const maxDelta =
            PIT_VISUAL_MAX_PROGRESS_PER_MS *
            Math.min(frameDeltaMs, PROJECTION_SMOOTHING_MAX_FRAME_MS) *
            speed;
          state.visualProgress += Math.min(maxDelta, Math.max(0, visualDelta));
        } else {
          state.visualProgress += visualDelta;
        }
        let point = routePoint(path, pitPath, state.route, state.visualProgress);
        if (!point) continue;
        if (state.transition) {
          const factor = Math.min(1, (now - state.transition.startedAt) / ROUTE_TRANSITION_MS);
          const eased = factor * factor * (3 - 2 * factor);
          point = {
            x: state.transition.from.x + (point.x - state.transition.from.x) * eased,
            y: state.transition.from.y + (point.y - state.transition.from.y) * eased,
          };
          if (factor >= 1) {
            state.transition = null;
          }
        }
        state.lastPoint = point;
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
            const entryProgress = activeProgress(entry);
            const point =
              entryProgress === null
                ? null
                : routePoint(
                    displayPathRef.current,
                    pitLanePathRef.current,
                    entry.route,
                    entryProgress,
                  );
            if (point) {
              element.style.transform = `translate(${point.x}px, ${point.y}px)`;
              const state = statesRef.current.get(driverNumber);
              if (state) state.lastPoint = point;
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
