"""
Build a wide driver-lap table from one downloaded OpenF1 race folder.

Input:  path to data/raw/<year>/sessions/<meeting>_<session>_…_race/
Output: pandas DataFrame (one row per driver-lap), same grain as the Bahrain notebook.

This module is the reusable version of notebooks/01_bahrain_laps_spine.ipynb.
Use process_race for one session, or process_all_races / ``f1-process-races`` for bulk.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pandas as pd

# Identifier columns kept on the spine (see docs/data/DRIVER_LAP_SCHEMA.md §A).
_SPINE_COLS = ["meeting_key", "session_key", "driver_number", "lap_number", "date_start"]

# JSON files process_race needs. Sessions missing any are skipped in bulk mode.
_REQUIRED_JSON = (
    "laps",
    "stints",
    "pit",
    "position",
    "intervals",
    "weather",
    "race_control",
)


def _load_json_frame(session_dir: Path, name: str) -> pd.DataFrame:
    """Load ``<name>.json`` from the session folder into a DataFrame."""
    path = session_dir / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"missing required file: {path}")
    return pd.DataFrame(json.loads(path.read_text()))


def _season_from_session_dir(session_dir: Path) -> int:
    """
    Infer season year from the raw layout: data/raw/<year>/sessions/<session_id>.

    session_dir.name is the session id; year is two levels up.
    """
    return int(session_dir.parent.parent.name)


def build_spine(laps: pd.DataFrame, season: int) -> pd.DataFrame:
    """
    Build the identifier spine: one row per driver-lap.

    Parameters
    ----------
    laps :
        Raw OpenF1 laps table for the session.
    season :
        Championship year (not stored inside laps.json).
    """
    spine = laps[_SPINE_COLS].copy()
    spine.insert(0, "season", season)
    return spine.sort_values(["driver_number", "lap_number"]).reset_index(drop=True)


def add_stint_features(spine: pd.DataFrame, stints: pd.DataFrame) -> pd.DataFrame:
    """
    Join the stint covering each lap → compound, tyre age, stint length.

    A stint covers laps lap_start … lap_end inclusive for one driver.
    """
    stints = stints.copy()
    # A live/current stint has lap_end=None; treat it as open through the
    # latest lap so it is not dropped by the covering-stint filter below.
    stints["lap_end"] = pd.to_numeric(stints["lap_end"], errors="coerce").fillna(
        int(spine["lap_number"].max())
    )

    # Expand to spine×stints per driver, then keep the covering stint only.
    merged = spine.merge(
        stints[
            [
                "meeting_key",
                "session_key",
                "driver_number",
                "stint_number",
                "lap_start",
                "lap_end",
                "compound",
                "tyre_age_at_start",
            ]
        ],
        on=["meeting_key", "session_key", "driver_number"],
        how="left",
    )
    in_stint = (merged["lap_number"] >= merged["lap_start"]) & (
        merged["lap_number"] <= merged["lap_end"]
    )
    out = merged.loc[in_stint].copy()
    # Pit-lap overlap: stint N ends and stint N+1 starts on the same lap_number.
    # Keep the higher stint_number so each spine row maps to exactly one stint.
    out = (
        out.sort_values("stint_number")
        .groupby(
            ["meeting_key", "session_key", "driver_number", "lap_number"],
            as_index=False,
        )
        .tail(1)
    )
    out = out.rename(
        columns={
            "compound": "current_compound",
            "stint_number": "current_stint_number",
        }
    )
    # OpenF1 tyre_age_at_start can be >0 (e.g. quali rubber); then count up each lap.
    out["tyre_age"] = out["tyre_age_at_start"] + (out["lap_number"] - out["lap_start"])
    out["stint_length"] = (out["lap_number"] - out["lap_start"]) + 1
    out = out.drop(columns=["lap_start", "lap_end", "tyre_age_at_start"])
    return out.sort_values(["driver_number", "lap_number"]).reset_index(drop=True)


def add_pit_features(driver_laps: pd.DataFrame, pits: pd.DataFrame) -> pd.DataFrame:
    """
    Attach number_of_pit_stops and laps_since_last_pit (leakage-safe).

    At completed lap L, only pits with pit_lap <= L count. If none yet,
    laps_since_last_pit equals L (race start as reference).
    """
    out = driver_laps.copy()
    stop_counts: list[int] = []
    laps_since: list[int] = []

    # Group once so each row is an O(pits_for_driver) scan, not a full filter.
    pits_by_driver = {
        driver: group["lap_number"].sort_values().to_numpy()
        for driver, group in pits.groupby("driver_number")
    }

    for row in out.itertuples(index=False):
        past = [p for p in pits_by_driver.get(row.driver_number, []) if p <= row.lap_number]
        stop_counts.append(len(past))
        # 0 on the pit lap itself; otherwise laps since that stop.
        laps_since.append(row.lap_number - past[-1] if past else row.lap_number)

    out["number_of_pit_stops"] = stop_counts
    out["laps_since_last_pit"] = laps_since
    return out


def add_current_position(
    driver_laps: pd.DataFrame,
    positions: pd.DataFrame,
    laps: pd.DataFrame,
) -> pd.DataFrame:
    """
    Attach current_position via merge_asof at end-of-lap time.

    as_of ≈ date_start + lap_duration. Only position rows with date ≤ as_of
    are used (no future leakage). Also leaves as_of on the table for later
    as-of joins (intervals, weather, race control).
    """
    # lap_duration is needed to estimate when this lap finished.
    out = driver_laps.merge(
        laps[["driver_number", "lap_number", "lap_duration"]],
        on=["driver_number", "lap_number"],
        how="left",
    )
    # OpenF1 timestamps sometimes omit fractional seconds.
    out["date_start"] = pd.to_datetime(out["date_start"], utc=True, format="ISO8601")
    # date_start + lap_duration must stay the same datetime precision as the
    # position/interval/weather/race_control date columns so merge_asof can
    # join them (all parse to the same pandas datetime64 unit).
    out["as_of"] = out["date_start"] + pd.to_timedelta(
        out["lap_duration"].fillna(0), unit="s"
    )
    # Rare incomplete laps (null date_start) cannot be as-of joined — drop them.
    out = out.dropna(subset=["as_of"])

    pos = positions.copy()
    pos["date"] = pd.to_datetime(pos["date"], utc=True, format="ISO8601")
    pos = pos[["driver_number", "date", "position"]].sort_values("date")

    joined = pd.merge_asof(
        out.sort_values("as_of"),
        pos,
        left_on="as_of",
        right_on="date",
        by="driver_number",
        direction="backward",
    )
    joined = joined.rename(columns={"position": "current_position"})
    # Drop the position-stream timestamp; keep as_of for the next joins.
    return (
        joined.drop(columns=["date"])
        .sort_values(["driver_number", "lap_number"])
        .reset_index(drop=True)
    )


def add_interval_features(driver_laps: pd.DataFrame, intervals: pd.DataFrame) -> pd.DataFrame:
    """
    Attach gap_to_leader and interval_ahead via merge_asof on as_of.

    Requires as_of from add_current_position. OpenF1 may store gap_to_leader
    as "+1 LAP" / "+2 LAPS" for lapped cars — kept as-is.
    """
    out = driver_laps.copy()
    if "as_of" not in out.columns:
        raise ValueError("expected as_of on driver_laps — run add_current_position first")

    iv = intervals.copy()
    iv["date"] = pd.to_datetime(iv["date"], utc=True, format="ISO8601")
    iv = iv[["driver_number", "date", "gap_to_leader", "interval"]].sort_values("date")

    joined = pd.merge_asof(
        out.sort_values("as_of"),
        iv,
        left_on="as_of",
        right_on="date",
        by="driver_number",
        direction="backward",
    )
    joined = joined.rename(columns={"interval": "interval_ahead"})
    return (
        joined.drop(columns=["date"])
        .sort_values(["driver_number", "lap_number"])
        .reset_index(drop=True)
    )


def add_weather_features(driver_laps: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """
    Attach session weather at end-of-lap as_of (no driver key — global).

    Columns: air_temperature, track_temperature, humidity, rainfall, wind_speed.
    """
    out = driver_laps.copy()
    if "as_of" not in out.columns:
        raise ValueError("expected as_of on driver_laps — run add_current_position first")

    cols = [
        "air_temperature",
        "track_temperature",
        "humidity",
        "rainfall",
        "wind_speed",
    ]
    wx = weather.copy()
    wx["date"] = pd.to_datetime(wx["date"], utc=True, format="ISO8601")
    wx = wx[["date", *cols]].sort_values("date")

    # No by=driver — one weather snapshot applies to every car at that time.
    joined = pd.merge_asof(
        out.sort_values("as_of"),
        wx,
        left_on="as_of",
        right_on="date",
        direction="backward",
    )
    return (
        joined.drop(columns=["date"])
        .sort_values(["driver_number", "lap_number"])
        .reset_index(drop=True)
    )


# How long a red flag "counts" as recent for red_flag_recent.
_RED_RECENT_WINDOW = pd.Timedelta(minutes=5)


def build_race_control_states(race_control: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """
    Walk race_control events in time and emit SC/VSC/yellow state after each.

    Returns (states DataFrame with date + flags, list of red-flag timestamps).
    """
    rc = race_control.copy()
    rc["date"] = pd.to_datetime(rc["date"], utc=True, format="ISO8601")
    rc = rc.sort_values("date")

    sc = vsc = yellow = False
    rows: list[dict] = []
    red_times: list = []

    for r in rc.itertuples(index=False):
        msg = (r.message or "").upper()
        flag = r.flag or ""

        # OpenF1 encodes SC/VSC in message text, not a boolean column.
        if "SAFETY CAR DEPLOYED" in msg and "VIRTUAL" not in msg:
            sc = True
        if "SAFETY CAR IN THIS LAP" in msg:
            sc = False
        if "VIRTUAL SAFETY CAR DEPLOYED" in msg or msg.strip() == "VSC DEPLOYED":
            vsc = True
        if "VIRTUAL SAFETY CAR ENDING" in msg or msg.strip() == "VSC ENDING":
            vsc = False

        # Simplified: any CLEAR/GREEN/CHEQUERED clears yellow globally.
        if flag in ("YELLOW", "DOUBLE YELLOW"):
            yellow = True
        if flag in ("CLEAR", "GREEN", "CHEQUERED"):
            yellow = False

        # Exact / prefix match — do NOT use `"RED FLAG" in msg` (matches CHEQUERED FLAG).
        if flag == "RED" or msg.strip() == "RED FLAG" or msg.startswith("RED FLAG"):
            red_times.append(r.date)

        rows.append(
            {
                "date": r.date,
                "safety_car_active": sc,
                "virtual_safety_car_active": vsc,
                "yellow_flag_active": yellow,
            }
        )

    return pd.DataFrame(rows), red_times


def add_race_control_features(
    driver_laps: pd.DataFrame, race_control: pd.DataFrame
) -> pd.DataFrame:
    """Attach SC/VSC/yellow/red_flag_recent at end-of-lap as_of (session-wide)."""
    out = driver_laps.copy()
    if "as_of" not in out.columns:
        raise ValueError("expected as_of — run add_current_position first")

    states, red_times = build_race_control_states(race_control)
    joined = pd.merge_asof(
        out.sort_values("as_of"),
        states,
        left_on="as_of",
        right_on="date",
        direction="backward",
    )
    for col in ("safety_car_active", "virtual_safety_car_active", "yellow_flag_active"):
        joined[col] = joined[col].fillna(False).astype(bool)

    def _red_recent(t: pd.Timestamp) -> bool:
        return any((t - rd) <= _RED_RECENT_WINDOW and rd <= t for rd in red_times)

    joined["red_flag_recent"] = joined["as_of"].map(_red_recent)
    return (
        joined.drop(columns=["date"])
        .sort_values(["driver_number", "lap_number"])
        .reset_index(drop=True)
    )


def add_pit_window_labels(driver_laps: pd.DataFrame, pits: pd.DataFrame) -> pd.DataFrame:
    """
    Attach pit_within_3/5/7_laps labels (0/1) using **future** pits only.

    At lap L: 1 iff some pit_lap satisfies L < pit_lap <= L+N.
    These are training targets — not live features.
    """
    out = driver_laps.copy()
    pits_by_driver = {
        driver: group["lap_number"].sort_values().to_numpy()
        for driver, group in pits.groupby("driver_number")
    }

    within_3: list[int] = []
    within_5: list[int] = []
    within_7: list[int] = []

    for row in out.itertuples(index=False):
        lap = row.lap_number
        driver_pits = pits_by_driver.get(row.driver_number, [])
        within_3.append(int(any(lap < p <= lap + 3 for p in driver_pits)))
        within_5.append(int(any(lap < p <= lap + 5 for p in driver_pits)))
        within_7.append(int(any(lap < p <= lap + 7 for p in driver_pits)))

    out["pit_within_3_laps"] = within_3
    out["pit_within_5_laps"] = within_5
    out["pit_within_7_laps"] = within_7
    return out


def add_next_compound_label(driver_laps: pd.DataFrame, stints: pd.DataFrame) -> pd.DataFrame:
    """
    Attach next_compound: compound of the driver's following stint, else null.

    Label (uses future stint info). Used by the multiclass compound model.
    """
    out = driver_laps.copy()
    rows: list[dict] = []
    for driver, group in stints.groupby("driver_number"):
        ordered = group.sort_values("stint_number")
        compound_by_stint = dict(zip(ordered["stint_number"], ordered["compound"]))
        for stint_num in ordered["stint_number"]:
            rows.append(
                {
                    "driver_number": driver,
                    "current_stint_number": stint_num,
                    "next_compound": compound_by_stint.get(stint_num + 1),
                }
            )
    lookup = pd.DataFrame(rows)
    return out.merge(lookup, on=["driver_number", "current_stint_number"], how="left")


# Dry compounds that count toward the two-compound rule.
_DRY_COMPOUNDS = frozenset({"SOFT", "MEDIUM", "HARD"})


def add_compound_history_features(
    driver_laps: pd.DataFrame, stints: pd.DataFrame
) -> pd.DataFrame:
    """
    Attach has_used_* flags, compounds_used_so_far, previous_compound.

    Only stints with lap_start <= current lap (already begun) — no future leak.
    """
    out = driver_laps.copy()
    stints_by_driver = {
        driver: group.sort_values("stint_number")
        for driver, group in stints.groupby("driver_number")
    }

    records: list[dict] = []
    for row in out.itertuples(index=False):
        started = stints_by_driver[row.driver_number]
        started = started[started["lap_start"] <= row.lap_number]
        compounds = list(started["compound"])
        used = set(compounds)
        records.append(
            {
                "compounds_used_so_far": len(used),
                "has_used_soft": "SOFT" in used,
                "has_used_medium": "MEDIUM" in used,
                "has_used_hard": "HARD" in used,
                "has_used_intermediate": "INTERMEDIATE" in used,
                "has_used_wet": "WET" in used,
                "has_used_two_dry_compounds": len(used & _DRY_COMPOUNDS) >= 2,
                "previous_compound": compounds[-2] if len(compounds) >= 2 else None,
            }
        )

    return pd.concat([out.reset_index(drop=True), pd.DataFrame(records)], axis=1)


def add_pace_features(driver_laps: pd.DataFrame, laps: pd.DataFrame) -> pd.DataFrame:
    """Attach trailing pace / sector columns; no future laps in the rollups."""
    out = driver_laps.copy()

    extra = laps[
        [
            "driver_number",
            "lap_number",
            "lap_duration",
            "duration_sector_1",
            "duration_sector_2",
            "duration_sector_3",
            "is_pit_out_lap",
        ]
    ]
    # Position step may already have attached lap_duration — replace cleanly.
    if "lap_duration" in out.columns:
        out = out.drop(columns=["lap_duration"])
    out = out.merge(extra, on=["driver_number", "lap_number"], how="left")
    out = out.sort_values(["driver_number", "lap_number"])

    g = out.groupby("driver_number", group_keys=False)
    out["current_lap_time"] = out["lap_duration"]
    out["previous_lap_time"] = g["lap_duration"].shift(1)

    # Windows include the current lap (min_periods=1 for early race).
    out["rolling_mean_lap_time_3"] = g["lap_duration"].transform(
        lambda s: s.rolling(3, min_periods=1).mean()
    )
    out["rolling_mean_lap_time_5"] = g["lap_duration"].transform(
        lambda s: s.rolling(5, min_periods=1).mean()
    )
    out["rolling_median_lap_time_3"] = g["lap_duration"].transform(
        lambda s: s.rolling(3, min_periods=1).median()
    )
    out["pace_delta_to_recent_average"] = (
        out["current_lap_time"] - out["rolling_mean_lap_time_3"]
    )

    stint_g = out.groupby(["driver_number", "current_stint_number"], group_keys=False)
    stint_best = stint_g["lap_duration"].transform(lambda s: s.expanding().min())
    out["pace_delta_to_stint_best"] = out["lap_duration"] - stint_best

    return out.reset_index(drop=True)


def process_race(session_dir: str | Path) -> pd.DataFrame:
    """
    Build the full driver-lap table for one race session directory.

    Mirrors notebooks/01_bahrain_laps_spine.ipynb (features + labels).
    """
    session_dir = Path(session_dir)
    season = _season_from_session_dir(session_dir)

    laps = _load_json_frame(session_dir, "laps")
    stints = _load_json_frame(session_dir, "stints")
    pits = _load_json_frame(session_dir, "pit")
    positions = _load_json_frame(session_dir, "position")
    intervals = _load_json_frame(session_dir, "intervals")
    weather = _load_json_frame(session_dir, "weather")
    race_control = _load_json_frame(session_dir, "race_control")

    table = build_spine(laps, season)
    table = add_stint_features(table, stints)
    table = add_pit_features(table, pits)
    table = add_current_position(table, positions, laps)
    table = add_interval_features(table, intervals)
    table = add_weather_features(table, weather)
    table = add_race_control_features(table, race_control)
    table = add_pit_window_labels(table, pits)
    table = add_next_compound_label(table, stints)
    table = add_compound_history_features(table, stints)
    return add_pace_features(table, laps)


def iter_race_dirs(raw_root: str | Path) -> Iterator[Path]:
    """Yield ``*_race`` session folders under data/raw/<year>/sessions/."""
    raw_root = Path(raw_root)
    for year_dir in sorted(raw_root.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        sessions = year_dir / "sessions"
        if not sessions.is_dir():
            continue
        for session_dir in sorted(sessions.iterdir()):
            if session_dir.is_dir() and session_dir.name.endswith("_race"):
                yield session_dir


def session_is_processable(session_dir: Path) -> bool:
    """True if every JSON required by process_race exists and is non-empty."""
    for name in _REQUIRED_JSON:
        path = session_dir / f"{name}.json"
        # Missing or tiny files (e.g. failed download) are not usable.
        if not path.exists() or path.stat().st_size < 3:
            return False
    return True


def process_all_races(
    raw_root: str | Path = "data/raw",
    processed_root: str | Path = "data/processed",
    *,
    skip_existing: bool = True,
) -> list[Path]:
    """
    Run process_race on every usable race folder and write CSVs.

    Output path: data/processed/<year>/<session_id>_driver_laps.csv
    Returns list of paths written (or already present if skip_existing).
    """
    raw_root = Path(raw_root)
    processed_root = Path(processed_root)
    written: list[Path] = []

    for session_dir in iter_race_dirs(raw_root):
        if not session_is_processable(session_dir):
            print(f"skip (incomplete): {session_dir.name}")
            continue

        season = _season_from_session_dir(session_dir)
        out_dir = processed_root / str(season)
        out_path = out_dir / f"{session_dir.name}_driver_laps.csv"

        if skip_existing and out_path.exists():
            print(f"skip (exists): {out_path}")
            written.append(out_path)
            continue

        try:
            table = process_race(session_dir)
        except Exception as exc:  # keep bulk run going; one bad race must not abort all
            print(f"FAIL {session_dir.name}: {exc}")
            continue

        out_dir.mkdir(parents=True, exist_ok=True)
        table.to_csv(out_path, index=False)
        print(f"wrote {out_path} ({len(table)} rows)")
        written.append(out_path)

    return written


def build_master_training_csv(
    processed_root: str | Path = "data/processed",
    out_path: str | Path | None = None,
) -> Path:
    """
    Stack every per-race ``*_driver_laps.csv`` into one training table.

    Default output: data/processed/driver_laps_all.csv
    """
    processed_root = Path(processed_root)
    out_path = Path(out_path) if out_path else processed_root / "driver_laps_all.csv"

    # Recurse year folders; ignore the master file if re-running.
    csv_paths = sorted(
        p
        for p in processed_root.glob("*/*_driver_laps.csv")
        if p.is_file()
    )
    if not csv_paths:
        raise FileNotFoundError(f"no per-race CSVs under {processed_root}")

    frames = [pd.read_csv(p) for p in csv_paths]
    master = pd.concat(frames, ignore_index=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(out_path, index=False)
    print(f"wrote master {out_path} ({len(master)} rows from {len(csv_paths)} races)")
    return out_path


def main(argv: Sequence[str] | None = None) -> None:
    """CLI: process races and/or build the master training CSV."""
    parser = argparse.ArgumentParser(
        description="Build driver-lap CSVs for every usable OpenF1 race folder.",
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("data/raw"),
        help="Root of downloaded session JSON (default: data/raw).",
    )
    parser.add_argument(
        "--processed-root",
        type=Path,
        default=Path("data/processed"),
        help="Where to write CSVs (default: data/processed).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process even if the output CSV already exists.",
    )
    parser.add_argument(
        "--concat-only",
        action="store_true",
        help="Skip per-race processing; only build driver_laps_all.csv.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.concat_only:
        paths = process_all_races(
            args.raw_root,
            args.processed_root,
            skip_existing=not args.force,
        )
        print(f"done: {len(paths)} per-race CSV path(s)")

    build_master_training_csv(args.processed_root)


if __name__ == "__main__":
    main()
