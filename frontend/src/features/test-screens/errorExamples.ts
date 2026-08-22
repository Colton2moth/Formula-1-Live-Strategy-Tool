import { ApiError } from "../../api/raceState";

export type ErrorPreset = {
  key: string;
  label: string;
  error: ApiError;
};

export const unavailableExample = new ApiError({
  type: "network",
  method: "GET",
  path: "/api/race-state",
  message: "Failed to fetch",
});

export const serverErrorExample = new ApiError({
  type: "http",
  method: "GET",
  path: "/api/race-state",
  message: "Request failed: 500",
  status: 500,
  statusText: "Internal Server Error",
  serverDetail: "Failed to build race snapshot",
  attempts: 4,
});

export const invalidDataExample = new ApiError({
  type: "invalid-data",
  method: "GET",
  path: "/api/race-state",
  message: "Race state response did not match the expected shape.",
  status: 200,
  statusText: "OK",
});

export const timeoutExample = new ApiError({
  type: "timeout",
  method: "GET",
  path: "/api/race-state",
  message: "The request did not complete within the configured time limit.",
});

const unknownExample = new ApiError({
  type: "unknown",
  message: "Unable to load race data.",
});

const longServerDetail =
  "The upstream provider returned an unexpected payload while resolving session metadata. " +
  "The response body contained an HTML error page that could not be parsed as JSON, and no " +
  "fallback value was available for the requested field. This usually happens when the data " +
  "provider is rate-limited or returns a maintenance page. Retry the request after a short " +
  "delay, or verify the configured API URL points at the correct environment.";

export const errorPresets: ErrorPreset[] = [
  { key: "unavailable", label: "API unavailable (network)", error: unavailableExample },
  {
    key: "server-400",
    label: "HTTP 400 Bad Request",
    error: new ApiError({
      type: "http",
      method: "GET",
      path: "/api/race-state",
      message: "Request failed: 400",
      status: 400,
      statusText: "Bad Request",
      serverDetail: "The request parameters were invalid.",
    }),
  },
  {
    key: "server-404",
    label: "HTTP 404 Not Found",
    error: new ApiError({
      type: "http",
      method: "GET",
      path: "/api/track",
      message: "Request failed: 404",
      status: 404,
      statusText: "Not Found",
    }),
  },
  {
    key: "server-429",
    label: "HTTP 429 Too Many Requests",
    error: new ApiError({
      type: "http",
      method: "GET",
      path: "/api/race-state",
      message: "Request failed: 429",
      status: 429,
      statusText: "Too Many Requests",
      serverDetail: longServerDetail,
      attempts: 7,
    }),
  },
  { key: "server-500", label: "HTTP 500 Internal Server Error", error: serverErrorExample },
  {
    key: "server-502",
    label: "HTTP 502 Bad Gateway",
    error: new ApiError({
      type: "http",
      method: "GET",
      path: "/api/track",
      message: "Request failed: 502",
      status: 502,
      statusText: "Bad Gateway",
      serverDetail: "The API gateway could not reach the upstream race service.",
    }),
  },
  {
    key: "server-503",
    label: "HTTP 503 Service Unavailable",
    error: new ApiError({
      type: "http",
      method: "GET",
      path: "/api/race-state",
      message: "Request failed: 503",
      status: 503,
      statusText: "Service Unavailable",
      serverDetail: "The live session is still bootstrapping.",
      attempts: 3,
    }),
  },
  {
    key: "server-504",
    label: "HTTP 504 Gateway Timeout",
    error: new ApiError({
      type: "http",
      method: "GET",
      path: "/api/race-state",
      message: "Request failed: 504",
      status: 504,
      statusText: "Gateway Timeout",
    }),
  },
  { key: "invalid-data", label: "Invalid API data (200 OK)", error: invalidDataExample },
  { key: "timeout", label: "Request timed out", error: timeoutExample },
  { key: "unknown", label: "Unknown error → server-error", error: unknownExample },
];

export const variantShowcases: ErrorPreset[] = [
  { key: "unavailable", label: "API unavailable", error: unavailableExample },
  { key: "server-error", label: "Server error", error: serverErrorExample },
  { key: "invalid-data", label: "Invalid data", error: invalidDataExample },
  { key: "timeout", label: "Request timed out", error: timeoutExample },
];
