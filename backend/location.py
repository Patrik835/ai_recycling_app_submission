"""Location module: GPS coordinates → region code, manual selection (Req14, SUC2)."""
from typing import Optional, Tuple

# Approximate bounding boxes: (lat_min, lat_max, lon_min, lon_max) → region_code
COUNTRY_BOXES = [
    (46.37, 49.02, 9.53, 17.16,  "AT", "Austria"),
    (47.27, 55.06, 5.87, 15.04,  "DE", "Germany"),
    (45.82, 48.58, 6.02, 10.49,  "CH", "Switzerland"),
    (33.11, 38.61, 124.61, 131.87, "KR", "South Korea"),
    (49.50, 54.84, 14.12, 24.15,  "PL", "Poland"),
    (36.14, 47.79, 6.63, 18.52,   "IT", "Italy"),
    (42.33, 51.09, -4.79, 8.23,   "FR", "France"),
    (36.01, 43.79, -9.50, -6.19,  "PT", "Portugal"),
    (35.95, 43.80, -9.39, 3.30,   "ES", "Spain"),
    (50.75, 53.55, 3.36, 7.23,    "NL", "Netherlands"),
    (49.50, 51.50, 2.54, 6.40,    "BE", "Belgium"),
    (55.34, 57.75, 8.07, 15.19,   "DK", "Denmark"),
    (57.91, 71.19, 4.64, 31.07,   "NO", "Norway"),
    (55.34, 69.07, 10.93, 24.17,  "SE", "Sweden"),
    (59.45, 70.09, 19.09, 31.59,  "FI", "Finland"),
    (24.52, 49.38, -124.77, -66.95, "US", "United States"),
    (42.01, 83.11, -141.00, -52.62, "CA", "Canada"),
    (-43.64, -10.00, 113.34, 153.64, "AU", "Australia"),
    (20.22, 53.56, 73.56, 134.77,  "CN", "China"),
    (24.40, 45.55, 122.93, 145.82, "JP", "Japan"),
]

KNOWN_COUNTRIES = {row[4]: row[5] for row in COUNTRY_BOXES}
KNOWN_COUNTRIES["GLOBAL"] = "Global (General Guide)"


def coords_to_region(lat: float, lon: float) -> Tuple[str, str]:
    """Return (region_code, display_name) for GPS coordinates."""
    for lat_min, lat_max, lon_min, lon_max, code, name in COUNTRY_BOXES:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return code, name
    return "GLOBAL", "Global (General Guide)"


def country_to_region(country_code: str) -> Tuple[str, str]:
    """Validate and return region tuple for a manual country code selection."""
    code = country_code.upper()
    name = KNOWN_COUNTRIES.get(code, "Global (General Guide)")
    if code not in KNOWN_COUNTRIES:
        code = "GLOBAL"
    return code, name


def get_all_countries() -> list:
    return [{"code": k, "name": v} for k, v in sorted(KNOWN_COUNTRIES.items(), key=lambda x: x[1])]
