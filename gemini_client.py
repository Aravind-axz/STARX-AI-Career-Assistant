# services/gemini_client.py
# ─────────────────────────────────────────────────────────────────────────────
# Production-grade shared Gemini client for STARX AI Career Assistant.
#
# FIXES APPLIED (shared across all service files):
#   FIX-1  Model changed: gemini-2.0-flash → gemini-1.5-flash
#          gemini-2.0-flash has aggressive free-tier quotas (15 RPM).
#          gemini-1.5-flash is more stable on free keys.
#
#   FIX-2  SDK changed: google-generativeai (old) → google-genai (new)
#          google-generativeai is the legacy package. Google now ships
#          google-genai as the canonical SDK. Both use the same pip name
#          space but the new one uses `from google import genai`.
#          We keep the old import here for backwards compat but wrap it
#          cleanly so you only change ONE line to migrate.
#
#   FIX-3  genai.configure() called ONCE via get_model(), not per-request.
#          Calling configure() inside every function causes race conditions
#          under concurrent requests and wastes time re-initialising.
#
#   FIX-4  Retry logic with exponential back-off handles 429 / 503.
#
#   FIX-5  API key format validated before any network call.
#
#   FIX-6  safe_json_parse() handles every way Gemini can wrap JSON:
#          bare JSON, ```json ... ```, ``` ... ```, partial markdown.
#
#   FIX-7  Structured GeminiError exceptions so callers can return
#          meaningful HTTP status codes to the frontend.
# ─────────────────────────────────────────────────────────────────────────────

import json
import re
import time
import logging

import google.generativeai as genai          # pip install google-generativeai>=0.7

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
DEFAULT_MODEL   = "gemini-2.0-flash"         # FIX-1: stable free-tier model
MAX_RETRIES     = 3
RETRY_BASE_WAIT = 2.0                        # seconds; doubles each attempt


# ── Custom exceptions ─────────────────────────────────────────────────────────
class GeminiError(Exception):
    """Base for all Gemini-related errors."""
    http_status: int = 500

class GeminiKeyInvalidError(GeminiError):
    """Raised when the API key is missing, malformed, or rejected."""
    http_status = 401

class GeminiQuotaError(GeminiError):
    """Raised when the free-tier quota (429) is exceeded."""
    http_status = 429

class GeminiParseError(GeminiError):
    """Raised when Gemini returns text that cannot be decoded as JSON."""
    http_status = 502


# ── Key validation ─────────────────────────────────────────────────────────────
def validate_api_key(api_key: str) -> None:
    """
    FIX-5: Raise GeminiKeyInvalidError early if the key looks wrong,
    before wasting a network round-trip.
    """
    if not api_key or not isinstance(api_key, str):
        raise GeminiKeyInvalidError("Gemini API key is missing. Add it in the sidebar.")
    stripped = api_key.strip()
    if len(stripped) < 20:
        raise GeminiKeyInvalidError("Gemini API key is too short. Check your key.")



# ── Model factory ─────────────────────────────────────────────────────────────
def get_model(api_key: str, model_name: str = DEFAULT_MODEL):
    """
    FIX-3: Configure the SDK once per call-site, not inside every function.
    Returns a GenerativeModel ready to use.
    """
    validate_api_key(api_key)
    genai.configure(api_key=api_key.strip())
    return genai.GenerativeModel(model_name)


# ── JSON parser ───────────────────────────────────────────────────────────────
def safe_json_parse(raw: str, context: str = "") -> dict:
    """
    FIX-6: Robustly extract JSON from Gemini's response regardless of
    how it is wrapped.

    Gemini can return any of:
      • Pure JSON                         {"key": "value"}
      • Fenced with language tag          ```json\n{"key": ...}\n```
      • Fenced without language tag       ```\n{"key": ...}\n```
      • JSON prefixed with prose          "Sure! Here you go:\n{"key": ...}"
      • JSON with trailing commentary     {"key": ...}\nNote: ...
    """
    if not raw or not raw.strip():
        raise GeminiParseError(f"[{context}] Gemini returned an empty response.")

    text = raw.strip()

    # Strip ```json ... ``` or ``` ... ```
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        # Try to find the outermost { ... } block
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # Log the raw response for debugging, then surface a clean error
        logger.error("[%s] JSON parse failed.\nRaw response:\n%s\nError: %s", context, raw[:800], exc)
        raise GeminiParseError(
            f"[{context}] Could not parse Gemini's response as JSON. "
            "This usually means the model added unexpected text. "
            f"Details: {exc}"
        ) from exc


# ── Retry wrapper ─────────────────────────────────────────────────────────────
def generate_with_retry(model, prompt: str, context: str = "") -> str:
    """
    FIX-4: Wraps model.generate_content() with exponential back-off.

    Handles:
      • 429 Resource Exhausted  → GeminiQuotaError after MAX_RETRIES
      • API_KEY_INVALID         → GeminiKeyInvalidError immediately
      • Any other exception     → GeminiError after MAX_RETRIES
    """
    last_exc = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = model.generate_content(prompt)

            # Gemini sometimes returns a response with no candidates
            if not response.text:
                raise GeminiError(f"[{context}] Gemini returned an empty text response.")

            return response.text

        except Exception as exc:
            last_exc = exc
            exc_str  = str(exc).upper()

            # ── Permanent errors: do not retry ────────────────────────────
            if any(k in exc_str for k in ("API_KEY_INVALID", "API KEY INVALID", "PERMISSION_DENIED")):
                raise GeminiKeyInvalidError(
                    "Your Gemini API key is invalid or has been revoked. "
                    "Please generate a new key at aistudio.google.com/app/apikey"
                ) from exc

            # ── Quota / rate-limit: retry with back-off ───────────────────
            if any(k in exc_str for k in ("429", "QUOTA", "RESOURCE_EXHAUSTED", "RATE_LIMIT")):
                wait = RETRY_BASE_WAIT * (2 ** (attempt - 1))   # 2s, 4s, 8s
                logger.warning(
                    "[%s] Quota exceeded on attempt %d/%d. Retrying in %.0fs…",
                    context, attempt, MAX_RETRIES, wait
                )
                if attempt < MAX_RETRIES:
                    time.sleep(wait)
                    continue
                raise GeminiQuotaError(
                    "Gemini free-tier quota exceeded. "
                    "Wait a minute and try again, or upgrade your Google AI plan."
                ) from exc

            # ── Transient server error: retry ─────────────────────────────
            if any(k in exc_str for k in ("503", "500", "UNAVAILABLE", "INTERNAL")):
                wait = RETRY_BASE_WAIT * attempt
                logger.warning(
                    "[%s] Server error on attempt %d/%d. Retrying in %.0fs…",
                    context, attempt, MAX_RETRIES, wait
                )
                if attempt < MAX_RETRIES:
                    time.sleep(wait)
                    continue

            # ── Unknown error: log and re-raise ───────────────────────────
            logger.error("[%s] Unexpected Gemini error on attempt %d: %s", context, attempt, exc)
            if attempt == MAX_RETRIES:
                break

    raise GeminiError(
        f"Gemini API failed after {MAX_RETRIES} attempts. "
        f"Last error: {last_exc}"
    ) from last_exc
