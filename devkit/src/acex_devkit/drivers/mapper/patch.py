"""A diff as the lines that make a device match it, cut from full renders of the trees the diff was made from."""

from typing import Any

from acex_devkit.configdiffer import ComponentChange, ComponentDiffOp, ConfigDiffer, Diff
from acex_devkit.exceptions import DriverException
from acex_devkit.models.codec_result import RenderMetadata, RenderResult


class Rendered:
    """One full render of a tree, with the lines each component and each of its fields spans."""

    def __init__(self, mapper: Any, root: Any, context: Any):
        self.mapper = mapper
        result = mapper.render(root, context)
        self.lines = result.payload.split("\n") if result.payload else []
        self.spans: dict[tuple[str, ...], tuple[int, int]] = {}
        for span in result.metadata.spans:
            self.spans.setdefault(tuple(span.path), (span.start - 1, span.end - 1))
        self.components = set(ConfigDiffer().flatten(root))

    def span(self, path: list[str]) -> tuple[int, int]:
        return self.spans[tuple(path)]

    def has(self, path: list[str]) -> bool:
        return tuple(path) in self.spans

    def headed(self, start: int, end: int) -> bool:
        """Whether the span opens with a header the rest is nested under, e.g. `interface Gi1`."""
        depth = self.mapper.depth(self.lines[start])
        return end > start and all(self.mapper.depth(self.lines[i]) > depth for i in range(start + 1, end + 1))

    def context(self, start: int, end: int) -> list[str]:
        """The headers of the blocks the span sits in, outermost first."""
        headers = {s: self.lines[s] for s, e in self.spans.values() if s < start and e >= end and self.headed(s, e)}
        return [headers[s] for s in sorted(headers)]

    def own(self, path: list[str], start: int, end: int) -> list[int]:
        """The component's own lines: not its header, nor the lines of components nested in it."""
        nested = [
            self.spans[p]
            for p in self.spans
            if p in self.components and len(p) > len(path) and list(p[: len(path)]) == path
        ]
        first = start + 1 if self.headed(start, end) else start
        return [i for i in range(first, end + 1) if not any(s <= i <= e for s, e in nested)]

    def nests(self, path: list[str], name: str) -> bool:
        """Whether the component's field `name` holds components of its own, e.g. a network instance's vlans."""
        field = (*path, name)
        return any(p[: len(field)] == field for p in self.components)

    def attribute_lines(self, change: ComponentChange, lines: list[int]) -> list[int]:
        """Of the component's own lines, those spanned by a field the change names. All of them when no
        line is, e.g. a field written on a line together with others."""
        names = {attribute.attribute_name for attribute in change.changed_attributes}
        spanned = [self.spans[(*change.path, name)] for name in names if (*change.path, name) in self.spans]
        picked = [i for i in lines if any(s <= i <= e for s, e in spanned)]
        return picked or lines


class Patch:
    """Removed components negated from the observed render, then added and changed ones from the desired
    render, each under the headers of the blocks it sits in.

    An added component is written whole; a changed one only on the lines of the attributes that changed. A
    removed component with a header is removed by negating the header, which takes what's nested along. A
    component the syntax has no lines for is left out and listed as unrendered."""

    def __init__(self, mapper: Any, diff: Diff, context: Any):
        if diff.desired is None or diff.observed is None:
            raise DriverException("A patch is rendered from a diff that holds the trees it was made from")
        self.diff = diff
        self.desired = Rendered(mapper, diff.desired, context) if diff.added or diff.changed else None
        self.observed = Rendered(mapper, diff.observed, context) if diff.removed else None
        self.blocks: list[tuple[list[str], list[str]]] = []
        self.unrendered: list[list[str]] = []

    def render(self) -> RenderResult[str]:
        if self.observed is not None:
            removed = sorted(self.expressed(self.diff.removed, self.observed), key=lambda c: self.observed.span(c.path))
            for change in removed:
                if not self.inside_removed(change, removed):
                    self.remove(change)
        if self.desired is not None:
            trimmed = [t for c in self.diff.added + self.diff.changed if (t := self.trimmed(c)) is not None]
            for change in sorted(self.expressed(trimmed, self.desired), key=lambda c: self.desired.span(c.path)):
                self.write(change)
        return RenderResult(payload="\n".join(self.joined()), metadata=RenderMetadata(unrendered=self.unrendered))

    def expressed(self, changes: list[ComponentChange], rendered: Rendered) -> list[ComponentChange]:
        """The changes whose component has lines in the render; the others are noted as unrendered."""
        self.unrendered += [c.path for c in changes if not rendered.has(c.path)]
        return [c for c in changes if rendered.has(c.path)]

    def trimmed(self, change: ComponentChange) -> ComponentChange | None:
        """A change without the attributes holding nested components, which are changes of their own; None
        when nothing else changed."""
        if change.op != ComponentDiffOp.CHANGE:
            return change
        attributes = [a for a in change.changed_attributes if not self.desired.nests(change.path, a.attribute_name)]
        return change.model_copy(update={"changed_attributes": attributes}) if attributes else None

    def inside_removed(self, change: ComponentChange, removed: list[ComponentChange]) -> bool:
        """Whether a component around this one goes, header and all, and takes it along."""
        for other in removed:
            if len(other.path) < len(change.path) and change.path[: len(other.path)] == other.path:
                start, end = self.observed.span(other.path)
                if self.observed.headed(start, end) and not other.changed_attributes:
                    return True
        return False

    def remove(self, change: ComponentChange) -> None:
        rendered = self.observed
        start, end = rendered.span(change.path)
        context = rendered.context(start, end)
        if rendered.headed(start, end) and not change.changed_attributes:
            self.blocks.append((context, [self.negate(rendered.lines[start])]))
            return
        own = rendered.own(change.path, start, end)
        if change.changed_attributes:
            own = rendered.attribute_lines(change, own)
        if rendered.headed(start, end):
            context = [*context, rendered.lines[start]]
        self.blocks.append((context, [self.negate(rendered.lines[i]) for i in own]))

    def write(self, change: ComponentChange) -> None:
        rendered = self.desired
        start, end = rendered.span(change.path)
        context = rendered.context(start, end)
        own = rendered.own(change.path, start, end)
        if change.changed_attributes:
            own = rendered.attribute_lines(change, own)
        if rendered.headed(start, end):
            context = [*context, rendered.lines[start]]
        if own or rendered.headed(start, end):
            self.blocks.append((context, [rendered.lines[i] for i in own]))

    def negate(self, line: str) -> str:
        """`no shutdown` negates to `shutdown`, anything else gets a `no`."""
        body = line.lstrip()
        indent = line[: len(line) - len(body)]
        return indent + (body[3:] if body.startswith("no ") else f"no {body}")

    def joined(self) -> list[str]:
        """The blocks' lines, each header written again only when the block before was under another."""
        lines: list[str] = []
        current: list[str] = []
        for context, body in self.blocks:
            if context != current:
                lines += context[len(current) :] if context[: len(current)] == current else context
                current = context
            lines += body
        return lines
