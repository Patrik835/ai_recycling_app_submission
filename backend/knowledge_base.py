"""Municipal Rules Knowledge Base: JSON lookup per country/material (Req15, design decision #3)."""
import json
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "rules")

_cache: Dict[str, Any] = {}


def _load(region_code: str) -> Optional[Dict]:
    if region_code in _cache:
        return _cache[region_code]
    path = os.path.join(_DATA_DIR, f"{region_code.upper()}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _cache[region_code] = data
    return data


def lookup_rule(region_code: str, material: str) -> Optional[Dict[str, Any]]:
    """Return the recycling rule dict for (region, material), or None if not found.

    Falls back to GLOBAL rules when no country-specific data is available (design decision #2).
    """
    data = _load(region_code)
    if data:
        rules = data.get("rules", {})
        # Try exact match, then case-insensitive prefix match
        rule = rules.get(material) or _fuzzy_lookup(rules, material)
        if rule:
            return rule

    # Fall back to GLOBAL
    if region_code != "GLOBAL":
        global_data = _load("GLOBAL")
        if global_data:
            rules = global_data.get("rules", {})
            return rules.get(material) or _fuzzy_lookup(rules, material)
    return None


def list_supported_regions() -> list:
    regions = []
    try:
        for fname in os.listdir(_DATA_DIR):
            if fname.endswith(".json"):
                code = fname[:-5]
                data = _load(code)
                regions.append({
                    "code": code,
                    "name": data.get("display_name", code) if data else code,
                })
    except Exception:
        pass
    return regions


def _fuzzy_lookup(rules: Dict, material: str) -> Optional[Dict]:
    mat_lower = material.lower()
    for key, val in rules.items():
        if key.lower() in mat_lower or mat_lower in key.lower():
            return val
    return None
