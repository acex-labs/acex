import json
from typing import Literal

from acex.ai_ops.ai_ops import USAGE_MARKER, AllLevelsExhaustedError
from acex.ai_ops.web_ui_context import WEB_UI_SYSTEM_PROMPTS
from acex.constants import BASE_URL
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


class AskRequest(BaseModel):
    prompt: str
    messages: list[dict] = []
    context: str | None = None
    # Explicit model override: "provider/model" or "model" (first chain provider).
    # When omitted, the task's failover chain is used.
    model: str | None = None


class ConfigAnalysisRequest(BaseModel):
    task: Literal["explain", "risk_assessment", "alignment"]
    diff: str
    node_hostname: str | None = None
    snap_a_hash: str | None = None
    snap_b_hash: str | None = None
    snap_a_timestamp: str | None = None
    snap_b_timestamp: str | None = None
    model: str | None = None


def create_router(automation_engine):

    if not hasattr(automation_engine, "ai_ops_manager"):
        return None

    router = APIRouter(prefix=f"{BASE_URL}/ai_ops")
    tags = ["AI Operations"]

    aiom = automation_engine.ai_ops_manager

    # HEAD lets the frontend detect whether AI ops is enabled
    @router.head("/ai/ask", tags=tags)
    async def ai_enabled():
        return {}

    @router.get("/providers", tags=tags)
    async def list_providers():
        """List configured AI providers enriched with health + available models.

        Model lists are cached per provider (~60s). A provider that is
        unreachable is still returned, with status "unreachable" and its
        static_models (if any) as the model list.
        """
        providers = []
        for info in aiom.providers_info():
            models = await aiom.list_models(info["name"])
            providers.append(
                {
                    **info,
                    "status": "ok" if models is not None else "unreachable",
                    "models": models or [],
                }
            )

        # Per-task chain overview so the frontend can pre-select defaults
        chains = {
            task: [{"provider": lvl.provider, "model": lvl.model} for lvl in aiom.settings.chain_for(task)]
            for task in ("default", "chat", "analysis")
            if aiom.settings.chains.get(task) or task == "default"
        }

        return {"providers": providers, "chains": chains}

    @router.get("/models", tags=tags)
    async def list_models(
        provider: str = Query(..., description="Provider name"),
        refresh: bool = Query(False, description="Bypass the model list cache"),
        include_all: bool = Query(False, description="Include non-chat models (embeddings, STT, rerank, image)"),
    ):
        """List models for one provider (cache-aware refresh endpoint)."""
        if provider not in aiom.settings.providers:
            raise HTTPException(status_code=404, detail=f"Unknown provider '{provider}'")
        models = await aiom.list_models(provider, force_refresh=refresh, include_all=include_all)
        if models is None:
            raise HTTPException(status_code=502, detail=f"Provider '{provider}' did not return a model list")
        return {"provider": provider, "models": models}

    @router.post("/ai/ask", tags=tags)
    async def ask(request: AskRequest):
        async def sse_stream():
            try:
                async for chunk in aiom.ask(
                    request.prompt,
                    request.messages,
                    context=request.context,
                    extra_system_prompts=WEB_UI_SYSTEM_PROMPTS,
                    model=request.model,
                ):
                    if chunk == USAGE_MARKER:
                        yield f"data: {json.dumps({'usage': aiom._last_usage})}\n\n"
                    else:
                        yield f"data: {json.dumps({'content': chunk})}\n\n"
            except AllLevelsExhaustedError as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"

        return StreamingResponse(sse_stream(), media_type="text/event-stream")

    @router.post("/ai/config_analysis", tags=tags)
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
                async for chunk in aiom.analyze_config_diff(request.task, request.diff, context, model=request.model):
                    if chunk == USAGE_MARKER:
                        yield f"data: {json.dumps({'usage': aiom._last_usage})}\n\n"
                    else:
                        yield f"data: {json.dumps({'content': chunk})}\n\n"
            except AllLevelsExhaustedError as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"

        return StreamingResponse(sse_stream(), media_type="text/event-stream")

    return router
