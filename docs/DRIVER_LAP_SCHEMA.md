# Driver-lap schema (wide v1)

Approved target for the processed training table.

**Grain:** one row = one driver at the end of one completed lap.

**Philosophy:** build a wide leakage-safe table from OpenF1 endpoints we already have; choose model feature subsets later.

**Reference race for first implementation:** 2024 Bahrain  
`data/raw/2024/sessions/1229_9472_bahrain_race/`

See also: [TWO_MODEL_ARCHITECTURE.md](TWO_MODEL_ARCHITECTURE.md), [DECISIONS.md](DECISIONS.md).

---

## A. Identifiers (not model features)

| Column | Source |
|--------|--------|
| `season` | year / session date |
| `meeting_key` | session / laps |
| `session_key` | session / laps |
| `circuit_key` | session |
| `circuit_short_name` | session |
| `country_name` | session |
| `driver_number` | laps |
| `team_name` | drivers |
| `lap_number` | laps |
| `date_start` | laps |

---

## B. Race state

| Column | Notes |
|--------|--------|
| `total_laps` | max lap in session (or metadata) |
| `laps_remaining` | `total_laps - lap_number` |
| `race_progress` | `lap_number / total_laps` |
| `current_position` | as-of join from `position` |
| `number_of_pit_stops` | pits with `lap_number <= current` |
| `laps_since_last_pit` | from pit history |
| `current_stint_number` | from `stints` |
| `is_pit_out_lap` | from `laps` |

---

## C. Tyre / stint

| Column | Notes |
|--------|--------|
| `current_compound` | stint covering this lap |
| `tyre_age` | from stint `tyre_age_at_start` + laps into stint |
| `stint_length` | laps so far in current stint |
| `compounds_used_so_far` | distinct compounds up to now |
| `has_used_soft` | flag |
| `has_used_medium` | flag |
| `has_used_hard` | flag |
| `has_used_intermediate` | flag |
| `has_used_wet` | flag |
| `has_used_two_dry_compounds` | soft/medium/hard history |
| `previous_compound` | prior stint |

---

## D. Pace (trailing windows only)

| Column | Notes |
|--------|--------|
| `current_lap_time` | `lap_duration` |
| `previous_lap_time` | lag within driver |
| `rolling_mean_lap_time_3` | trailing |
| `rolling_mean_lap_time_5` | trailing |
| `rolling_median_lap_time_3` | trailing |
| `pace_delta_to_recent_average` | current − rolling mean |
| `pace_delta_to_stint_best` | current − best in stint so far |
| `duration_sector_1` | from laps |
| `duration_sector_2` | from laps |
| `duration_sector_3` | from laps |

---

## E. Gaps / traffic

| Column | Notes |
|--------|--------|
| `gap_to_leader` | as-of from `intervals` |
| `interval_ahead` | as-of from `intervals` |
| `interval_behind` | include if cleanly derivable; else null |

---

## F. Weather (as-of)

| Column | Notes |
|--------|--------|
| `air_temperature` | weather |
| `track_temperature` | weather |
| `humidity` | weather |
| `rainfall` | weather |
| `wind_speed` | weather |
| `track_temperature_trend` | optional delta vs earlier sample |

---

## G. Race control

| Column | Notes |
|--------|--------|
| `safety_car_active` | derived from `race_control` |
| `virtual_safety_car_active` | derived |
| `yellow_flag_active` | derived |
| `red_flag_recent` | derived (rule TBD at implementation) |

---

## H. Season / regulations

| Column | Notes |
|--------|--------|
| `is_2026_regulations` | `season >= 2026` |
| `race_number_within_season` | optional from meetings order |

---

## I. Labels

| Column | Notes |
|--------|--------|
| `pit_within_3_laps` | 0/1 — pit model 3 |
| `pit_within_5_laps` | 0/1 — pit model 5 |
| `pit_within_7_laps` | 0/1 — pit model 7 |
| `next_compound` | SOFT…WET or null if no future stop |
| `next_pit_lap` | debug helper; not a model feature |

---

## Out of scope for this table

- Telemetry summaries (`car_data` not downloaded)
- Hand-wavy track scores (pit-lane loss, overtaking difficulty)
- `starting_grid` (unavailable from API)

---

## Model usage (later)

- **Pit models (3):** shared feature matrix `X`; targets `pit_within_{3,5,7}_laps`
- **Compound model:** train on rows where `pit_within_3_laps == 1`; target `next_compound`
