"""Chat endpoint — conversational goal elicitation via Ollama."""
from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.models import User
from app.schemas.schemas import ChatMessage, ChatResponse
from app.services.ai_service import ollama_service
import re

router = APIRouter(prefix="/chat", tags=["chat"])

# Simple per-user in-memory history. Production: persist to DB.
_HISTORY: dict[int, list[dict]] = {}


@router.post("/", response_model=ChatResponse)
async def chat(msg: ChatMessage, user: User = Depends(get_current_user)):
    history = _HISTORY.setdefault(user.id, [])
    reply = await ollama_service.chat(msg.message, history)

    # Detect the "ready to generate" tag
    suggest = False
    extracted_goal = None
    match = re.search(r"\[READY_TO_GENERATE:\s*(.+?)\]", reply)
    if match:
        suggest = True
        extracted_goal = match.group(1).strip()
        reply = re.sub(r"\[READY_TO_GENERATE:.+?\]", "", reply).strip()

    history.append({"role": "user", "content": msg.message})
    history.append({"role": "assistant", "content": reply})
    if len(history) > 20:
        _HISTORY[user.id] = history[-20:]

    return ChatResponse(
        reply=reply,
        suggest_roadmap=suggest,
        extracted_goal=extracted_goal,
    )


@router.delete("/history")
async def clear_history(user: User = Depends(get_current_user)):
    _HISTORY.pop(user.id, None)
    return {"ok": True}
