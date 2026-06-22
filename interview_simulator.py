# services/interview_simulator.py
# ─────────────────────────────────────────────────────────────────────────────
# FIXES vs original:
#   FIX-1  Removed per-function genai.configure() calls → shared get_model()
#   FIX-2  Model: gemini-2.0-flash → gemini-1.5-flash
#   FIX-3  safe_json_parse() wraps all json.loads() calls
#   FIX-4  generate_with_retry() adds 429 / 503 back-off
#   FIX-5  Key validation via get_model()
#   FIX-6  Guard against empty evaluations list in generate_final_report()
# ─────────────────────────────────────────────────────────────────────────────

from gemini_client import get_model, generate_with_retry, safe_json_parse

ROLE_CONTEXTS = {
    "software_developer": "data structures, algorithms, OOP, system design, coding practices, CS fundamentals",
    "aiml_engineer":      "machine learning, deep learning, neural networks, Python, TensorFlow/PyTorch, MLOps, statistics",
    "data_analyst":       "SQL, data visualisation, Excel, Python/R, statistical analysis, BI tools (Tableau/Power BI)",
    "web_developer":      "HTML, CSS, JavaScript, React/Vue/Angular, REST APIs, responsive design, web performance",
    "hr_interview":       "behavioural questions, situational judgement, teamwork, leadership, communication, career goals",
}


def get_interview_question(role: str, question_number: int, history: list, api_key: str) -> dict:
    """
    Generate the next interview question.

    Returns: {"question": str, "question_number": int, "is_final": bool}
    """
    # FIX-1 + FIX-2
    model = get_model(api_key)

    context      = ROLE_CONTEXTS.get(role, "general professional skills")
    is_final     = question_number >= 8
    history_text = "\n".join(
        f"Q{i+1}: {h['question']}\nA{i+1}: {h['answer']}"
        for i, h in enumerate(history)
    ) or "This is the first question."

    prompt = f"""You are a professional interviewer conducting a {role.replace('_', ' ')} interview.
Focus areas: {context}

Previous Q&A:
{history_text}

Generate question {question_number} of 8.
{"This is the FINAL question — make it appropriately challenging." if is_final else ""}

Rules:
- Progress from basic (Q1-3) to intermediate (Q4-6) to advanced (Q7-8)
- Be specific and realistic, not generic
- HR mode: behavioural / situational questions only

Respond with ONLY valid JSON, no markdown, no extra text:
{{"question": "...", "question_number": {question_number}, "is_final": {str(is_final).lower()}}}"""

    # FIX-4
    raw = generate_with_retry(model, prompt, context="interview/get_question")
    # FIX-3
    return safe_json_parse(raw, context="interview/get_question")


def evaluate_answer(role: str, question: str, answer: str, api_key: str) -> dict:
    """
    Evaluate a single answer.

    Returns scores dict with keys:
        confidence_score, communication_score, technical_score, overall_score,
        strength, improvement, model_answer_hint
    """
    model   = get_model(api_key)  # FIX-1
    context = ROLE_CONTEXTS.get(role, "general professional skills")

    prompt = f"""You are an expert interview evaluator for a {role.replace('_', ' ')} position.
Focus areas: {context}

Question: {question}
Candidate's Answer: {answer}

Evaluate and respond with ONLY valid JSON (no markdown):
{{
  "confidence_score":    <integer 0-100>,
  "communication_score": <integer 0-100>,
  "technical_score":     <integer 0-100>,
  "overall_score":       <integer 0-100>,
  "strength":            "One key strength of this answer",
  "improvement":         "One specific, actionable improvement",
  "model_answer_hint":   "Brief hint about what an ideal answer includes"
}}

Scoring:
  confidence_score    → assertiveness, structure, certainty of delivery
  communication_score → clarity, grammar, logical flow
  technical_score     → accuracy and depth of domain knowledge
  overall_score       → weighted: technical 50% + communication 30% + confidence 20%"""

    raw = generate_with_retry(model, prompt, context="interview/evaluate_answer")
    return safe_json_parse(raw, context="interview/evaluate_answer")


def generate_final_report(role: str, evaluations: list, api_key: str) -> dict:
    """
    Generate a comprehensive final report from all per-question evaluations.

    FIX-6: Guards against empty evaluations list.
    """
    if not evaluations:
        # Should never happen, but prevents ZeroDivisionError
        return {
            "verdict": "Incomplete",
            "overall_score": 0,
            "confidence_score": 0,
            "communication_score": 0,
            "technical_score": 0,
            "executive_summary": "The interview session had no completed answers.",
            "top_strengths": [],
            "improvement_areas": [],
            "recommended_resources": [],
            "next_steps": "Please complete a full interview session.",
        }

    model = get_model(api_key)  # FIX-1

    n = len(evaluations)
    avg_confidence    = round(sum(e.get("confidence_score",    0) for e in evaluations) / n, 1)
    avg_communication = round(sum(e.get("communication_score", 0) for e in evaluations) / n, 1)
    avg_technical     = round(sum(e.get("technical_score",     0) for e in evaluations) / n, 1)
    avg_overall       = round(sum(e.get("overall_score",       0) for e in evaluations) / n, 1)

    import json as _json
    eval_summary = _json.dumps(evaluations, indent=2)

    prompt = f"""You are generating a final interview report for a {role.replace('_', ' ')} candidate.

Individual question evaluations ({n} questions):
{eval_summary}

Computed averages:
  Confidence:    {avg_confidence}/100
  Communication: {avg_communication}/100
  Technical:     {avg_technical}/100
  Overall:       {avg_overall}/100

Generate a professional final report as ONLY valid JSON (no markdown):
{{
  "verdict":           "Selected | Strong Candidate | Needs Improvement | Not Recommended",
  "overall_score":      {avg_overall},
  "confidence_score":   {avg_confidence},
  "communication_score":{avg_communication},
  "technical_score":    {avg_technical},
  "executive_summary":  "2-3 sentence professional assessment",
  "top_strengths":      ["strength 1", "strength 2", "strength 3"],
  "improvement_areas":  ["area 1", "area 2", "area 3"],
  "recommended_resources": ["topic/resource 1", "topic/resource 2", "topic/resource 3"],
  "next_steps":         "Concrete, actionable advice for the candidate"
}}"""

    raw = generate_with_retry(model, prompt, context="interview/final_report")
    return safe_json_parse(raw, context="interview/final_report")
