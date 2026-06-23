"""FastAPI application entry point and route definitions."""
import logging
import os
import uuid
from typing import Optional

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import controller
import database
import location as loc_mod
import knowledge_base
from models import (
    ChatRequest, ChatResponse, ConsentRequest, ConsentResponse,
    ImpactStats, InstructionsResult, LocationRequest, LocationResponse,
    ScanResult,
)
from preprocessing import ImageValidationError, validate_and_preprocess

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

app = FastAPI(title="Recycling Object Detector", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── helpers ──────────────────────────────────────────────────────────────────

def get_user_id(x_user_id: Optional[str] = None) -> str:
    """Resolve user ID from request header; auto-generate if missing."""
    if x_user_id and len(x_user_id) >= 8:
        database.ensure_user(x_user_id)
        return x_user_id
    uid = str(uuid.uuid4())
    database.ensure_user(uid)
    return uid


# ── startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    database.init_db()
    logging.getLogger("main").info("Database initialised.")
    import threading, asyncio
    def _preload():
        import material as mat
        mat._load_clip()  # pre-warm CLIP so the first scan isn't slow
    threading.Thread(target=_preload, daemon=True).start()

    async def _warm_ollama():
        import httpx
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                await client.post("http://localhost:11434/api/chat", json={
                    "model": "llama3", "messages": [{"role": "user", "content": "hi"}],
                    "stream": False, "options": {"num_predict": 1},
                })
            logging.getLogger("main").info("Ollama model warmed up.")
        except Exception:
            pass
    asyncio.create_task(_warm_ollama())


# ── scan ─────────────────────────────────────────────────────────────────────

@app.post("/api/scan", response_model=ScanResult)
async def scan(
    file: UploadFile = File(...),
    x_user_id: Optional[str] = Header(default=None),
):
    """POST multipart image → detection results with bounding boxes (Req01-08)."""
    user_id = get_user_id(x_user_id)
    raw = await file.read()

    try:
        img = validate_and_preprocess(raw, file.filename or "upload.jpg")
    except ImageValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = await controller.run_scan(img, user_id)
    return result


# ── instructions ─────────────────────────────────────────────────────────────

@app.get("/api/instructions", response_model=InstructionsResult)
async def instructions(
    item: str = Query(...),
    material: str = Query(...),
    region: str = Query("GLOBAL"),
    lang: str = Query("en"),
    x_user_id: Optional[str] = Header(default=None),
):
    """Lookup + LLM-phrased disposal instructions (Req09-11, Req15, Req17)."""
    user_id = get_user_id(x_user_id)
    return await controller.get_instructions(item, material, region, lang, user_id)


# ── chat ─────────────────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    x_user_id: Optional[str] = Header(default=None),
):
    """Follow-up natural-language Q&A (Req12-13, NfReq05)."""
    user_id = get_user_id(x_user_id)
    return await controller.handle_chat(req, user_id)


# ── location ─────────────────────────────────────────────────────────────────

@app.get("/api/location/countries")
def list_countries():
    return loc_mod.get_all_countries()


@app.put("/api/location", response_model=LocationResponse)
async def set_location(
    req: LocationRequest,
    x_user_id: Optional[str] = Header(default=None),
):
    """Set location via GPS coords or country code (Req14, Req16, Req22)."""
    user_id = get_user_id(x_user_id)

    if req.latitude is not None and req.longitude is not None:
        code, name = loc_mod.coords_to_region(req.latitude, req.longitude)
    elif req.country:
        code, name = loc_mod.country_to_region(req.country)
    else:
        raise HTTPException(status_code=400, detail="Provide latitude/longitude or country code.")

    database.set_user_region(user_id, code)
    return LocationResponse(country=name, region_code=code, display_name=name)


@app.get("/api/location", response_model=LocationResponse)
def get_location(x_user_id: Optional[str] = Header(default=None)):
    user_id = get_user_id(x_user_id)
    region_code = database.get_user_region(user_id)
    info = loc_mod.get_all_countries()
    name = next((c["name"] for c in info if c["code"] == region_code), region_code)
    return LocationResponse(country=name, region_code=region_code, display_name=name)


# ── history ───────────────────────────────────────────────────────────────────

@app.get("/api/history", response_model=ImpactStats)
def history(x_user_id: Optional[str] = Header(default=None)):
    """Return scan history + aggregated impact stats (Req18-19, NfReq10)."""
    user_id = get_user_id(x_user_id)
    if not database.get_user_consent(user_id):
        return ImpactStats(total_scans=0, total_co2_saved=0.0, total_energy_saved=0.0, history=[])
    return controller.get_impact_stats(user_id)


@app.delete("/api/history")
def delete_history(x_user_id: Optional[str] = Header(default=None)):
    user_id = get_user_id(x_user_id)
    database.clear_history(user_id)
    return {"message": "History cleared."}


# ── consent ───────────────────────────────────────────────────────────────────

@app.put("/api/consent", response_model=ConsentResponse)
def set_consent(
    req: ConsentRequest,
    x_user_id: Optional[str] = Header(default=None),
):
    """Toggle data-consent (NfReq10, GDPR)."""
    user_id = get_user_id(x_user_id)
    database.set_consent(user_id, req.consent)
    if not req.consent:
        database.clear_history(user_id)
    msg = "Consent granted. Scan history will be saved." if req.consent else "Consent revoked. History cleared."
    return ConsentResponse(consent=req.consent, message=msg)


@app.get("/api/consent")
def get_consent(x_user_id: Optional[str] = Header(default=None)):
    user_id = get_user_id(x_user_id)
    return {"consent": database.get_user_consent(user_id), "user_id": user_id}


# ── language ──────────────────────────────────────────────────────────────────

@app.put("/api/language")
def set_language(
    language: str = Query(...),
    x_user_id: Optional[str] = Header(default=None),
):
    user_id = get_user_id(x_user_id)
    database.set_user_language(user_id, language)
    return {"language": language}


@app.get("/api/language")
def get_language(x_user_id: Optional[str] = Header(default=None)):
    user_id = get_user_id(x_user_id)
    return {"language": database.get_user_language(user_id)}


# ── health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    ollama_ok = await controller.llm_orchestrator.is_ollama_available()
    return {
        "status": "ok",
        "ollama": ollama_ok,
        "supported_regions": [r["code"] for r in knowledge_base.list_supported_regions()],
    }


# ── static frontend ───────────────────────────────────────────────────────────
_FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_FRONTEND):
    app.mount("/", StaticFiles(directory=_FRONTEND, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
