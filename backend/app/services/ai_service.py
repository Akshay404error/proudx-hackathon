"""AI service powered by local Ollama.

Two responsibilities:
  1. Conversational chat with the learner — natural goal elicitation.
  2. Structured roadmap generation — strict JSON output that we parse into DB rows.

Everything runs locally; no external API calls.
"""
from __future__ import annotations
import json
import re
import logging
from typing import Optional, List, Dict, Any
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


SYSTEM_CHAT_PROMPT = """You are PathForge, a friendly AI learning coach.
Your job is to help learners articulate their learning goals clearly.

Behavior rules:
- Keep replies concise (2-4 sentences).
- Ask ONE focused clarifying question at a time when the goal is vague.
- Once you have enough info (target skill, current level, available time),
  end your reply with a special tag on its own line:
  [READY_TO_GENERATE: <one-line goal summary>]
- Never invent the user's goal — only summarize what they told you.
- Be warm but practical. No filler phrases like "Great question!"."""


ROADMAP_GENERATION_PROMPT = """You are an expert curriculum designer.
Generate a complete learning roadmap as STRICT JSON. No prose outside JSON.

Output schema:
{{
  "title": "string — short title",
  "description": "string — 1-2 sentence overview",
  "milestones": [
    {{
      "title": "string",
      "description": "string",
      "estimated_hours": <int>,
      "lessons": [
        {{
          "title": "string",
          "summary": "string — 1 sentence",
          "content_type": "article|docs|interactive",
          "estimated_minutes": <int>,
          "resources": [
            {{ "title": "string", "url": "string", "type": "article|docs" }}
          ]
        }}
      ],
      "projects": [
        {{
          "title": "string",
          "description": "string",
          "requirements": ["bullet 1", "bullet 2"]
        }}
      ]
    }}
  ]
}}

CRITICAL URL RULES (read carefully):
- DO NOT invent YouTube watch URLs. Never output a URL like "youtube.com/watch?v=XXXX"
  unless you are 100% certain the video exists. When in doubt, use a CHANNEL page instead:
  https://www.youtube.com/@freecodecamp
  https://www.youtube.com/@Fireship
  https://www.youtube.com/@TraversyMedia
  https://www.youtube.com/@TheNetNinja
- PREFER official documentation and well-known sites. Use these by default:
  * Python:        https://docs.python.org/3/tutorial/
  * JavaScript:    https://developer.mozilla.org/en-US/docs/Web/JavaScript
  * MDN (web):     https://developer.mozilla.org/
  * React:         https://react.dev/learn
  * FastAPI:       https://fastapi.tiangolo.com/
  * freeCodeCamp:  https://www.freecodecamp.org/learn
  * Real Python:   https://realpython.com/
  * GeeksForGeeks: https://www.geeksforgeeks.org/
  * LeetCode:      https://leetcode.com/problemset/
  * W3Schools is OK as a fallback only.
- Use the SITE ROOT or a STABLE TUTORIAL PAGE (e.g. /tutorial/, /learn/, /docs/).
  Do NOT make up deep article URLs you are not sure about.
- Each lesson should have 1-2 resources, no more.

Constraints:
- Generate {num_milestones} milestones total.
- 3-5 lessons per milestone.
- 1 capstone project per milestone.
- Order milestones from foundational to advanced.
- Tailor depth to skill level: {skill_level}.

Goal: {goal}
Total duration: {duration_weeks} weeks at {hours_per_week} hours/week.
Extra context: {extra_context}

Return ONLY the JSON object."""


class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self.timeout = httpx.Timeout(600.0, connect=10.0)

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    async def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Conversational reply. history = [{"role":"user|assistant","content":"..."}]"""
        messages = [{"role": "system", "content": SYSTEM_CHAT_PROMPT}]
        if history:
            messages.extend(history[-10:])  # last 10 turns
        messages.append({"role": "user", "content": message})

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.7},
                },
            )
            r.raise_for_status()
            data = r.json()
            return data.get("message", {}).get("content", "").strip()

    async def generate_roadmap(
        self,
        goal: str,
        skill_level: str = "beginner",
        duration_weeks: int = 12,
        hours_per_week: int = 10,
        extra_context: str = "",
    ) -> Dict[str, Any]:
        """Generate structured roadmap JSON."""
        # Heuristic: 1 milestone per ~1.5 weeks, capped 4-10
        num_milestones = max(4, min(10, duration_weeks // 2))

        prompt = ROADMAP_GENERATION_PROMPT.format(
            num_milestones=num_milestones,
            skill_level=skill_level,
            goal=goal,
            duration_weeks=duration_weeks,
            hours_per_week=hours_per_week,
            extra_context=extra_context or "none",
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",  # Ollama JSON-mode
                    "options": {"temperature": 0.6},
                },
            )
            r.raise_for_status()
            raw = r.json().get("response", "")

        return self._parse_roadmap_json(raw, goal, duration_weeks)

    def _parse_roadmap_json(self, raw: str, goal: str, weeks: int) -> Dict[str, Any]:
        """Robust JSON parsing with fallback to a sensible default."""
        # Strip code-fence wrappers if any
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        try:
            data = json.loads(cleaned)
            # Sanity: must have title and milestones
            if "title" not in data or "milestones" not in data:
                raise ValueError("Missing required fields")
            return data
        except Exception as e:
            logger.error(f"Roadmap JSON parse failed: {e}. Using fallback.")
            return self._fallback_roadmap(goal, weeks)

    def _fallback_roadmap(self, goal: str, weeks: int) -> Dict[str, Any]:
        """Defensive fallback if Ollama is unavailable / returns junk."""
        return {
            "title": f"Learning Path: {goal[:60]}",
            "description": f"A {weeks}-week journey toward: {goal}",
            "milestones": [
                {
                    "title": "Foundations",
                    "description": "Build core understanding.",
                    "estimated_hours": 15,
                    "lessons": [
                        {
                            "title": "Introduction & key concepts",
                            "summary": "Learn the fundamentals.",
                            "content_type": "article",
                            "estimated_minutes": 30,
                            "resources": [
                                {"title": "MDN Web Docs", "url": "https://developer.mozilla.org",
                                 "type": "docs"}
                            ],
                        }
                    ],
                    "projects": [
                        {
                            "title": "Hello World",
                            "description": "Build your first working example.",
                            "requirements": ["Setup environment", "Run sample code"],
                        }
                    ],
                }
            ],
        }


# Singleton
ollama_service = OllamaService()