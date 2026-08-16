"""
Static country name for each circuit_key, shown on the track-map preview.

Keys mirror the circuit library in ``circuits.py``. This mapping lives in its
own module (rather than the generated ``circuits.py``) so regenerating circuit
geometry does not drop the country metadata.
"""

from __future__ import annotations

COUNTRY_NAMES: dict[int, str] = {
    2: "United Kingdom",
    4: "Hungary",
    7: "Belgium",
    9: "United States",
    10: "Australia",
    14: "Brazil",
    15: "Spain",
    19: "Austria",
    22: "Monaco",
    23: "Canada",
    39: "Italy",
    46: "Japan",
    49: "China",
    55: "Netherlands",
    61: "Singapore",
    63: "Bahrain",
    65: "Mexico",
    70: "United Arab Emirates",
    144: "Azerbaijan",
    149: "Saudi Arabia",
    150: "Qatar",
    151: "United States",
    152: "United States",
}
