import { useCallback, useEffect, useRef } from "react";
import type { DriverTrackProgress } from "../../hooks/useLiveState";
import type { TrackPoint, TrackRoute } from "../../types/race";
import { displayPathPoint, openPathPoint } from "./geometry";
import type { SvgPoint } from "./geometry";
import {
  adaptiveLiveDelayMs,
  advanceSourceCursor,
  boundedExtrapolate,
  forwardDeltaFor,
  interpolateProgress,
  LIVE_HISTORY_WINDOW_MS,
  normalize,
  updateProgressRate,
  updateTimingStats,
  validateSample,
} from "./motion";
import type { MotionSample, TimingStats } from "./motion";

export type MarkerAnimationMode =
  | { type: "live" }
  | { type: "replay"; speed: number; playing: boolean };

// Forward-motion continuity: incoming progress is normalized 0..1, so a
// long-gap sample can legitimately advance more than half a lap. Movement is
// resolved forward-only and rejected only when it implies a faster lap than
// MIN_PLAUSIBLE_LAP_MS — an anomaly guard, not a lap-time prediction model.
const MIN_PLAUSIBLE_LAP_MS = 30000;
const PROGRESS_GAP_SLACK = 0.05;

// Visual easing toward the computed target (shared by live and replay).
const SMOOTHING_TAU_MS = 75;
const SMOOTHING_MAX_FRAME_MS = 100;

// Replay renders from a deliberately buffered, monotonic source-time cursor
// instead of guessing. The buffer is race/source time (not wall time) and
// exceeds the ~3.4 s source gap observed between coalesced replay samples so a
// future bracketing sample normally exists.
const REPLAY_BUFFER_MS = 5000;
const REPLAY_HISTORY_WINDOW_MS = 10000;
const ROUTE_TRANSITION_MS = 750;
const PIT_VISUAL_MAX_PROGRESS_PER_MS = 0.0001;

// Development-only diagnostics are throttled per driver to avoid noise.
const DIAG_LOG_INTERVAL_MS = 5000;
const CORRECTION_LOG_THRESHOLD = 0.03;

type DriverMotion = {
  route: TrackRoute;
  samples: MotionSample[];
  visualProgress: number;
  authoritativeProgress: number;
  timing: TimingStats;
  progressRate: number;
  cursor: { sourceTimeMs: number | null; underrun: boolean };
  renderKind: "interpolate" | "extrapolate" | "hold";
  underrunSinceMs: number | null;
  lastDiagLogMs: number;
  lastPoint: SvgPoint | null;
  transition: { from: SvgPoint; startedAt: number } | null;
  pendingRoute: DriverMotion | null;
};

type ReplayClock = {
  sourceTimeMs: number | null;
  underrun: boolean;
};

function sampleHistory(samples: MotionSample[]): { sourceTimeMs: number; progress: number }[] {
  return samples.map((sample) => ({ sourceTimeMs: sample.sourceTimeMs, progress: sample.progress }));
}

type MotionLogKind =
  | "implausible"
  | "out-of-order"
  | "underrun"
  | "extrapolate"
  | "interpolate"
  | "timing"
  | "correction";

function motionLog(kind: MotionLogKind, payload: Record<string, unknown>): void {
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
    timing: { cadenceMs: 0, jitterMs: 0 },
    progressRate: 0,
    cursor: { sourceTimeMs: null, underrun: false },
    renderKind: "hold",
    underrunSinceMs: null,
    lastDiagLogMs: now,
    lastPoint: transitionFrom,
    transition: transitionFrom ? { from: transitionFrom, startedAt: now } : null,
    pendingRoute: null,
  };
}

function trimHistory(
  samples: MotionSample[],
  latestSourceTimeMs: number,
  windowMs: number | null,
): void {
  if (windowMs === null) {
    return;
  }
  const cutoff = latestSourceTimeMs - windowMs;
  while (samples.length > 1 && samples[0].sourceTimeMs < cutoff) {
    samples.shift();
  }
}

function advanceMotion(
  driverNumber: number,
  state: DriverMotion,
  progress: number,
  sourceTimeMs: number,
  historyWindowMs: number | null,
): void {
  const last = state.samples[state.samples.length - 1];
  const verdict = validateSample(last?.sourceTimeMs ?? null, sourceTimeMs);
  if (verdict === "out-of-order") {
    motionLog("out-of-order", {
      driverNumber,
      sourceTimeMs,
      previousSourceTimeMs: last?.sourceTimeMs ?? null,
      history: sampleHistory(state.samples),
    });
    return;
  }
  if (verdict === "duplicate") {
    return;
  }

  const previousProgress =
    state.route === "track" ? normalize(state.authoritativeProgress) : state.authoritativeProgress;
  const forwardDelta = forwardDeltaFor(state.route, previousProgress, progress);

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

  if (last && sourceGapMs > 0) {
    state.timing = updateTimingStats(state.timing, sourceGapMs);
    state.progressRate = updateProgressRate(state.progressRate, forwardDelta, sourceGapMs);
  }

  const newUnwrapped = state.authoritativeProgress + forwardDelta;
  state.samples.push({ sourceTimeMs, progress: newUnwrapped });
  trimHistory(state.samples, sourceTimeMs, historyWindowMs);
  state.authoritativeProgress = newUnwrapped;
}

function computeReplayTarget(state: DriverMotion, renderSourceTimeMs: number | null): number {
  if (renderSourceTimeMs === null) {
    return state.visualProgress;
  }
  const interp = interpolateProgress(state.samples, renderSourceTimeMs);
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

function advanceLiveCursor(
  state: DriverMotion,
  driverNumber: number,
  frameDeltaMs: number,
  now: number,
): void {
  const latest = state.samples[state.samples.length - 1];
  if (!latest) {
    return;
  }
  const first = state.samples[0];
  const bufferMs = adaptiveLiveDelayMs(state.timing);
  const next = advanceSourceCursor(
    state.cursor,
    latest.sourceTimeMs,
    bufferMs,
    1,
    frameDeltaMs,
    first.sourceTimeMs,
  );
  if (!state.cursor.underrun && next.underrun) {
    motionLog("underrun", {
      driverNumber,
      bufferMs: Math.round(bufferMs),
      cadenceMs: Math.round(state.timing.cadenceMs),
      jitterMs: Math.round(state.timing.jitterMs),
    });
  }
  state.cursor = next;
  if (next.underrun) {
    if (state.underrunSinceMs === null) {
      state.underrunSinceMs = now;
    }
  } else {
    state.underrunSinceMs = null;
  }
}

function computeLiveTarget(
  state: DriverMotion,
  now: number,
): { value: number; kind: "interpolate" | "extrapolate" | "hold" } {
  const latest = state.samples[state.samples.length - 1];
  if (!latest || state.cursor.sourceTimeMs === null) {
    return { value: state.visualProgress, kind: "hold" };
  }
  const interp = interpolateProgress(state.samples, state.cursor.sourceTimeMs);
  if (interp !== null) {
    return { value: interp, kind: "interpolate" };
  }
  const elapsedMs = state.underrunSinceMs === null ? 0 : now - state.underrunSinceMs;
  const extrapolated = boundedExtrapolate({
    latestProgress: latest.progress,
    progressRate: state.progressRate,
    elapsedMs,
    visualProgress: state.visualProgress,
  });
  return {
    value: extrapolated,
    kind: extrapolated <= state.visualProgress ? "hold" : "extrapolate",
  };
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
  const next = advanceSourceCursor(
    { sourceTimeMs: clock.sourceTimeMs, underrun: clock.underrun },
    latestSourceTimeMs,
    REPLAY_BUFFER_MS,
    speed,
    frameDeltaMs,
    0,
  );
  clock.sourceTimeMs = next.sourceTimeMs;
  setReplayUnderrun(clock, next.underrun);
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
    const historyWindowMs = modeRef.current.type === "replay" ? REPLAY_HISTORY_WINDOW_MS : LIVE_HISTORY_WINDOW_MS;
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
            advanceMotion(number, routeState, incomingProgress, sourceTimeMs, historyWindowMs);
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
        advanceMotion(number, state, incomingProgress, sourceTimeMs, historyWindowMs);
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
        -Math.min(frameDeltaMs, SMOOTHING_MAX_FRAME_MS) / SMOOTHING_TAU_MS,
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

        let target: number;
        if (mode.type === "replay") {
          target = computeReplayTarget(state, renderSourceTimeMs);
        } else {
          advanceLiveCursor(state, number, frameDeltaMs, now);
          const live = computeLiveTarget(state, now);
          if (state.renderKind !== live.kind) {
            if (live.kind === "extrapolate" || live.kind === "interpolate") {
              motionLog(live.kind, { driverNumber: number });
            }
            state.renderKind = live.kind;
          }
          if (now - state.lastDiagLogMs >= DIAG_LOG_INTERVAL_MS) {
            const bufferMs = adaptiveLiveDelayMs(state.timing);
            const correction = Math.abs(live.value - state.visualProgress);
            motionLog("timing", {
              driverNumber: number,
              cadenceMs: Math.round(state.timing.cadenceMs),
              jitterMs: Math.round(state.timing.jitterMs),
              bufferMs: Math.round(bufferMs),
              kind: live.kind,
              underrun: state.cursor.underrun,
            });
            if (correction > CORRECTION_LOG_THRESHOLD) {
              motionLog("correction", {
                driverNumber: number,
                delta: Number(correction.toFixed(4)),
              });
            }
            state.lastDiagLogMs = now;
          }
          target = live.value;
        }

        // Forward-only easing: unwrapped progress is monotonic, so a corrective
        // target that lags the visual position holds instead of moving backward.
        const rawDelta = (target - state.visualProgress) * alpha;
        const forwardDelta = Math.max(0, rawDelta);
        if (state.route === "pit_lane") {
          const speed = mode.type === "replay" ? mode.speed : 1;
          const maxDelta =
            PIT_VISUAL_MAX_PROGRESS_PER_MS *
            Math.min(frameDeltaMs, SMOOTHING_MAX_FRAME_MS) *
            speed;
          state.visualProgress += Math.min(maxDelta, forwardDelta);
        } else {
          state.visualProgress += forwardDelta;
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
