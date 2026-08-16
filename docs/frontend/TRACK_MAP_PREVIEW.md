# Track Map Previews

A developer-only page that renders every circuit map the application supports,
including each circuit's pit lane and start/finish marker, in one grid. Its job
is to make it fast to check SVG geometry without loading a live race.

## Access

- Local URL: `http://localhost:5173/test/maps`
- Deployed path: `/test/maps`

The page is intentionally **not linked** from the dashboard, replay page,
navigation, header, or footer. It is reachable only by entering the URL
directly (or from the `/test` index).

> A hidden route is not access control. Anyone who knows the deployed path can
> still open it. If the page must be hidden from deployed users, real
> authentication or a build-time guard is required; this page adds neither.

## What it displays

For each supported circuit, one card shows:

- the circuit name, country, and `circuit_key`
- the main circuit outline (closed path)
- the pit-lane centreline, when present, drawn in a distinct colour
- the start/finish marker (line + checkered squares)
- a pit-lane status chip: `available`, `missing`, or `invalid`
- a `start/finish: missing` note when the marker point is absent or invalid
- an `Unavailable: invalid circuit path` state when the outline is malformed

The page contains no live drivers, leaderboard, predictions, or weather — only
track geometry.

## Data source

The page reads the same geometry the dashboard uses, via a single request to
`GET /api/tracks`, which returns the full static circuit library from
`src/formula1_strategy_tool/api/circuits.py` with pit lanes merged from
`src/formula1_strategy_tool/api/pit_lanes.py` and country names from
`src/formula1_strategy_tool/api/countries.py`. It does not maintain its own
copy of the coordinates. Rendering reuses the transformation, smoothing, and
start/finish logic extracted into
`frontend/src/features/track-map/geometry.ts` (shared with the production
`TrackMap`).

Circuits currently without reviewed pit-lane data:

- 14 Autodromo Jose Carlos Pace (Interlagos)
- 55 Circuit Zandvoort
- 63 Bahrain International Circuit
- 149 Jeddah Corniche Circuit
- 150 Lusail International Circuit

## Using the page when editing geometry

1. Start the backend and frontend (see
   [development setup](../development/SETUP.md)).
2. Open `http://localhost:5173/test/maps`.
3. Confirm the outline is not clipped or distorted, the pit lane follows the
   track where it exists, and the start/finish marker sits on the outline.

When adding a circuit, regenerate the static library with
`scripts/generate_circuit_paths.py` and, if pit geometry is available,
`scripts/generate_pit_lanes.py`; the preview page picks the changes up on the
next request with no frontend edits.

[Back to Documentation](../README.md)
