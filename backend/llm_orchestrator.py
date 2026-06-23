"""LLM Prompt Orchestrator: Ollama client with 5 s timeout and fallback (SUC4, design decisions #3, #8)."""
import asyncio
import logging
from typing import List, Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"
OLLAMA_MODEL = "llama3"          # can also be "mistral" or "llama3:8b"
LLM_TIMEOUT = 120.0              # Ollama needs up to 60 s to load model on first call
CHAT_TIMEOUT = 120.0
MAX_HISTORY = 6                  # keep last N message pairs for chat context

FALLBACK_MESSAGE = (
    "The AI assistant is currently unavailable. "
    "Please check your local municipal website for recycling guidelines, "
    "or try again in a moment."
)

_LANG_NAMES = {
    "en": "English",
    "de": "German",
}

SYSTEM_PROMPT_TEMPLATE = """\
You are RecycleBot, an assistant that ONLY answers questions about waste sorting, recycling, and disposal.
Politely decline anything off-topic and redirect to recycling questions.

Item: {item_name} | Material: {material} | Region: {region}

Official local rules (authoritative; base your answer ONLY on these rules):
{rules_text}

You MUST respond entirely in {language_name}. Every word of your response must be in {language_name}.
Be concise and step-by-step.
Never invent bin colors or local regulations not present in the rules above.
If no local rules are provided, give general advice based on the material type and clearly state
that location-specific rules are unavailable for this region.\
"""


def _build_rules_text(rule: Optional[Dict[str, Any]]) -> str:
    if not rule:
        return "(No location-specific rules available — give general material-based advice.)"
    lines = []
    if rule.get("bin_color"):
        lines.append(f"Bin color: {rule['bin_color']}")
    if rule.get("category"):
        lines.append(f"Category: {rule['category']}")
    if rule.get("prep"):
        lines.append("Preparation steps: " + "; ".join(rule["prep"]))
    if rule.get("deposit_return"):
        lines.append("Deposit-return system: yes")
    if rule.get("notes"):
        lines.append(f"Note: {rule['notes']}")
    return "\n".join(lines) if lines else "(No rules found for this material.)"


async def generate_instructions(
    item_name: str,
    material: str,
    region: str,
    language: str,
    rule: Optional[Dict[str, Any]],
) -> str:
    """Generate disposal instructions via LLM. Returns fallback string on failure."""
    language_name = _LANG_NAMES.get(language, "English")
    system = SYSTEM_PROMPT_TEMPLATE.format(
        item_name=item_name,
        material=material,
        region=region,
        rules_text=_build_rules_text(rule),
        language_name=language_name,
    )
    user_msg = (
        f"Please give me clear, step-by-step disposal instructions for a {item_name} "
        f"made of {material} in {region}. Include which bin to use and any preparation steps."
    )
    return await _call_ollama(system, [{"role": "user", "content": user_msg}], LLM_TIMEOUT)


async def chat(
    message: str,
    item_name: str,
    material: str,
    region: str,
    language: str,
    rule: Optional[Dict[str, Any]],
    history: List[Dict[str, str]],
) -> str:
    """Answer a follow-up question in context. (Req12–13)"""
    language_name = _LANG_NAMES.get(language, "English")
    system = SYSTEM_PROMPT_TEMPLATE.format(
        item_name=item_name,
        material=material,
        region=region,
        rules_text=_build_rules_text(rule),
        language_name=language_name,
    )
    messages = history[-MAX_HISTORY:] + [{"role": "user", "content": message}]
    return await _call_ollama(system, messages, CHAT_TIMEOUT)


async def _call_ollama(
    system: str,
    messages: List[Dict[str, str]],
    timeout: float,
) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 512},
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"].strip()
    except (httpx.TimeoutException, asyncio.TimeoutError):
        logger.warning("Ollama request timed out after %.1f s.", timeout)
        return FALLBACK_MESSAGE
    except Exception as e:
        logger.warning("Ollama unavailable: %s", e)
        return FALLBACK_MESSAGE


async def is_ollama_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            return r.status_code == 200
    except Exception:
        return False
