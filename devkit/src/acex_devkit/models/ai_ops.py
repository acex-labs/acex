from pydantic import BaseModel


class AiAskRequest(BaseModel):
    """Body for `POST /ai_ops/ai/ask/`. Returns an SSE stream of str chunks."""

    question: str
    node_instance_id: int | None = None
    site: str | None = None


class AiAnalysisTask(BaseModel):
    """Task type for AI config-diff analysis."""

    name: str
    description: str = ""


class AiAnalysisRequest(BaseModel):
    """Body for `POST /ai_ops/ai/config_analysis/`. Returns an SSE stream."""

    task: str  # "explain" | "risk_assessment" | "alignment"
    diff: str
    node_instance_id: int | None = None
