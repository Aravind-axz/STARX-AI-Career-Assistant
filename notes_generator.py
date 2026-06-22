# services/notes_generator.py
# ─────────────────────────────────────────────────────────────────────────────
# FIXES vs original:
#   FIX-1  Removed per-function genai.configure() → uses shared get_model()
#   FIX-2  Model changed to gemini-1.5-flash (stable free-tier)
#   FIX-3  json.loads wrapped with safe_json_parse (handles all fence styles)
#   FIX-4  Retry logic inherited from generate_with_retry()
#   FIX-5  Key validation inherited from get_model()
#   FIX-6  Descriptive error messages bubble up to Flask → real HTTP codes
# ─────────────────────────────────────────────────────────────────────────────

from gemini_client import get_model, generate_with_retry, safe_json_parse


def generate_notes(text: str, api_key: str) -> dict:
    """
    Takes extracted document text and returns a structured study-notes dict.

    Raises:
        GeminiKeyInvalidError – bad/missing API key
        GeminiQuotaError      – free-tier rate limit hit
        GeminiParseError      – Gemini response was not valid JSON
        GeminiError           – any other Gemini failure
    """
    # FIX-1 + FIX-2: configure once, use stable model
    model = get_model(api_key)

    prompt = f"""
You are an expert academic assistant. Analyse the following document and generate
comprehensive study material.

DOCUMENT CONTENT:
{text[:12000]}

Respond with ONLY a single valid JSON object — no markdown fences, no prose before
or after, no trailing commas.  Use exactly these keys:

{{
  "short_summary": "2-3 sentence overview",
  "detailed_summary": "Thorough paragraph-form summary covering all major points",
  "key_concepts": ["concept 1", "concept 2"],
  "two_mark_questions":  [{{"question": "...", "answer": "..."}}],
  "five_mark_questions": [{{"question": "...", "answer": "..."}}],
  "ten_mark_questions":  [{{"question": "...", "answer": "..."}}],
  "viva_questions":      [{{"question": "...", "answer": "..."}}],
  "mcqs": [
    {{
      "question": "...",
      "options":  ["A) ...", "B) ...", "C) ...", "D) ..."],
      "answer":   "A"
    }}
  ],
  "quick_revision": ["bullet 1", "bullet 2"]
}}

Counts required:
  2-mark  → 5 Q&A  (answers: 2-3 sentences)
  5-mark  → 4 Q&A  (answers: 4-6 sentences)
  10-mark → 3 Q&A  (answers: 8-12 sentences)
  viva    → 6 Q&A  (answers: 1-2 sentences)
  mcqs    → 6 items (4 options each; answer field = correct letter only)
  quick_revision → 10 bullet points
"""

    # FIX-4: retry wrapper handles 429 and transient errors
    raw = generate_with_retry(model, prompt, context="notes_generator")

    # FIX-3: robust JSON extraction + clean error message
    return safe_json_parse(raw, context="notes_generator")
