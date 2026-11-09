"""Where rendered configuration comes from: the config component behind each block of text."""

from pydantic import BaseModel

from acex_devkit.models.codec_result import Span


class ComponentOrigin(BaseModel):
    """The config component placed at `path` in the composed tree, and the config map code that added it."""

    path: list[str]
    component: str  # config component class, e.g. "FrontpanelPort"
    name: str | None = None
    config_map: str | None = None
    file: str | None = None  # relative to the config map directory it was loaded from
    line: int | None = None


class OriginSpan(Span):
    origin: ComponentOrigin | None = None  # the component whose path is the longest prefix of the span's


class AnnotatedConfigResponse(BaseModel):
    """Rendered configuration text with every span tied to the component it came from."""

    content: str
    spans: list[OriginSpan] = []
