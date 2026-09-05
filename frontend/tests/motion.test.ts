import { test } from "node:test";
import assert from "node:assert/strict";

import {
  adaptiveLiveDelayMs,
  advanceSourceCursor,
  boundedExtrapolate,
  clamp,
  forwardDeltaFor,
  interpolateProgress,
  LIVE_MAX_DELAY_MS,
  LIVE_MIN_DELAY_MS,
  normalize,
  updateProgressRate,
  updateTimingStats,
  validateSample,
} from "../src/features/track-map/motion.ts";

function assertClose(actual: number, expected: number, epsilon = 1e-6): void {
  assert.ok(
    Math.abs(actual - expected) <= epsilon,
    `expected ${actual} to be within ${epsilon} of ${expected}`,
  );
}

test("interpolates between two timestamped samples", () => {
  const samples = [
    { sourceTimeMs: 0, progress: 0 },
    { sourceTimeMs: 1000, progress: 1 },
  ];
  assertClose(interpolateProgress(samples, 250) as number, 0.25);
  assertClose(interpolateProgress(samples, 0) as number, 0);
  assert.equal(interpolateProgress(samples, 1000), null);
  assert.equal(interpolateProgress(samples, -1), null);
  assert.equal(interpolateProgress([{ sourceTimeMs: 0, progress: 0.5 }], 100), null);
});

test("adaptive live delay stays within bounds", () => {
  assert.equal(adaptiveLiveDelayMs({ cadenceMs: 0, jitterMs: 0 }), LIVE_MIN_DELAY_MS);
  assert.equal(
    adaptiveLiveDelayMs({ cadenceMs: 100_000, jitterMs: 100_000 }),
    LIVE_MAX_DELAY_MS,
  );
  // Normal ~1 Hz feed lands in the 1-2 s range.
  const normal = adaptiveLiveDelayMs({ cadenceMs: 1000, jitterMs: 0 });
  assert.ok(normal >= 1000 && normal <= 2000, `expected ${normal} in [1000, 2000]`);
});

test("bursty delivery raises the adaptive delay", () => {
  const calm = adaptiveLiveDelayMs({ cadenceMs: 1000, jitterMs: 0 });
  const bursty = adaptiveLiveDelayMs({ cadenceMs: 1000, jitterMs: 800 });
  assert.ok(bursty > calm, `expected ${bursty} > ${calm}`);
  assert.ok(bursty <= LIVE_MAX_DELAY_MS);
});

test("timing stats smooth cadence and jitter", () => {
  let stats = { cadenceMs: 0, jitterMs: 0 };
  stats = updateTimingStats(stats, 1000);
  assertClose(stats.cadenceMs, 1000);
  assertClose(stats.jitterMs, 0);
  stats = updateTimingStats(stats, 1000);
  assertClose(stats.jitterMs, 0);
  // A burst gap raises jitter and shifts cadence.
  stats = updateTimingStats(stats, 2000);
  assertClose(stats.cadenceMs, 1300);
  assertClose(stats.jitterMs, 140);
});

test("progress rate is derived from source-time deltas", () => {
  const first = updateProgressRate(0, 0.1, 1000);
  assertClose(first, 0.0001);
  const second = updateProgressRate(first, 0.2, 1000);
  assertClose(second, 0.00014);
});

test("source cursor advances, clamps, and reports underrun", () => {
  // Initial cursor starts at the first sample and flags the empty buffer.
  const start = advanceSourceCursor(
    { sourceTimeMs: null, underrun: false },
    10_000,
    1000,
    1,
    16,
    10_000,
  );
  assert.deepEqual(start, { sourceTimeMs: 10_000, underrun: true });

  // Normal advance toward the safe maximum.
  const advancing = advanceSourceCursor(
    { sourceTimeMs: 5000, underrun: false },
    10_000,
    1000,
    1,
    16,
    0,
  );
  assert.deepEqual(advancing, { sourceTimeMs: 5016, underrun: false });

  // Clamped at the buffer edge.
  const clamped = advanceSourceCursor(
    { sourceTimeMs: 8950, underrun: false },
    10_000,
    1000,
    1,
    100,
    0,
  );
  assert.deepEqual(clamped, { sourceTimeMs: 9000, underrun: false });

  // The cursor never advances past a buffer that has no future samples.
  const underrun = advanceSourceCursor(
    { sourceTimeMs: 9500, underrun: false },
    10_000,
    1000,
    1,
    16,
    0,
  );
  assert.deepEqual(underrun, { sourceTimeMs: 9500, underrun: true });
});

test("bounded extrapolation respects time and distance limits", () => {
  // No rate: hold at the authoritative position (never below the visual).
  assertClose(
    boundedExtrapolate({ latestProgress: 0.5, progressRate: 0, elapsedMs: 1000, visualProgress: 0.5 }),
    0.5,
  );
  // Normal coast within the time limit.
  assertClose(
    boundedExtrapolate({ latestProgress: 0.5, progressRate: 0.00001, elapsedMs: 1000, visualProgress: 0.5 }),
    0.51,
  );
  // Time cap: only EXTRAPOLATE_MAX_MS of projection counts.
  assertClose(
    boundedExtrapolate({ latestProgress: 0.5, progressRate: 0.00001, elapsedMs: 10_000, visualProgress: 0.5 }),
    0.52,
  );
  // Distance cap dominates a fast rate.
  assertClose(
    boundedExtrapolate({ latestProgress: 0.5, progressRate: 0.001, elapsedMs: 1000, visualProgress: 0.5 }),
    0.54,
  );
});

test("extrapolation never moves backward past the visual position", () => {
  // Visual has already overshot; recovery holds instead of stepping back.
  const value = boundedExtrapolate({
    latestProgress: 0.5,
    progressRate: 0,
    elapsedMs: 0,
    visualProgress: 0.6,
  });
  assert.equal(value, 0.6);
});

test("start/finish wrapping resolves forward-only", () => {
  assertClose(forwardDeltaFor("track", 0.95, 0.05), 0.1);
  assertClose(forwardDeltaFor("track", 0.3, 0.4), 0.1);
  assertClose(forwardDeltaFor("track", 0.3, 0.3), 0);
  assertClose(forwardDeltaFor("pit_lane", 0.3, 0.5), 0.2);
  assertClose(forwardDeltaFor("pit_lane", 0.5, 0.3), -0.2);
});

test("normalize wraps arbitrary progress into [0, 1)", () => {
  assertClose(normalize(0.3), 0.3);
  assertClose(normalize(1.3), 0.3);
  assertClose(normalize(-0.2), 0.8);
  assertClose(normalize(1), 0);
});

test("sample validation rejects stale, duplicate, and out-of-order timestamps", () => {
  assert.equal(validateSample(null, 1000), "ok");
  assert.equal(validateSample(1000, 1000), "duplicate");
  assert.equal(validateSample(1000, 999), "out-of-order");
  assert.equal(validateSample(1000, 1001), "ok");
});

test("clamp bounds a value", () => {
  assert.equal(clamp(5, 0, 10), 5);
  assert.equal(clamp(-5, 0, 10), 0);
  assert.equal(clamp(15, 0, 10), 10);
});
