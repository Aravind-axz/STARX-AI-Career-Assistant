# services/study_planner.py
# Generates personalized study timetables and preparation roadmaps

import google.generativeai as genai
import json

def generate_study_plan(exam_date: str, subjects: list, daily_hours: int, api_key: str) -> dict:
    """
    Generates a personalized study timetable and roadmap using Gemini.
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    subjects_str = ", ".join(subjects)

    prompt = f"""
You are an expert academic coach and study strategist.

Student's study plan request:
- Exam Date: {exam_date}
- Subjects: {subjects_str}
- Daily Study Hours Available: {daily_hours} hours

Generate a comprehensive, personalized study plan as ONLY valid JSON (no markdown):
{{
  "total_days": <number of days until exam>,
  "daily_hours": {daily_hours},
  "strategy_overview": "2-3 sentence overview of the study approach",
  "subject_allocation": [
    {{
      "subject": "Subject Name",
      "total_hours": <hours>,
      "priority": "High/Medium/Low",
      "difficulty": "Hard/Medium/Easy",
      "completion_percentage": <0-100>
    }}
  ],
  "weekly_schedule": [
    {{
      "week": 1,
      "theme": "Week theme/focus",
      "daily_plan": [
        {{
          "day": "Monday",
          "subjects": [
            {{"subject": "...", "hours": <hours>, "topics": ["topic 1", "topic 2"]}}
          ],
          "total_hours": <hours>
        }}
      ]
    }}
  ],
  "milestones": [
    {{
      "day": <day number>,
      "milestone": "What should be completed by this day",
      "check": "How to verify completion"
    }}
  ],
  "revision_strategy": [
    "Revision tip 1",
    "Revision tip 2",
    "Revision tip 3",
    "Revision tip 4",
    "Revision tip 5"
  ],
  "exam_day_tips": ["Tip 1", "Tip 2", "Tip 3", "Tip 4"],
  "productivity_techniques": [
    {{"technique": "Name", "description": "How to apply it"}}
  ],
  "emergency_plan": "What to do if falling behind schedule"
}}

Rules:
- weekly_schedule: Generate weeks until exam (max 4 weeks shown)
- Each week: show 7 days with realistic subject distribution
- Allocate more hours to harder/higher-priority subjects
- Include breaks: max 3 hours of continuous study
- milestones: one per week
- productivity_techniques: 3 techniques (Pomodoro, active recall, spaced repetition etc.)
- Keep subject names exactly as provided by the student
"""
    response = model.generate_content(prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    if raw.endswith("```"):
        raw = raw[:-3]

    return json.loads(raw.strip())
