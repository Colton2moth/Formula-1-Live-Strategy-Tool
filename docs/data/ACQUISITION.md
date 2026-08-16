# Data Acquisition

Where raw historical data comes from and how it is downloaded and stored. The
processed ML dataset schema lives in [DRIVER_LAP_SCHEMA.md](./DRIVER_LAP_SCHEMA.md).

## Source

Historical data comes from the free [OpenF1](https://openf1.org) REST API.
Downloads are grouped as one endpoint × one session (for example `laps` for
session `9165`, `weather` for session `9165`).

## What is downloaded

Year-level metadata, one file each:

- `meetings.json`
- `sessions.json`

Per completed Race session, the following strategy-relevant endpoints:

- `drivers`
- `laps`
- `stints`
- `pit`
- `position`
- `intervals`
- `weather`
- `race_control`
- `starting_grid`
- `session_result`
- `overtakes`

Not downloaded (too large / not needed for the first models):

- historical `location`
- historical `car_data`

Only completed **Race** sessions are downloaded: Sprints, qualifying, and
practice are excluded, and a session must have ended at least two hours ago
(`SESSION_COMPLETION_BUFFER`) so incomplete data is not pulled.

## Storage

```text
data/
└── raw/
    └── <year>/
        ├── meetings.json
        ├── sessions.json
        └── sessions/
            └── <meeting>_<session>_<country>_<name>/
                ├── session.json
                ├── laps.json
                ├── stints.json
                └── ...
```

The session folder name encodes `meeting_key`, `session_key`, `country_name`,
and `session_name` (for example `1229_9472_bahrain_race`). Raw responses are
stored unchanged so they can be re-processed without another API request.

## Downloader behaviour

The bulk downloader (`f1-download-openf1`, `src/formula1_strategy_tool/acquisition/`):

- respects OpenF1 rate limits;
- retries temporary failures;
- skips files that already exist (resumable);
- writes responses atomically;
- records failed downloads to `data/raw/download_errors.jsonl`;
- continues past a failed endpoint so one bad session does not stop the run.

Re-running the same command retries only what failed. No database is used at
this stage.

## First validation

Before downloading everything:

1. Download one race.
2. Inspect each returned file.
3. Confirm row counts and important fields.
4. Process that race manually.
5. Expand to all races only after the structure is understood.
