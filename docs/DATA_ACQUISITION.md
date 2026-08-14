# Data Acquisition

## Historical endpoints

Download:

- meetings
- sessions
- drivers
- laps
- stints
- pit
- position
- intervals
- weather
- race_control
- starting_grid
- session_result
- overtakes

Do not download historical `location` or `car_data` initially.

## Download unit

Use:

```text
one endpoint × one session
```

Example:

```text
laps for session 9165
weather for session 9165
```

## Storage

```text
data/
└── raw/
    └── 2023/
        └── sessions/
            └── <session>/
                ├── session.json
                ├── laps.json
                ├── stints.json
                └── ...
```

## Downloader requirements

The downloader should:

- respect OpenF1 rate limits;
- retry temporary failures;
- skip files that already exist;
- save responses atomically;
- record failed downloads;
- remain resumable.

Do not add a database at this stage.

## First validation

Before downloading everything:

1. Download one race.
2. Inspect each returned file.
3. Confirm row counts and important fields.
4. Process that race manually.
5. Expand to all races only after the structure is understood.
