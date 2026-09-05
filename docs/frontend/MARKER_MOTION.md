# Driver-Marker Motion

How the frontend moves driver dots around the track map. Live and replay share
one rendering pipeline and differ only in their source-time cursor policy.

## Shared interpolation pipeline

Both modes render each driver from a history of authoritative, timestamped
samples. A `location_update` WebSocket event carries the projected `progress`,
`route`, `pit_lane_progress`, and the OpenF1 source `timestamp`; the frontend
turns this into a `DriverTrackProgress` entry (`sampleTimeMs` = parsed source
timestamp) and coalesces all entries into one state update per animation frame.

`useDriverMarkers` keeps, per driver, a bounded `MotionSample[]` history of
`{ sourceTimeMs, progress }` (progress unwrapped so lap wraps accumulate) and
renders an interpolated position against a source-time cursor. The pure math
lives in `frontend/src/features/track-map/motion.ts`:

- `interpolateProgress` — linear interpolation between the two samples that
  bracket the cursor.
- `advanceSourceCursor` — advances a cursor in source time, clamped to
  `latest - buffer`, and reports underrun.
- `updateTimingStats` / `adaptiveLiveDelayMs` — cadence + arrival jitter and
  the derived live buffer delay.
- `boundedExtrapolate` — time- and distance-limited forward projection.
- `forwardDeltaFor` / `validateSample` — start/finish wrap and stale/duplicate
  rejection.

Local monotonic time (`performance.now()`) is used only to advance the cursor;
epoch source timestamps are never compared directly with `performance.now()`.

## Live: adaptive jitter buffer

Live uses a **per-driver** source-time cursor advanced at rate 1 (source time
tracks wall time). The render delay is derived per driver from observed
cadence and arrival jitter:

```
delay = clamp(cadence * 1.5 + jitter * 1.5, 800 ms, 2500 ms)
```

A normal ~1 Hz feed (cadence ≈ 1000 ms, low jitter) renders ≈ 1.5 s behind
the latest sample — materially lower than replay's five-second buffer. Bursty
delivery raises the delay up to the 2500 ms ceiling without growing unbounded.
History is trimmed to a 6 s window, so memory stays bounded per driver.

## Replay: fixed buffer

Replay keeps its existing behaviour: one shared source-time cursor advanced at
`speed` and clamped to `latest - 5000 ms`, with a 10 s history window. All
drivers render from the same race-clock cursor.

## Underrun and correction

- Prefer interpolation between authoritative samples.
- On underrun (no future sample brackets the cursor), extrapolate forward from
  the latest sample using the smoothed progress rate, capped at 2000 ms and
  0.04 progress.
- When extrapolation reaches its cap, hold smoothly.
- When authoritative data resumes, the visual position eases toward the
  interpolated target and is clamped forward-only, so a corrective target that
  lags the extrapolated position holds rather than moving backward or
  teleporting.

## Development diagnostics

`useDriverMarkers` emits dev-only `[track-motion]` logs (gated on
`import.meta.env.DEV`):

- `out-of-order` / `implausible` — rejected stale or impossible samples.
- `underrun` — buffer-underflow transition.
- `extrapolate` / `interpolate` — render-mode transitions.
- `timing` — per-driver cadence, jitter, and selected buffer delay (throttled).
- `correction` — large authoritative corrections (throttled).

Production builds never log these.

## Testing

Pure timing math is covered by `frontend/tests/motion.test.ts`, run without any
frontend dependency via Node's built-in test runner:

```powershell
node --experimental-strip-types --test frontend/tests/motion.test.ts
```

Smoothness, pit-lane transitions, and reconnect recovery remain browser-only
checks (see `docs/TODO.md`).
