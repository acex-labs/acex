from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Literal
import json

from acex.constants import BASE_URL


class AskRequest(BaseModel):
    prompt: str
    messages: list[dict] = []


class ConfigAnalysisRequest(BaseModel):
    task: Literal["explain", "risk_assessment", "alignment"]
    diff: str
    node_hostname: str | None = None
    snap_a_hash: str | None = None
    snap_b_hash: str | None = None
    snap_a_timestamp: str | None = None
    snap_b_timestamp: str | None = None


def create_router(automation_engine):

    if not hasattr(automation_engine, "ai_ops_manager"):
        return None

    router = APIRouter(prefix=f"{BASE_URL}/ai_ops")
    tags = ["AI Operations"]

    aiom = automation_engine.ai_ops_manager

    # HEAD lets the frontend detect whether AI ops is enabled
    @router.head("/ai/ask/", tags=tags)
    async def ai_enabled():
        return {}

    @router.post("/ai/ask/", tags=tags)
    async def ask(request: AskRequest):
        async def sse_stream():
            async for chunk in aiom.ask(request.prompt, request.messages):
                yield f"data: {json.dumps({'content': chunk})}\n\n"

        return StreamingResponse(sse_stream(), media_type="text/event-stream")

    @router.post("/ai/config_analysis/", tags=tags)
    async def config_analysis(request: ConfigAnalysisRequest):
        """Analyse a config diff with a focused task-specific prompt.

        Streams an SSE response identical in format to /ai/ask/.
        """
        if not request.diff or not request.diff.strip():
            raise HTTPException(status_code=422, detail="diff must not be empty")

        # Build a brief context string from optional metadata
        context_parts = []
        if request.node_hostname:
            context_parts.append(f"Device: {request.node_hostname}")
        if request.snap_a_hash and request.snap_b_hash:
            a = request.snap_a_hash[:10]
            b = request.snap_b_hash[:10]
            ts_a = f" ({request.snap_a_timestamp})" if request.snap_a_timestamp else ""
            ts_b = f" ({request.snap_b_timestamp})" if request.snap_b_timestamp else ""
            context_parts.append(f"Change: {a}{ts_a} → {b}{ts_b}")
        context = "\n".join(context_parts)

        async def sse_stream():
            try:
                async for chunk in aiom.analyze_config_diff(request.task, request.diff, context):
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"

        return StreamingResponse(sse_stream(), media_type="text/event-stream")

    return router




