# State Screens

The dashboard renders loading and error screens when the REST API is not
immediately available or returns unexpected responses. Each screen corresponds
to a specific failure mode in the data-fetching pipeline. Each screen has an
isolated test route so its production appearance can be verified in the
browser.

## Loading states

These screens appear while waiting for data to arrive. The three-dot pulse
animation indicates the app is actively working.

| Screen | Test link | Trigger condition |
|---|---|---|
| **Connecting to race server** | `/test/loading/connecting` | Initial page load before the critical `/api/race-state` snapshot has ever succeeded. Track loads in parallel but no longer blocks this screen. |
| **Loading race data** | `/test/loading/data` | Reserved for subsequent data refresh cycles where the connection is already established but new data is being fetched. Not currently used by `App.tsx`. |

## Error states

These screens appear only when the critical race snapshot cannot be established.
A non-critical resource failure (track data, or a live-transport interruption) no
longer replaces the dashboard; it degrades the affected surface instead while the
rest of the page keeps rendering last-known-good data.

| Screen | Test link | Trigger condition |
|---|---|---|
| **API unavailable** | `/test/error/unavailable` | The critical race-state `fetch()` threw a network-level error before receiving any HTTP response. Typical causes: backend process is not running, wrong port, CORS misconfiguration, VPN required, or the machine is offline. |
| **Server error** | `/test/error/server-error` | The critical race-state request returned a non-2xx HTTP status that is not retryable (e.g. 500, 502). Typical causes: backend internal crash, upstream data provider outage, or backend middleware rejecting the request. |
| **Invalid data** | `/test/error/invalid-data` | The critical race-state request returned HTTP 200 but the JSON body did not pass `assertRaceState`. Typical causes: backend schema change without a corresponding frontend update, or an unexpected payload behind a 200 status. |
| **Request timed out** | `/test/error/timeout` | Not currently triggered by the app (the `fetch()` wrapper has no built-in timeout). This screen exists for future use when a timeout mechanism is added, or when a wrapping load balancer / proxy returns a gateway timeout. |

## Structured error diagnostics

API errors are no longer reduced to a human-readable string. The request layer
(`frontend/src/api/raceState.ts`) throws a typed `ApiError` that preserves
structured diagnostic information at the moment the failure occurs, and that
structure survives the whole flow: `fetch()` → request helper → `useRaceData` →
`App` → `ErrorScreen`.

Where available, an `ApiError` captures:

- error category/type (`network`, `http`, `invalid-data`, `timeout`, or `unknown`)
- the original error message
- HTTP status code and status text
- HTTP method and endpoint path (e.g. `GET /api/race-state`)
- a safe backend `detail`/`message` from the response body
- an ISO timestamp
- the number of attempts made before the error surfaced

Network failures carry no fabricated HTTP status. Invalid-data failures retain
the successful HTTP status and the endpoint that produced the bad payload.

### Error details panel

Below the main error text, `ErrorScreen` renders a collapsed native
`<details>`/`<summary>` control labelled **Error details**. Expanding it shows a
compact, monospace diagnostic table with only the fields that actually exist.
Long values wrap and arbitrary response text is trimmed and capped, so a proxy
HTML error page is never dumped into the UI.

A **Copy error details** button copies a concise plain-text version of the same
fields for pasting into GitHub issues, ChatGPT, Discord, or bug reports.

Sensitive information is intentionally excluded: no authorization headers,
cookies, tokens, API keys, environment secrets, stack traces, or full request
headers are captured or displayed. Only the safe request path is shown, never a
full configured backend URL.

## Retry behaviour

`useRaceData` loads `/api/race-state` and `/api/track` concurrently but settles
them independently. Each resource retries **503 Service Unavailable** (and **409**
for replay sources) with capped exponential backoff (up to ~8 s), so a 503 on the
track endpoint no longer forces a retry of the race-state request and vice versa.
A 503 normally means the backend is still bootstrapping a live session. Retries
finish before an error is surfaced, and the final error reports the total attempt
count. Any other error is surfaced immediately.

Race state is the critical resource: only its failure (with no usable snapshot)
produces the full-page error screen, which now offers a **Try again** action that
re-runs the bootstrap without a page refresh. Track is non-critical: its failure
leaves the header, leaderboard, and strategy panel running while the track panel
shows a loading or unavailable state.

Live-transport recovery is separate from the bootstrap. When the WebSocket
reconnects, `useLiveState` resyncs `/api/race-state`; if that resync fails it
keeps the last valid data visible, marks it `stale`, and retries the resync with
capped backoff until it succeeds or the socket reconnects again.

## How errors are classified

`classifyError()` (in `frontend/src/features/dashboard/useRaceData.ts`) maps the
structured `ApiError.type` to an error variant. `App.tsx` applies it only to the
critical `raceStateError` to choose the fatal screen; `TrackMapPreviews` uses it
for its test screen.

- `network` → `unavailable`
- `http` → `server-error`
- `invalid-data` → `invalid-data`
- `timeout` → `timeout`
- `unknown` → `server-error`

For genuinely unknown JavaScript errors it falls back to inspecting the message
string (`"Failed to fetch"` / `"NetworkError"` → `unavailable`, `"did not match
the expected shape"` → `invalid-data`, otherwise `server-error`).

## Test index

All development test routes are listed at `/test`:

- **UI State Workbench** — `/test/states`
- **Loading states** — `/test/loading/connecting`, `/test/loading/data`
- **Error states** — `/test/error/unavailable`, `/test/error/server-error`, `/test/error/invalid-data`, `/test/error/timeout`
- **Track map previews** — `/test/maps`

These pages are only reachable by knowing the `/test` URL and are never linked
from the public dashboard.

## UI State Workbench

The `/test/states` page is a small component playground for the real production
state components. It is split into three sections:

1. **Error screens** — select from every error example (network, HTTP 400/404/429/
   500/502/503/504, invalid data, timeout, and the `unknown` type that maps to
   the server-error UI) or press **Show all** to see the four visual variants at
   once. A **Show retry button** toggle exercises the retry action with a dummy
   handler.
2. **Loading screens** — switch between the `connecting` and `loading` variants,
   or show both.
3. **Activity / loading toasts** — toggle every `ACTIVITY_MESSAGES` example,
   show multiple toasts at once, show all, clear one or all, and replay the
   entrance/exit animation. Toasts render in the real `ActivityToastStack` and
   stay visible until explicitly cleared.

The workbench reuses the real `ErrorScreen`, `LoadingScreen`, and
`ActivityToastStack` components with controlled, test-only `ApiError` fixtures
defined in `frontend/src/features/test-screens/errorExamples.ts`. It never calls
the backend, performs failing requests, or alters production error handling.

The page is intended to stay open while editing component styles: toasts and
error/loading previews remain selected, so changes to
`frontend/src/styles/activity-toasts.css` or `state-screens.css` update the
previews through Vite HMR without reloading or recreating a real error.

[Back to Documentation](../README.md)
