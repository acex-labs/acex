
from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from acex.constants import BASE_URL


class AskRequest(BaseModel):
    prompt: str
    messages: list[dict] = []  # Optional conversation history


def create_router(automation_engine):

    if not hasattr(automation_engine, "ai_ops_manager"):
        return None

    router = APIRouter(prefix=f"{BASE_URL}/ai_ops")
    tags = ["AI Operations"]

    aiom = automation_engine.ai_ops_manager
    
    # HEAD is necessary for frontend to know that ai ops is enabled
    @router.head("/ai/ask/", tags=tags)
    async def ai_enabled():
        return {}

    @router.post("/ai/ask/", tags=tags)
    async def ask(request: AskRequest):
        async def sse_stream():
            async for chunk in aiom.ask(request.prompt, request.messages):
                # Server-Sent Events format
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        
        return StreamingResponse(
            sse_stream(),
            media_type="text/event-stream"
        )

    return router




