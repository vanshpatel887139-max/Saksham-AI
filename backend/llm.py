"""Thin LLM client for SakshamAI.

Uses Groq's OpenAI-compatible chat completions API. All secrets live in
backend/.env (gitignored) — this module never exposes the key and every call
has a graceful failure path so callers can fall back to deterministic mock
logic when the LLM is unavailable.
"""

import json
import os
import re
from typing import List, Dict

import httpx
from dotenv import load_dotenv

load_dotenv()

GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")


def _positive_float(name: str, default: float) -> float:
    """Read a float from the environment, falling back on anything unusable.

    These are evaluated at import time, and `main.py` imports this module, so a
    bare `float(...)` here takes the whole application down: one typo in a
    dashboard value ("60s", "1m", a stray space) raises ValueError while the
    import chain is still running, and the process exits before it can serve
    `/api/health` or report why. The AI features are an optional convenience
    that already degrade to deterministic logic when unavailable, so a
    malformed tuning knob should cost that and nothing more.

    Mirrors `_positive_int` in database.py, which fails with the variable name
    rather than letting int() explode inside a request handler.
    """
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    # 0 or negative is meaningless for both temperature and a timeout, and httpx
    # rejects a non-positive timeout outright, so treat it as unset too.
    return value if value > 0 else default


GROQ_TEMPERATURE = _positive_float("GROQ_TEMPERATURE", 0.4)
GROQ_TIMEOUT = _positive_float("GROQ_TIMEOUT", 60)


class LLMUnavailableError(Exception):
    """Raised when the LLM cannot be reached or returns an error."""


def llm_available() -> bool:
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def model_name() -> str:
    return GROQ_MODEL


def chat(
    messages: List[Dict[str, str]],
    *,
    json_mode: bool = False,
    temperature: float | None = None,
    max_tokens: int = 1024,
) -> str:
    """Send a chat completion request and return the assistant text.

    Raises LLMUnavailableError on missing key, network failure, or non-2xx.
    """
    if not llm_available():
        raise LLMUnavailableError("GROQ_API_KEY not configured")

    body: Dict = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature if temperature is not None else GROQ_TEMPERATURE,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    try:
        with httpx.Client(timeout=GROQ_TIMEOUT) as client:
            resp = client.post(
                f"{GROQ_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
    except httpx.HTTPError as e:
        raise LLMUnavailableError(f"LLM network error: {e}") from e

    if resp.status_code != 200:
        raise LLMUnavailableError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise LLMUnavailableError(f"Malformed LLM response: {e}") from e


def extract_json(text: str) -> dict:
    """Extract a JSON object from an LLM reply (strips ``` fences if present)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError("No JSON object found in LLM response")


def system(prompt: str) -> Dict[str, str]:
    return {"role": "system", "content": prompt}


def user(content: str) -> Dict[str, str]:
    return {"role": "user", "content": content}


def assistant(content: str) -> Dict[str, str]:
    return {"role": "assistant", "content": content}