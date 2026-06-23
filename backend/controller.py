"""System Controller: orchestrates the full scan pipeline (Req04-11, Req14-17, design decisions #1-10)."""
import asyncio
import json
import logging
import os
from typing import List, Optional, Dict, Any

from PIL import Image

import database
import knowledge_base
import llm_orchestrator
import material as material_mod
from models import (
    BoundingBox, ChatMessage, ChatRequest, ChatResponse,
    DetectedItem, HistoryEntry, ImpactStats,
    InstructionsResult, ScanResult,
)

logger = logging.getLogger(__name__)

DETECTION_CONF_THRESHOLD = 0.80   # Req07/23
MATERIAL_CONF_THRESHOLD = 0.75    # NfReq08, design decision #7

_IMPACT_PATH = os.path.join(os.path.dirname(__file__), "data", "impact_factors.json")
_impact_factors: Optional[Dict] = None


def _load_impact():
    global _impact_factors
    if _impact_factors is None:
        try:
            with open(_IMPACT_PATH) as f:
                _impact_factors = json.load(f)
        except Exception:
            _impact_factors = {}
    return _impact_factors


# ── Scan pipeline ────────────────────────────────────────────────────────────

async def run_scan(img: Image.Image, user_id: str) -> ScanResult:
    """Classify the uploaded image with CLIP and return a single DetectedItem."""
    w, h = img.size

    mat, mat_conf, cat, uncertain = await material_mod.classify_material(
        img, fallback_material="Unknown", fallback_category="landfill", timeout=10.0
    )

    del img  # never keep image bytes in memory (NfReq10)

    if mat == "Unknown":
        return ScanResult(items=[], image_width=w, image_height=h, no_items_found=True)

    item = DetectedItem(
        item_name=_material_to_name(mat),
        confidence=mat_conf,
        bbox=BoundingBox(x=0, y=0, width=w, height=h),
        material=mat,
        material_confidence=mat_conf,
        category=cat,
        material_uncertain=uncertain,
    )
    return ScanResult(
        items=[item],
        image_width=w,
        image_height=h,
        has_low_confidence=mat_conf < DETECTION_CONF_THRESHOLD,
        clutter_warning=False,
    )


# ── Instructions ─────────────────────────────────────────────────────────────

BIN_COLOR_HEX = {
    "yellow": "#F9C74F",
    "blue":   "#4895EF",
    "green":  "#4CC9A0",
    "white":  "#F8F9FA",
    "brown":  "#8B5E3C",
    "black":  "#212529",
    "grey":   "#6C757D",
    "gray":   "#6C757D",
    "red":    "#E63946",
    "orange": "#F4A261",
}


async def get_instructions(
    item_name: str,
    material: str,
    region: str,
    language: str,
    user_id: str,
) -> InstructionsResult:
    """Look up rules and have LLM phrase instructions (Req09-11, Req15, Req17, design decision #3)."""
    rule = knowledge_base.lookup_rule(region, material)
    location_specific = rule is not None

    # If no rule, still generate instructions (UC2 exception)
    llm_text = await llm_orchestrator.generate_instructions(
        item_name, material, region, language, rule
    )

    # Derive structured fields from rule (fall back to LLM-only text)
    if rule:
        bin_color = rule.get("bin_color", "")
        category = rule.get("category", "landfill")
        prep_steps = rule.get("prep", [])
        notes = rule.get("notes", "")
    else:
        bin_color = ""
        category = _infer_category(material)
        prep_steps = []
        notes = "Location-specific rules are unavailable for this region."

    # Environmental impact (Req11)
    factors = _load_impact()
    mat_key = material.lower().split("(")[0].strip().replace(" ", "_")
    factor = factors.get(mat_key, factors.get("default", {}))
    impact = factor.get("impact_text", "")

    # Persist to history if consent given (Req18, NfReq10)
    co2 = float(factor.get("co2_kg", 0.0))
    energy = float(factor.get("energy_kwh", 0.0))
    database.save_scan(user_id, item_name, material, category, region, co2, energy)

    bin_color_first = bin_color.split("/")[0].strip().lower() if bin_color else ""
    bin_hex = BIN_COLOR_HEX.get(bin_color_first, "#6C757D")

    if llm_text and llm_text != llm_orchestrator.FALLBACK_MESSAGE:
        prep_steps = _parse_llm_steps(llm_text)

    return InstructionsResult(
        item_name=item_name,
        material=material,
        region=region,
        bin_color=bin_color,
        bin_color_hex=bin_hex,
        category=category,
        prep_steps=prep_steps if prep_steps else [llm_text or "Dispose according to local guidelines."],
        impact=impact,
        notes=notes,
        location_specific=location_specific,
        language=language,
    )


# ── Chat ─────────────────────────────────────────────────────────────────────

async def handle_chat(req: ChatRequest, user_id: str) -> ChatResponse:
    """Follow-up Q&A with item context (Req12-13, design decision #8)."""
    rule = knowledge_base.lookup_rule(req.region, req.material)
    messages = [{"role": m.role, "content": m.content} for m in req.history]
    response = await llm_orchestrator.chat(
        req.message, req.item_name, req.material, req.region, req.language, rule, messages
    )
    return ChatResponse(response=response)


# ── History & impact ─────────────────────────────────────────────────────────

def get_impact_stats(user_id: str) -> ImpactStats:
    rows, co2, energy, total = database.get_history(user_id)
    history = [
        HistoryEntry(
            id=r["id"],
            item_name=r["item_name"],
            material=r["material"],
            category=r["category"],
            region=r["region"],
            timestamp=r["timestamp"],
            co2_saved=r["co2_saved"],
            energy_saved=r["energy_saved"],
        )
        for r in rows
    ]
    return ImpactStats(
        total_scans=total,
        total_co2_saved=round(co2, 3),
        total_energy_saved=round(energy, 3),
        history=history,
    )


_MATERIAL_NAME_MAP = {
    "plastic (pet)":  "Plastic Bottle",
    "plastic":        "Plastic Item",
    "glass":          "Glass Container",
    "aluminum":       "Aluminum Can",
    "metal":          "Metal Item",
    "cardboard":      "Cardboard",
    "paper":          "Paper",
    "organic":        "Food Waste",
    "e-waste":        "Electronic Device",
    "mixed waste":    "Mixed Waste",
    "ceramic":        "Ceramic Item",
    "textile":        "Textile Item",
    "hazardous":      "Hazardous Waste",
}

def _parse_llm_steps(text: str) -> list:
    import re
    text = re.sub(r'\*+', '', text)     # strip ** bold
    text = re.sub(r'#+\s*', '', text)   # strip # headers
    text = re.sub(r'`+', '', text)      # strip backticks

    parts = re.split(r'\n\s*\d+[\.\)]\s*', text)

    if len(parts) > 1:
        # Drop the first chunk if it's just an intro line (no sentence-ending punctuation)
        steps = []
        for i, p in enumerate(parts):
            p = p.strip()
            if not p:
                continue
            if i == 0 and len(p) < 100 and not re.search(r'[.!?]$', p):
                continue
            steps.append(p)
        return steps or [text.strip()]

    # No numbered list — split on non-empty lines
    return [p.strip() for p in text.splitlines() if p.strip()]


def _material_to_name(material: str) -> str:
    return _MATERIAL_NAME_MAP.get(material.lower(), material or "Unknown Item")


def _infer_category(material: str) -> str:
    m = material.lower()
    if any(x in m for x in ["organic", "food"]):
        return "compostable"
    if any(x in m for x in ["e-waste", "electronic", "battery"]):
        return "special disposal"
    if any(x in m for x in ["plastic", "glass", "aluminum", "metal", "paper", "cardboard"]):
        return "recyclable"
    return "landfill"
