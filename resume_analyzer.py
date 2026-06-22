# services/resume_analyzer.py
# ─────────────────────────────────────────────────────────────────────────────
# FIXES vs original:
#   FIX-1  Removed per-function genai.configure() → shared get_model()
#   FIX-2  Model: gemini-2.0-flash → gemini-1.5-flash
#   FIX-3  safe_json_parse() instead of bare json.loads()
#   FIX-4  generate_with_retry() for 429 / 503 resilience
#   FIX-5  Key validation via get_model()
# ─────────────────────────────────────────────────────────────────────────────

from gemini_client import get_model, generate_with_retry, safe_json_parse


def analyze_resume(text: str, api_key: str) -> dict:
    """
    Analyse resume text and return a comprehensive ATS report dict.

    Raises:
        GeminiKeyInvalidError / GeminiQuotaError / GeminiParseError / GeminiError
    """
    # FIX-1 + FIX-2
    model = get_model(api_key)

    prompt = f"""You are an expert HR consultant and ATS (Applicant Tracking System) specialist.
Analyse the following resume thoroughly.

RESUME CONTENT:
{text[:10000]}

Respond with ONLY a valid JSON object — no markdown fences, no prose:
{{
  "ats_score":          <integer 0-100>,
  "candidate_name":     "Extracted full name or 'Not Found'",
  "target_role":        "Inferred target role from the resume content",
  "experience_level":   "Fresher | Junior | Mid-level | Senior",
  "overall_impression": "2-3 sentence executive summary",
  "strengths": [
    {{"title": "Short title", "description": "1-2 sentence explanation"}}
  ],
  "weaknesses": [
    {{"title": "Short title", "description": "1-2 sentence explanation"}}
  ],
  "missing_skills":  ["skill 1", "skill 2"],
  "present_skills":  ["skill 1", "skill 2"],
  "ats_issues":      ["Issue 1 affecting ATS parsing", "Issue 2"],
  "improvements": [
    {{"priority": "High | Medium | Low", "action": "Specific improvement action"}}
  ],
  "section_scores": {{
    "contact_info":    <integer 0-100>,
    "work_experience": <integer 0-100>,
    "education":       <integer 0-100>,
    "skills":          <integer 0-100>,
    "formatting":      <integer 0-100>
  }},
  "keyword_density":    "Low | Medium | High — one-line comment",
  "recommended_roles":  ["Role 1", "Role 2", "Role 3"]
}}

Rules:
  ats_score    → based on keyword density, section clarity, measurable achievements, formatting
  strengths    → 4-5 items
  weaknesses   → 4-5 items
  missing_skills → 5-8 skills relevant to target role
  ats_issues   → 4-6 items (missing keywords, tables, graphics, headers, etc.)
  improvements → exactly 5 items, sorted High → Medium → Low
"""

    # FIX-4
    raw = generate_with_retry(model, prompt, context="resume_analyzer")
    # FIX-3
    return safe_json_parse(raw, context="resume_analyzer")
