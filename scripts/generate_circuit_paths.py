"""
Generate circuit path data for the static track library.

Uses FastF1's official circuit corner / marshal-sector coordinates as anchor
points, orders them around the circuit, smooths them into a closed loop, and
emits the result in the **raw FastF1 coordinate system**.

The raw coordinate system is shared with OpenF1 ``v1/location`` ``x``/``y``
(proven in the Phase 0 spike), so the frontend can place live car markers with
a single shared transform. No per-axis normalization is applied here — that
would distort the aspect ratio and break the link to live locations.

FastF1 is a build-time dependency only (not listed in requirements.txt). Run:

    python scripts/generate_circuit_paths.py --write-circuits --year 2025

to regenerate ``src/formula1_strategy_tool/api/circuits.py``, or:

    python scripts/generate_circuit_paths.py --year 2025 --circuit-key 4

to print one circuit's raw path for inspection.

OpenF1 and FastF1 share the same ``circuit_key`` numbering.
"""

from __future__ import annotations

import argparse
import math
from collections.abc import Iterable
from pathlib import Path

try:
    import fastf1.mvapi as mvapi
except ImportError as exc:  # pragma: no cover - build-time tool
    raise SystemExit("fastf1 is required: pip install fastf1") from exc

RESAMPLE = 140
SAMPLES_PER_SEGMENT = 12

# circuit_key -> circuit name. Matches the 2026 calendar circuits that FastF1
# has geometry for (Madring 153 and Sepang 12 are still missing a real source).
CIRCUITS: list[tuple[int, str]] = [
    (2, "Silverstone Circuit"),
    (4, "Hungaroring"),
    (7, "Circuit de Spa-Francorchamps"),
    (9, "Circuit of the Americas"),
    (10, "Albert Park Circuit"),
    (14, "Autodromo Jose Carlos Pace"),
    (15, "Circuit de Barcelona-Catalunya"),
    (19, "Red Bull Ring"),
    (22, "Circuit de Monaco"),
    (23, "Circuit Gilles Villeneuve"),
    (39, "Autodromo Nazionale Monza"),
    (46, "Suzuka International Racing Course"),
    (49, "Shanghai International Circuit"),
    (55, "Circuit Zandvoort"),
    (61, "Marina Bay Street Circuit"),
    (63, "Bahrain International Circuit"),
    (65, "Autodromo Hermanos Rodriguez"),
    (70, "Yas Marina Circuit"),
    (144, "Baku City Circuit"),
    (149, "Jeddah Corniche Circuit"),
    (150, "Lusail International Circuit"),
    (151, "Miami International Autodrome"),
    (152, "Las Vegas Strip Circuit"),
]


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _project(
    point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return 0.0
    t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_sq
    return max(0.0, min(1.0, t))


def _order_by_track_distance(
    sectors: list[tuple[float, float]], corners: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    """Order corners + sectors by arc length along the sector reference loop."""
    n = len(sectors)
    cumulative = [0.0] * n
    for i in range(1, n):
        cumulative[i] = cumulative[i - 1] + _dist(sectors[i - 1], sectors[i])

    def position(point: tuple[float, float]) -> float:
        best: tuple[float, float] | None = None
        for i in range(n):
            a = sectors[i]
            b = sectors[(i + 1) % n]
            t = _project(point, a, b)
            projected = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            d = _dist(point, projected)
            if best is None or d < best[0]:
                best = (d, cumulative[i] + t * _dist(a, b))
        return best[1] if best else 0.0

    merged = sectors + corners
    ordered = sorted(merged, key=position)
    out: list[tuple[float, float]] = []
    for point in ordered:
        if not out or _dist(point, out[-1]) > 1.0:
            out.append(point)
    if out and _dist(out[0], out[-1]) < 1.0:
        out = out[:-1]
    return out


def _catmull_rom_closed(
    points: list[tuple[float, float]], samples: int
) -> list[tuple[float, float]]:
    n = len(points)
    out: list[tuple[float, float]] = []
    for i in range(n):
        p0 = points[(i - 1) % n]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        p3 = points[(i + 2) % n]
        for step in range(samples):
            t = step / samples
            t2 = t * t
            t3 = t2 * t
            out.append(
                (
                    0.5
                    * (
                        2 * p1[0]
                        + (-p0[0] + p2[0]) * t
                        + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                        + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
                    ),
                    0.5
                    * (
                        2 * p1[1]
                        + (-p0[1] + p2[1]) * t
                        + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                        + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
                    ),
                )
            )
    return out


def _resample(
    points: list[tuple[float, float]], count: int
) -> list[tuple[float, float]]:
    closed = points + [points[0]]
    total = sum(
        math.hypot(closed[i + 1][0] - closed[i][0], closed[i + 1][1] - closed[i][1])
        for i in range(len(closed) - 1)
    )
    step = total / count
    out: list[tuple[float, float]] = []
    acc = 0.0
    for i in range(len(closed) - 1):
        a = closed[i]
        b = closed[i + 1]
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        while acc + seg >= step and len(out) < count:
            t = (step - acc) / seg
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            seg -= step - acc
            acc = 0.0
            a = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        acc += seg
    return out


def build_raw(
    year: int, circuit_key: int
) -> tuple[list[tuple[float, float]], tuple[float, float]]:
    """Return (raw closed path points, raw start_finish point)."""
    info = mvapi.get_circuit_info(year=year, circuit_key=circuit_key)
    if info is None:
        raise ValueError(
            f"no circuit info for year={year} circuit_key={circuit_key}"
        )

    corners = list(zip(info.corners["X"], info.corners["Y"]))
    sectors = list(zip(info.marshal_sectors["X"], info.marshal_sectors["Y"]))
    start_finish_raw = sectors[0]

    anchors = _order_by_track_distance(sectors, corners)
    if len(anchors) < 4:
        raise ValueError("too few anchor points")

    splined = _catmull_rom_closed(anchors, SAMPLES_PER_SEGMENT)
    resampled = _resample(splined, RESAMPLE)
    resampled.append(resampled[0])
    return resampled, start_finish_raw


def _format_point(x: float, y: float) -> str:
    return f"TrackPoint(x={x:.4f}, y={y:.4f})"


def write_circuits_module(year: int, destination: Path) -> None:
    """Regenerate the circuits.py module with raw-coordinate geometry."""
    lines: list[str] = [
        '"""',
        "Static circuit path library for the track map.",
        "",
        "Each entry maps an OpenF1 ``circuit_key`` to a :class:`TrackState` whose",
        "path points are in the raw FastF1 coordinate system. This is the same",
        "coordinate system as OpenF1 ``v1/location`` ``x``/``y``, so live car",
        "markers and the circuit outline can share one display transform.",
        "",
        "Geometry is derived from official FastF1 circuit data via",
        "``scripts/generate_circuit_paths.py``; see that script for the source and",
        "regeneration instructions.",
        "",
        "OpenF1 and FastF1 share the same ``circuit_key`` numbering.",
        "",
        "Not yet available (return 404 until sourced): Madring (153), Sepang (12).",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from formula1_strategy_tool.api.schemas import TrackPoint, TrackState",
        "",
        "CIRCUITS: dict[int, TrackState] = {",
    ]

    for circuit_key, circuit_name in CIRCUITS:
        path, start_finish = build_raw(year, circuit_key)
        lines.append(f"    {circuit_key}: TrackState(")
        lines.append(f'        circuit_name="{circuit_name}",')
        lines.append(f"        circuit_key={circuit_key},")
        lines.append(
            f"        start_finish={_format_point(start_finish[0], start_finish[1])},"
        )
        lines.append("        path=[")
        lines.extend(f"            {_format_point(x, y)}," for x, y in path)
        lines.append("        ],")
        lines.append("    ),")

    lines.extend(
        [
            "}",
            "",
            "",
            "def track_for_circuit(circuit_key: int) -> TrackState | None:",
            '    """Return the TrackState for a circuit_key, or None if unknown."""',
            "    return CIRCUITS.get(circuit_key)",
            "",
        ]
    )

    destination.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {destination} ({len(CIRCUITS)} circuits)")


def _format_path_lines(points: Iterable[tuple[float, float]]) -> str:
    return "\n".join(f"    TrackPoint(x={x:.4f}, y={y:.4f})," for x, y in points)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--circuit-key", type=int, default=None)
    parser.add_argument(
        "--write-circuits",
        action="store_true",
        help="regenerate src/formula1_strategy_tool/api/circuits.py",
    )
    args = parser.parse_args()

    if args.write_circuits:
        destination = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "formula1_strategy_tool"
            / "api"
            / "circuits.py"
        )
        write_circuits_module(args.year, destination)
        return

    if args.circuit_key is None:
        parser.error("--circuit-key is required unless --write-circuits is set")

    path, start_finish = build_raw(args.year, args.circuit_key)
    print(
        f"start_finish=TrackPoint(x={start_finish[0]:.4f}, y={start_finish[1]:.4f})"
    )
    print("path=[")
    print(_format_path_lines(path))
    print("]")


if __name__ == "__main__":
    main()
