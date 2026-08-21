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
| **Connecting to race server** | `/test/loading/connecting` | Initial page load before the first `fetch()` call completes. Shown while `Promise.all([fetchRaceState(), fetchTrack()])` is in flight. |
| **Loading race data** | `/test/loading/data` | Reserved for subsequent data refresh cycles where the connection is already established but new data is being fetched. Not currently used by `App.tsx`. |

## Error states

These screens replace the dashboard when an API call fails.

| Screen | Test link | Trigger condition |
|---|---|---|
| **API unavailable** | `/test/error/unavailable` | The `fetch()` call threw a network-level error before receiving any HTTP response. Typical causes: backend process is not running, wrong port, CORS misconfiguration, VPN required, or the machine is offline. |
| **Server error** | `/test/error/server-error` | The API returned a non-2xx HTTP status (e.g. 500, 503, 502). Typical causes: backend internal crash, upstream data provider outage, or backend middleware rejecting the request. |
| **Invalid data** | `/test/error/invalid-data` | The API returned HTTP 200 but the JSON body did not pass the frontend type assertion (`assertRaceState` or `assertTrackState`). Typical causes: backend schema change without a corresponding frontend update, or the API returned an unexpected payload (e.g. an HTML error page behind a 200 status). |
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

`useRaceData` automatically retries **503 Service Unavailable** responses with
exponential backoff (up to ~8 s), because a 503 normally means the backend is
still bootstrapping a live session. Retries finish before an error is surfaced,
and the final error reports the total attempt count. Any other error is surfaced
immediately and the user must refresh.

## How errors are classified

`classifyError()` (in `frontend/src/features/dashboard/useRaceData.ts`, used by
`App.tsx`) maps the structured `ApiError.type` to an error variant:

- `network` → `unavailable`
- `http` → `server-error`
- `invalid-data` → `invalid-data`
- `timeout` → `timeout`
- `unknown` → `server-error`

For genuinely unknown JavaScript errors it falls back to inspecting the message
string (`"Failed to fetch"` / `"NetworkError"` → `unavailable`, `"did not match
the expected shape"` → `invalid-data`, otherwise `server-error`).

## Test index

All test routes are listed at `/test`. The `/test/error/*` routes render each
error screen with realistic example diagnostic data so the details panel, copy
action, and field formatting can be verified in isolation without affecting
production requests.

[Back to Documentation](../README.md)
