from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class DetectedItem(BaseModel):
    item_name: str
    confidence: float
    bbox: BoundingBox
    material: Optional[str] = None
    material_confidence: Optional[float] = None
    material_uncertain: bool = False
    category: Optional[str] = None  # recyclable | compostable | landfill | special disposal


class ScanResult(BaseModel):
    items: List[DetectedItem]
    image_width: int
    image_height: int
    has_low_confidence: bool = False
    clutter_warning: bool = False
    no_items_found: bool = False


class InstructionsResult(BaseModel):
    item_name: str
    material: str
    region: str
    bin_color: Optional[str] = None
    bin_color_hex: Optional[str] = None
    category: str
    prep_steps: List[str]
    impact: str = ""
    notes: str = ""
    location_specific: bool = True
    language: str = "en"


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    item_name: str
    material: str
    region: str
    language: str = "en"
    history: List[ChatMessage] = []


class ChatResponse(BaseModel):
    response: str


class LocationRequest(BaseModel):
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class LocationResponse(BaseModel):
    country: str
    region_code: str
    display_name: str


class HistoryEntry(BaseModel):
    id: Optional[int] = None
    item_name: str
    material: str
    category: str
    region: str
    timestamp: datetime
    co2_saved: float = 0.0
    energy_saved: float = 0.0


class ImpactStats(BaseModel):
    total_scans: int
    total_co2_saved: float
    total_energy_saved: float
    history: List[HistoryEntry]


class ConsentRequest(BaseModel):
    consent: bool


class ConsentResponse(BaseModel):
    consent: bool
    message: str
