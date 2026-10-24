"""The engine: drives render and parse from the top-level `Block`s."""

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from acex_devkit.drivers.mapper.syntax import Block, Capture, Item, Mount, Section, Tree
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.codec_result import (
    ParseMetadata,
    ParseResult,
    RenderMetadata,
    RenderResult,
    Span,
    UnmatchedLine,
)
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.reference import Reference


@dataclass
class Text:
    """Rendered lines and the spans of components within them, 0-based and relative to `lines`."""

    lines: list[str] = field(default_factory=list)
    spans: list[tuple[int, int, tuple[str, ...]]] = field(default_factory=list)

    def add(self, *lines: str) -> "Text":
        self.lines.extend(lines)
        return self

    def extend(self, other: "Text") -> "Text":
        offset = len(self.lines)
        self.spans += [(start + offset, end + offset, path) for start, end, path in other.spans]
        self.lines += other.lines
        return self

    def span(self, path: tuple[str, ...]) -> "Text":
        """Mark everything so far as one component's lines."""
        if self.lines:
            self.spans.insert(0, (0, len(self.lines) - 1, path))
        return self

    def add_spanned(self, lines: list[str], path: tuple[str, ...]) -> "Text":
        """Add lines that express one field, spanned by the field's path."""
        if lines:
            self.spans.append((len(self.lines), len(self.lines) + len(lines) - 1, path))
            self.lines.extend(lines)
        return self

    def result(self) -> RenderResult[str]:
        spans = [Span(start=start + 1, end=end + 1, path=list(path)) for start, end, path in self.spans]
        return RenderResult(payload="\n".join(self.lines), metadata=RenderMetadata(spans=spans))


class Mapper:
    """Renders and parses indentation-nested CLI text. `indent` is one nesting level (Cisco a single
    space; empty for flat text, where every line reads as top level). `separator` is a line written
    between top-level components and skipped on parse (Cisco `!`)."""

    def __init__(self, blocks: list[Block], indent: str = "", separator: str | None = None):
        self.blocks = tuple(blocks)
        self.indent = indent
        self.separator = separator
        self.headed = tuple(block for block in self.blocks if block.header is not None)
        root = ComposedConfiguration()
        for block in self.blocks:
            if not block.params and isinstance(block.locate(root), dict) != block.keyed:
                kind = "a keyed collection, which needs" if not block.keyed else "a single object, which can't have"
                raise ValueError(f"{type(block).__name__}: {block.path} is {kind} a header or key")

    def supported_components(self) -> list[str]:
        """Dotted `ComposedConfiguration` paths of the top-level components this mapper covers."""
        return sorted({block.path for block in self.blocks})

    def depth(self, line: str) -> int:
        return len(line) - len(line.lstrip(self.indent)) if self.indent else 0

    def render(self, root: ComposedConfiguration, context: Any = None) -> RenderResult[str]:
        """`context` reaches every block's `derive` hook, e.g. the node whose hardware names the interfaces."""
        return Renderer(self, root, context).render()

    def parse(self, text: str, context: Any = None) -> ParseResult:
        """`context` reaches every block's `complete` hook."""
        return ParseRun(self, context).run(text)


class Renderer:
    """One render of a configuration tree into text."""

    def __init__(self, mapper: Mapper, root: ComposedConfiguration, context: Any):
        self.mapper = mapper
        self.root = root
        self.context = context

    def render(self) -> RenderResult[str]:
        text = Text()
        for block in self.mapper.blocks:
            for chunk in self.chunks(block, self.root, {}, (), 0):
                if chunk.lines and text.lines and self.mapper.separator is not None:
                    text.add(self.mapper.separator)
                text.extend(chunk)
        return text.result()

    def chunks(self, block: Block, parent: Any, values: dict[str, Any], path: tuple, depth: int) -> list[Text]:
        """The block's text below `parent`: one chunk per component with a header of its own, one chunk
        for a block whose components share lines or ranges."""
        if not block.active(values):
            return []
        if block.flat:
            return [self.lines(block, parent, path, depth)]
        if block.shared:
            return self.shared(block, parent, path, depth)
        components = block.components(parent, values)
        if block.ranged:
            return [self.ranges(block, components, path, depth)]
        return [self.component(block, key, component, path, depth) for key, component in components]

    def component(
        self,
        block: Block,
        key: str | None,
        component: BaseModel,
        path: tuple,
        depth: int,
        keys: list | None = None,
        walked: tuple | None = None,
    ) -> Text:
        """One component's text; `keys` writes a run of components that render alike under one header, and
        `walked` is the path to a component reached through path parameters."""
        values = block.derive(self.canonical(block.values(component, key)), self.context)
        if values is None:
            return Text()
        if keys is not None:
            values[block.key] = keys
        path = path + (block.segments if walked is None else walked) + (() if key is None else (key,))
        if block.header is None:
            return self.body(block.entries[type(component)], component, values, path, key, depth).span(path)
        header = block.header.pattern.render(values)
        if header is None:
            return Text()
        body = self.body(block.entries[type(component)], component, values, path, key, depth + 1)
        return Text().add(self.mapper.indent * depth + header).extend(body).span(path)

    def body(
        self, entries: tuple, component: BaseModel, values: dict[str, Any], path: tuple, key: str | None, depth: int
    ) -> Text:
        indent = self.mapper.indent * depth
        text = Text()
        for entry in entries:
            if isinstance(entry, Item) and not entry.admits(self.context, rendering=True):
                continue
            if isinstance(entry, Block):
                for chunk in self.chunks(entry, component, values, path, depth):
                    text.extend(chunk)
            elif isinstance(entry, Section):
                section = self.body(entry.entries(type(component)), component, values, path, key, depth + 1)
                header = entry.header.render(values)
                if header is not None and (section.lines or entry.always):
                    text.add(indent + header).extend(section)
                    if entry.footer:
                        text.add(indent + entry.footer)
            elif isinstance(entry, Mount):
                bindings = entry.bindings(self.root, key, ".".join(path))
                text.add(*(indent + entry.pattern.render(self.named(entry, b)) for b in bindings if b != entry.default))
            else:
                # A field's own span lets a line resolve to a component placed at the field, e.g. a hostname.
                text.add_spanned([indent + line for line in entry.render(values)], path + entry.fields[:1])
        return text

    def lines(self, block: Block, parent: Any, path: tuple, depth: int) -> Text:
        """A block whose lines carry their key: each component's lines at the enclosing level, with the
        path parameters bound on the way to it."""
        text = Text()
        for binding, walked, collection in block.placements(parent):
            shown = {param: None if value == block.implied.get(param) else value for param, value in binding.items()}
            for key, component in collection.items():
                if type(component) not in block.types or not block.includes(key, component):
                    continue
                # The path parameters win over a same-named field the component leaves unset.
                values = block.derive(self.canonical({**block.values(component, key), **shown}), self.context)
                if values is not None:
                    own = path + walked + (key,)
                    text.extend(self.body(block.entries[type(component)], component, values, own, key, depth).span(own))
        return text

    def shared(self, block: Block, parent: Any, path: tuple, depth: int) -> list[Text]:
        """Entries held in several places under one key, written once each, from where they're first found."""
        chunks, seen = [], set()
        for _, walked, collection in block.placements(parent):
            for key, component in collection.items():
                if key not in seen and type(component) in block.types and block.includes(key, component):
                    seen.add(key)
                    chunks.append(self.component(block, key, component, path, depth, walked=walked))
        return chunks

    def ranges(self, block: Block, components: list[tuple[str, BaseModel]], path: tuple, depth: int) -> Text:
        """Components keyed by a number, consecutive ones whose bodies render alike written as one range."""
        numbered = [(Tree.value(component, block.key), key, component) for key, component in components]
        runs: list[list[tuple[int, list[str], str, BaseModel]]] = []
        for number, key, component in sorted((t for t in numbered if t[0] is not None), key=lambda t: t[0]):
            values = block.derive(self.canonical(block.values(component, key)), self.context)
            if values is None:
                continue
            body = self.body(block.entries[type(component)], component, values, path, key, depth + 1).lines
            if runs and runs[-1][-1][0] == number - 1 and runs[-1][-1][1] == body:
                runs[-1].append((number, body, key, component))
            else:
                runs.append([(number, body, key, component)])
        text = Text()
        for run in runs:
            _, _, key, component = run[0]
            text.extend(self.component(block, key, component, path, depth, keys=[number for number, *_ in run]))
        return text

    def pointer(self, pointer: str) -> str:
        """`pointer` with its target addressed by the name it renders under rather than its dict key.
        A desired tree keys components by config-component name; the text uses the device's name."""
        for block in self.mapper.headed:
            prefix = f"{block.path}."
            if not pointer.startswith(prefix):
                continue
            key = pointer.removeprefix(prefix)
            target = Tree.get(block.locate(self.root), key)
            if type(target) not in block.types:
                continue
            values = block.derive(block.values(target, key), self.context)
            if values and values.get(block.key) is not None:
                return prefix + str(values[block.key])
        return pointer

    def canonical(self, values: dict[str, Any]) -> dict[str, Any]:
        return {
            k: Reference(pointer=self.pointer(v.pointer)) if isinstance(v, Reference) else v for k, v in values.items()
        }

    def named(self, mount: Mount, binding: dict[str, str]) -> dict[str, str]:
        """A membership's keys as the names their components render under."""
        return {
            name: self.pointer(f"{mount.prefix(name)}.{key}").removeprefix(f"{mount.prefix(name)}.")
            for name, key in binding.items()
        }


@dataclass
class Frame:
    """An open level of the text: the entries that may match inside it and the live component its
    lines write to. Sections push a frame on the same component and don't span lines of their own."""

    entries: tuple
    target: Any
    block: Block | None
    key: str | None
    path: tuple[str, ...]
    depth: int
    header: str = ""
    start: int = 0
    last: int = 0
    spans: bool = True

    def values(self) -> dict[str, Any]:
        target = self.target[0] if isinstance(self.target, list) else self.target
        return self.block.values(target, self.key) if self.block else {}


class ParseRun:
    """One pass over a config text, building a live `ComposedConfiguration`: a component is created
    and mounted as soon as its header is read, and each body line sets fields on it. Memberships
    (`Mount`) are applied after the last line, when every collection they point into exists."""

    def __init__(self, mapper: Mapper, context: Any):
        self.mapper = mapper
        self.context = context
        self.root = ComposedConfiguration()
        self.stack = [Frame(mapper.blocks, self.root, None, None, (), -1)]
        # An open multiline field: the capture, the component it writes to, and the span path its lines
        # count toward when no open frame already spans them.
        self.capture: tuple[Capture, Any, tuple[str, ...] | None] | None = None
        self.mounts: dict[tuple[tuple[str, ...], int], tuple[Mount, dict, str, UnmatchedLine | None]] = {}
        self.unmatched: list[UnmatchedLine] = []
        self.orphans: list[tuple[int, str]] = []  # unmatched lines whose deeper lines read as their body
        self.spans: list[tuple[int, int, tuple[str, ...]]] = []
        self.raw = ""
        self.number = 0
        self.depth = 0

    def run(self, text: str) -> ParseResult:
        for block in self.stack[0].entries:
            if not block.keyed and block.header is None:
                self.assign(block.locate(self.root, create=True), block.defaults[block.types[0]])
        for number, raw in enumerate(text.splitlines(), start=1):
            self.feed(number, raw)
        while len(self.stack) > 1:
            self.pop()
        self.apply_mounts()
        spans = [Span(start=start, end=end, path=list(path)) for start, end, path in sorted(self.spans)]
        return ParseResult(configuration=self.root, metadata=ParseMetadata(spans=spans, unmatched=self.unmatched))

    def feed(self, number: int, raw: str) -> None:
        self.raw, self.number = raw, number
        if self.capture is not None:
            capture, target, path = self.capture
            for open_frame in self.stack[1:]:
                open_frame.last = number
            if path is not None:
                self.mark(path)
            values = capture.feed(raw)
            if values is not None:
                self.assign(target, values)
                self.capture = None
            return
        text = raw.strip()
        if not text:
            return
        self.depth = depth = self.mapper.depth(raw)
        while len(self.stack) > 1 and depth <= self.stack[-1].depth:
            self.pop()
        self.orphans = [(d, line) for d, line in self.orphans if d < depth]
        if text == self.mapper.separator:
            return
        for open_frame in self.stack[1:]:
            open_frame.last = number
        frame = self.stack[-1]
        # A line deeper than the frame's body belongs to something the frame doesn't model.
        if depth != frame.depth + 1 or not any(self.match(entry, frame, text, depth) for entry in frame.entries):
            self.unmatched.append(self.unmatched_line())
            self.orphans.append((depth, raw))

    def unmatched_line(self) -> UnmatchedLine:
        """The current line, with the headers of the blocks it sits in, modelled or not."""
        headers = [(f.depth, f.header) for f in self.stack[1:]] + self.orphans
        return UnmatchedLine(line=self.raw, parents=[header for _, header in sorted(headers, key=lambda h: h[0])])

    def mark(self, path: tuple[str, ...]) -> None:
        """Count the current line toward `path`, joining the span of the line before when it's the same."""
        if self.spans and self.spans[-1][2] == path and self.spans[-1][1] == self.number - 1:
            self.spans[-1] = (self.spans[-1][0], self.number, path)
        else:
            self.spans.append((self.number, self.number, path))

    def pop(self) -> None:
        frame = self.stack.pop()
        if frame.spans:
            self.spans.append((frame.start, frame.last, frame.path))

    def match(self, entry: Any, frame: Frame, text: str, depth: int) -> bool:
        if isinstance(entry, Block):
            if not entry.active(frame.values()):
                return False
            if entry.header is not None:
                return self.open(entry, frame, text, depth)
            return self.lines(entry, frame, text) if entry.flat else self.inline(entry, frame, text)
        if isinstance(entry, Section):
            return self.section(entry, frame, text, depth)
        if not entry.admits(self.context, rendering=False):
            return False
        result = entry.match(text)
        if result is None:
            return False
        if isinstance(entry, Mount):
            self.mounts[(frame.path, id(entry))] = (entry, result, frame.key, self.unmatched_line())
        elif isinstance(result, Capture):
            self.capture = (result, frame.target, None)
        else:
            self.assign(frame.target, result)
        return True

    def open(self, block: Block, frame: Frame, text: str, depth: int) -> bool:
        fields = block.header.match(text)
        component_type = None if fields is None else block.type_for(fields)
        if component_type is None:
            return False
        if block.shared:
            return self.open_shared(block, frame, fields, depth)
        collection = block.locate(frame.target, create=True)
        if collection is None:
            return False
        if block.single:
            self.assign(collection, fields)
            path = frame.path + block.segments
            entries = block.entries[type(collection)]
            self.stack.append(Frame(entries, collection, block, None, path, depth, self.raw, self.number, self.number))
            return True
        # A ranged header opens every component in its range; its body lines then write to all of them.
        keys = [str(value) for value in (fields[block.key] if block.ranged else [fields[block.key]])]
        for key, value in zip(keys, fields[block.key] if block.ranged else [fields[block.key]], strict=True):
            if key not in collection:
                collection[key] = block.create(
                    component_type, {**fields, block.key: value}, len(collection), self.context
                )
        components, key = [collection[k] for k in keys], keys[0]
        component = components[0]
        path = frame.path + block.segments + (key,)
        entries = block.entries[type(component)]
        target = components if block.ranged else component
        self.stack.append(Frame(entries, target, block, key, path, depth, self.raw, self.number, self.number))
        for entry in entries:
            if isinstance(entry, Mount) and entry.default is not None:
                self.mounts.setdefault((path, id(entry)), (entry, entry.default, key, None))
        return True

    def open_shared(self, block: Block, frame: Frame, fields: dict[str, Any], depth: int) -> bool:
        key = str(fields[block.key])
        found = [
            (walked, collection[key]) for _, walked, collection in block.placements(frame.target) if key in collection
        ]
        if not found:
            return False
        components = [component for _, component in found]
        self.assign(components, {k: v for k, v in fields.items() if k != block.key})
        path = frame.path + found[0][0] + (key,)
        entries = block.entries[type(components[0])]
        self.stack.append(Frame(entries, components, block, key, path, depth, self.raw, self.number, self.number))
        return True

    def inline(self, block: Block, frame: Frame, text: str) -> bool:
        for entry in block.entries[block.types[0]]:
            result = entry.match(text) if entry.admits(self.context, rendering=False) else None
            if result is None:
                continue
            target = block.locate(frame.target, create=True)
            path = frame.path + block.segments
            self.mark(path)
            if isinstance(result, Capture):
                self.capture = (result, target, path)
            else:
                self.assign(target, result)
            return True
        return False

    def lines(self, block: Block, frame: Frame, text: str) -> bool:
        """A line carrying its component's key, and its path parameters, among its fields."""
        for entry in block.entries[block.types[0]]:
            result = entry.match(text) if entry.admits(self.context, rendering=False) else None
            if result is None or isinstance(result, Capture):
                continue
            binding = {param: result.pop(param, block.implied.get(param)) for param in block.param_names}
            placed = block.place(frame.target, binding)
            if placed is None:
                return False
            collection, walked = placed
            key = str(result[block.key])
            if key not in collection:
                collection[key] = block.create(
                    block.types[0], {block.key: result[block.key]}, len(collection), self.context
                )
            self.mark(frame.path + walked + (key,))
            self.assign(collection[key], {k: v for k, v in result.items() if k != block.key})
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
        self.stack.append(
            Frame(entries, frame.target, frame.block, frame.key, frame.path, depth, self.raw, spans=False)
        )
        return True

    def assign(self, target: BaseModel | list[BaseModel], values: dict[str, Any]) -> None:
        for component in target if isinstance(target, list) else [target]:
            for name, value in values.items():
                setattr(component, name, value if isinstance(value, BaseModel) else AttributeValue(value=value))

    def apply_mounts(self) -> None:
        for (path, _), (mount, binding, key, line) in self.mounts.items():
            collection = mount.collection(self.root, binding)
            if isinstance(collection, dict):
                collection[key] = Reference(pointer=".".join(path))
            elif line is not None:
                self.unmatched.append(line)
