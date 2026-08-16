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
| **API unavailable** | `/test/error/unavailable` | The `fetch()` call threw a network-level error before receiving any HTTP response. Typical causes: backend process is not running, wrong port, CORS misconfiguration, VPN required, or the machine is offline. The error message includes `"Failed to fetch"` or `"NetworkError"`. |
| **Server error** | `/test/error/server-error` | The API returned a non-2xx HTTP status (e.g. 500, 503, 502). The error message starts with `"Request failed: <status>"`. Typical causes: backend internal crash, upstream data provider outage, or backend middleware rejecting the request. |
| **Invalid data** | `/test/error/invalid-data` | The API returned HTTP 200 but the JSON body did not pass the frontend type assertion (`assertRaceState` or `assertTrackState`). The error message includes `"did not match the expected shape"`. Typical causes: backend schema change without a corresponding frontend update, or the API returned an unexpected payload (e.g. an HTML error page behind a 200 status). |
| **Request timed out** | `/test/error/timeout` | Not currently triggered by the app (the `fetch()` wrapper has no built-in timeout). This screen exists for future use when a timeout mechanism is added, or when a wrapping load balancer / proxy returns a gateway timeout. |

## Retry behaviour

`useRaceData` automatically retries **503 Service Unavailable** responses with
exponential backoff (up to ~8 s), because a 503 normally means the backend is
still bootstrapping a live session. Any other error is surfaced immediately and
the user must refresh.

## How errors are classified

The `classifyError()` function (in `frontend/src/features/dashboard/useRaceData.ts`,
used by `App.tsx`) inspects the caught error message string and maps it to one
of the error variants:

- `"Failed to fetch"` or `"NetworkError"` → `unavailable`
- `"Request failed:"` prefix → `server-error`
- `"did not match the expected shape"` → `invalid-data`
- Everything else → `server-error` (fallback)

## Test index

All test routes are listed at `/test`. Navigate there from the dashboard to
preview every loading and error screen in isolation.

[Back to Documentation](../README.md)
