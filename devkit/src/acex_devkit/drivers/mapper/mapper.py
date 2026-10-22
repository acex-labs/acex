"""The engine: drives render and parse from the top-level `Block`s."""

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from acex_devkit.drivers.mapper.syntax import Block, Capture, Mount, Section
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.reference import Reference


@dataclass
class ParseResult:
    configuration: ComposedConfiguration
    unmatched: list[str] = field(default_factory=list)
    """Lines no declaration claimed: not yet modelled, or not matching any pattern."""


class Mapper:
    """Renders and parses indentation-nested CLI text. `indent` is one nesting level (Cisco a single
    space; empty for flat text, where every line reads as top level). `separator` is a line written
    between top-level components and skipped on parse (Cisco `!`)."""

    def __init__(self, blocks: list[Block], indent: str = "", separator: str | None = None):
        self.blocks = tuple(blocks)
        self.indent = indent
        self.separator = separator
        root = ComposedConfiguration()
        for block in self.blocks:
            if isinstance(block.locate(root, {}), dict) != (block.header is not None):
                kind = (
                    "a keyed collection, which needs" if block.header is None else "a single object, which can't have"
                )
                raise ValueError(f"{type(block).__name__}: {block.path} is {kind} a header")

    def supported_components(self) -> list[str]:
        """Dotted `ComposedConfiguration` paths of the top-level components this mapper covers."""
        return sorted({block.path for block in self.blocks})

    def depth(self, line: str) -> int:
        return len(line) - len(line.lstrip(self.indent)) if self.indent else 0

    def render(self, root: ComposedConfiguration) -> str:
        return Renderer(self, root).render()

    def parse(self, text: str) -> ParseResult:
        return ParseRun(self).run(text)


class Renderer:
    """One render of a configuration tree into text."""

    def __init__(self, mapper: Mapper, root: ComposedConfiguration):
        self.mapper = mapper
        self.root = root

    def render(self) -> str:
        chunks = [
            self.component(block, key, component, (), {}, 0)
            for block in self.mapper.blocks
            for key, component in block.components(self.root, {})
        ]
        lines: list[str] = []
        for chunk in filter(None, chunks):
            if lines and self.mapper.separator is not None:
                lines.append(self.mapper.separator)
            lines.extend(chunk)
        return "\n".join(lines)

    def component(
        self, block: Block, key: str | None, component: BaseModel, path: tuple, parent: dict[str, Any], depth: int
    ) -> list[str]:
        values = block.values(component, key)
        path = path + block.resolve(parent) + (() if key is None else (key,))
        if block.header is None:
            return self.body(block.entries[type(component)], component, values, path, key, depth)
        header = block.header.pattern.render(values)
        if header is None:
            return []
        body = self.body(block.entries[type(component)], component, values, path, key, depth + 1)
        return [self.mapper.indent * depth + header, *body]

    def body(
        self, entries: tuple, component: BaseModel, values: dict[str, Any], path: tuple, key: str | None, depth: int
    ) -> list[str]:
        indent = self.mapper.indent * depth
        lines: list[str] = []
        for entry in entries:
            if isinstance(entry, Block):
                for child_key, child in entry.components(component, values):
                    lines += self.component(entry, child_key, child, path, values, depth)
            elif isinstance(entry, Section):
                section = self.body(entry.entries(type(component)), component, values, path, key, depth + 1)
                header = entry.header.render(values)
                if header is not None and (section or entry.always):
                    lines += [indent + header, *section] + ([indent + entry.footer] if entry.footer else [])
            elif isinstance(entry, Mount):
                bindings = entry.bindings(self.root, key, ".".join(path))
                lines += [indent + entry.pattern.render(b) for b in bindings if b != entry.default]
            else:
                lines += [indent + line for line in entry.render(values)]
        return lines


@dataclass
class Frame:
    """An open level of the text: the entries that may match inside it and the live component its
    lines write to. Sections push a frame on the same component."""

    entries: tuple
    target: Any
    block: Block | None
    key: str | None
    path: tuple[str, ...]
    depth: int

    def values(self) -> dict[str, Any]:
        return self.block.values(self.target, self.key) if self.block else {}


class ParseRun:
    """One pass over a config text, building a live `ComposedConfiguration`: a component is created
    and mounted as soon as its header is read, and each body line sets fields on it. Memberships
    (`Mount`) are applied after the last line, when every collection they point into exists."""

    def __init__(self, mapper: Mapper):
        self.mapper = mapper
        self.root = ComposedConfiguration()
        self.stack = [Frame(mapper.blocks, self.root, None, None, (), -1)]
        self.capture: tuple[Capture, Any] | None = None
        self.mounts: dict[tuple[tuple[str, ...], int], tuple[Mount, dict, str, str | None]] = {}
        self.unmatched: list[str] = []
        self.raw = ""

    def run(self, text: str) -> ParseResult:
        for block in self.stack[0].entries:
            if block.header is None:
                self.assign(block.locate(self.root, {}, create=True), block.defaults[block.types[0]])
        for raw in text.splitlines():
            self.feed(raw)
        self.apply_mounts()
        return ParseResult(self.root, self.unmatched)

    def feed(self, raw: str) -> None:
        self.raw = raw
        if self.capture is not None:
            capture, target = self.capture
            values = capture.feed(raw)
            if values is not None:
                self.assign(target, values)
                self.capture = None
            return
        text = raw.strip()
        if not text:
            return
        depth = self.mapper.depth(raw)
        while len(self.stack) > 1 and depth <= self.stack[-1].depth:
            self.stack.pop()
        if text == self.mapper.separator:
            return
        frame = self.stack[-1]
        # A line deeper than the frame's body belongs to something the frame doesn't model.
        if depth != frame.depth + 1 or not any(self.match(entry, frame, text, depth) for entry in frame.entries):
            self.unmatched.append(raw)

    def match(self, entry: Any, frame: Frame, text: str, depth: int) -> bool:
        if isinstance(entry, Block):
            if not entry.active(frame.values()):
                return False
            return self.open(entry, frame, text, depth) if entry.header else self.inline(entry, frame, text)
        if isinstance(entry, Section):
            return self.section(entry, frame, text, depth)
        result = entry.match(text)
        if result is None:
            return False
        if isinstance(entry, Mount):
            self.mounts[(frame.path, id(entry))] = (entry, result, frame.key, self.raw)
        elif isinstance(result, Capture):
            self.capture = (result, frame.target)
        else:
            self.assign(frame.target, result)
        return True

    def open(self, block: Block, frame: Frame, text: str, depth: int) -> bool:
        fields = block.header.match(text)
        component_type = None if fields is None else block.type_for(fields)
        if component_type is None:
            return False
        values = frame.values()
        collection = block.locate(frame.target, values, create=True)
        if collection is None:
            return False
        key = str(fields[block.key])
        if key not in collection:
            collection[key] = block.create(component_type, fields, len(collection))
        component = collection[key]
        path = frame.path + block.resolve(values) + (key,)
        entries = block.entries[type(component)]
        self.stack.append(Frame(entries, component, block, key, path, depth))
        for entry in entries:
            if isinstance(entry, Mount) and entry.default is not None:
                self.mounts.setdefault((path, id(entry)), (entry, entry.default, key, None))
        return True

    def inline(self, block: Block, frame: Frame, text: str) -> bool:
        for entry in block.entries[block.types[0]]:
            result = entry.match(text)
            if result is None:
                continue
            target = block.locate(frame.target, frame.values(), create=True)
            if isinstance(result, Capture):
                self.capture = (result, target)
            else:
                self.assign(target, result)
            return True
        return False

    def section(self, section: Section, frame: Frame, text: str, depth: int) -> bool:
        if section.footer is not None and text == section.footer:
            return True
        values = section.header.match(text)
        if values is None:
            return False
        self.assign(frame.target, values)
        entries = section.entries(type(frame.target))
        self.stack.append(Frame(entries, frame.target, frame.block, frame.key, frame.path, depth))
        return True

    def assign(self, target: BaseModel, values: dict[str, Any]) -> None:
        for name, value in values.items():
            setattr(target, name, value if isinstance(value, BaseModel) else AttributeValue(value=value))

    def apply_mounts(self) -> None:
        for (path, _), (mount, binding, key, raw) in self.mounts.items():
            collection = mount.collection(self.root, binding)
            if isinstance(collection, dict):
                collection[key] = Reference(pointer=".".join(path))
            elif raw is not None:
                self.unmatched.append(raw)
