"""What a codec returns: the rendered payload or parsed tree, plus metadata tying text to the tree."""

from pydantic import BaseModel

from acex_devkit.models.composed_configuration import ComposedConfiguration


class Span(BaseModel):
    """A run of lines in configuration text that expresses one component. Spans nest: an interface's
    span holds the span of its storm-control settings."""

    start: int  # first line, 1-based
    end: int  # last line, inclusive
    path: list[str]  # where the component sits in ComposedConfiguration, e.g. ["interfaces", "uplink"]


class UnmatchedLine(BaseModel):
    """A line of observed configuration the driver couldn't parse into the tree."""

    line: str  # as written on the device, indentation included
    parents: list[str] = []  # header lines of the blocks it sits in, outermost first


class RenderMetadata(BaseModel):
    spans: list[Span] = []
    # Of a patch: the paths of the changes the syntax has no lines for, so they were left out. Like unmatched
    # lines on parse, they say how far the driver covers the configuration.
    unrendered: list[list[str]] = []


class RenderResult[Payload](BaseModel):
    payload: Payload
    metadata: RenderMetadata = RenderMetadata()


class ParseMetadata(BaseModel):
    spans: list[Span] = []
    unmatched: list[UnmatchedLine] = []


class ParseResult(BaseModel):
    configuration: ComposedConfiguration
    metadata: ParseMetadata = ParseMetadata()
