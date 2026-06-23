"""Material Classifier: CLIP zero-shot on cropped detections (Req05, NfReq08, SUC3)."""
import asyncio
import logging
from typing import Tuple, Optional

from PIL import Image

MATERIAL_CONF_THRESHOLD = 0.75  # NfReq08, design decision #7

logger = logging.getLogger(__name__)

# Zero-shot labels that align with our recycling materials
ZS_LABELS = [
    "a plastic bottle or plastic container",
    "a glass bottle or glass jar",
    "an aluminum can or metal tin",
    "a cardboard box or cardboard packaging",
    "paper or newspaper",
    "food waste or organic material",
    "an electronic device or electronic waste",
    "garbage or mixed waste",
    "a metal object",
    "a ceramic or porcelain item",
    "a textile or fabric item",
]

LABEL_TO_MATERIAL = {
    "a plastic bottle or plastic container":    ("Plastic (PET)", "recyclable"),
    "a glass bottle or glass jar":              ("Glass",          "recyclable"),
    "an aluminum can or metal tin":             ("Aluminum",       "recyclable"),
    "a cardboard box or cardboard packaging":   ("Cardboard",      "recyclable"),
    "paper or newspaper":                       ("Paper",          "recyclable"),
    "food waste or organic material":           ("Organic",        "compostable"),
    "an electronic device or electronic waste": ("E-Waste",        "special disposal"),
    "garbage or mixed waste":                   ("Mixed Waste",    "landfill"),
    "a metal object":                           ("Metal",          "recyclable"),
    "a ceramic or porcelain item":              ("Ceramic",        "landfill"),
    "a textile or fabric item":                 ("Textile",        "special disposal"),
}

_clip_pipeline = None


def _load_clip():
    global _clip_pipeline
    if _clip_pipeline is not None:
        return _clip_pipeline
    try:
        from transformers import pipeline as hf_pipeline
        _clip_pipeline = hf_pipeline(
            "zero-shot-image-classification",
            model="openai/clip-vit-base-patch32",
        )
        logger.info("CLIP model loaded for material classification.")
    except Exception as e:
        logger.warning(f"Could not load CLIP model: {e}. Falling back to rule-based material.")
        _clip_pipeline = None
    return _clip_pipeline


async def classify_material(
    crop: Image.Image,
    fallback_material: Optional[str] = None,
    fallback_category: Optional[str] = None,
    timeout: float = 10.0,
) -> Tuple[str, float, str, bool]:
    """Return (material, confidence, category, uncertain).

    uncertain=True triggers manual-selection prompt per design decision #7.
    """
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _run_clip, crop),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning("Material classifier timed out — using fallback.")
        result = None

    if result is None:
        mat = fallback_material or "Unknown"
        cat = fallback_category or "landfill"
        return mat, 0.0, cat, True

    label = result[0]["label"]
    score = float(result[0]["score"])
    mat, cat = LABEL_TO_MATERIAL.get(label, (fallback_material or "Unknown", fallback_category or "landfill"))
    uncertain = score < MATERIAL_CONF_THRESHOLD
    return mat, score, cat, uncertain


def _run_clip(crop: Image.Image):
    pipe = _load_clip()
    if pipe is None:
        return None
    try:
        return pipe(crop, candidate_labels=ZS_LABELS)
    except Exception as e:
        logger.warning(f"CLIP inference failed: {e}")
        return None
