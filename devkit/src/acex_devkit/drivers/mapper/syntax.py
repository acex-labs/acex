"""Declarative syntax: patterns, the line items built from them, and the blocks and sections that
bind items to components in `ComposedConfiguration`. Every declaration works in both directions, so
one declaration drives both render and parse."""

import re
import types
import typing
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from acex_devkit.drivers.mapper.tokens import TOKENS, Range, Token
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.reference import Reference


class Tree:
    """One step through the configuration tree, where a step is an attribute or a dict key."""

    @staticmethod
    def get(node: Any, segment: str) -> Any:
        return node.get(segment) if isinstance(node, dict) else getattr(node, segment, None)

    @staticmethod
    def put(node: Any, segment: str, value: Any) -> None:
        if isinstance(node, dict):
            node[segment] = value
        else:
            setattr(node, segment, value)

    @staticmethod
    def walk(node: Any, segments: tuple[str, ...]) -> Any:
        for segment in segments:
            if node is None:
                return None
            node = Tree.get(node, segment)
        return node

    @staticmethod
    def value(node: Any, field: str) -> Any:
        value = getattr(node, field, None)
        return value.get_value() if isinstance(value, AttributeValue) else value

    @staticmethod
    def schema(owner: type[BaseModel], field: str) -> Any:
        """The declared type of `owner.field`, without its `| None`."""
        annotation = owner.model_fields[field].annotation
        if typing.get_origin(annotation) in (typing.Union, types.UnionType):
            present = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
            annotation = present[0] if len(present) == 1 else annotation
        return annotation

    @staticmethod
    def create(owner: BaseModel, field: str) -> Any:
        """An empty value for a field left unset: a dict for a collection, a default model for a sub-model."""
        schema = Tree.schema(type(owner), field)
        if typing.get_origin(schema) is dict:
            return {}
        return schema() if isinstance(schema, type) and issubclass(schema, BaseModel) else None


@dataclass(frozen=True)
class Field:
    name: str
    token: Token


class Pattern:
    """One line pattern compiled into both a renderer and a full-line regex.

    `{field}` is a word, `{field:token}` picks a named token from `TOKENS`, and a token passed in
    `tokens` overrides both. `[...]` is an optional segment: rendered only when every field inside
    renders, optional on parse.
    """

    _parts = re.compile(r"(\[|\]|\{[^}]+\})")

    def __init__(self, text: str, tokens: dict[str, Token] | None = None):
        self.text = text
        self.fields: dict[str, Token] = {}
        self._overrides = tokens or {}
        self.elements = self._compile(iter(self._parts.split(text)), nested=False)
        self.regex = re.compile(self._regex(self.elements))
        unused = self._overrides.keys() - self.fields.keys()
        if unused:
            raise ValueError(f"{text!r}: tokens given for fields not in the pattern: {sorted(unused)}")

    def _compile(self, parts: Iterator[str], nested: bool) -> list:
        elements: list = []
        for part in parts:
            if part == "[":
                elements.append(self._compile(parts, nested=True))
            elif part == "]":
                if not nested:
                    raise ValueError(f"{self.text!r}: unbalanced ']'")
                return elements
            elif part.startswith("{"):
                name, _, token_name = part[1:-1].partition(":")
                if token_name and token_name not in TOKENS:
                    raise ValueError(f"{self.text!r}: unknown token {token_name!r}")
                token = self._overrides.get(name) or TOKENS[token_name or "word"]
                self.fields[name] = token
                elements.append(Field(name, token))
            elif part:
                elements.append(part)
        if nested:
            raise ValueError(f"{self.text!r}: unclosed '['")
        return elements

    def _regex(self, elements: list) -> str:
        out = ""
        for element in elements:
            if isinstance(element, str):
                out += re.escape(element)
            elif isinstance(element, list):
                out += f"(?:{self._regex(element)})?"
            else:
                out += f"(?P<{element.name}>{element.token.regex})"
        return out

    def _render(self, elements: list, values: dict[str, Any]) -> str | None:
        out = ""
        for element in elements:
            if isinstance(element, str):
                out += element
            elif isinstance(element, list):
                out += self._render(element, values) or ""
            else:
                value = values.get(element.name)
                text = None if value is None else element.token.render(value)
                if text is None:
                    return None
                out += text
        return out

    def render(self, values: dict[str, Any]) -> str | None:
        return self._render(self.elements, values)

    def match(self, text: str) -> dict[str, Any] | None:
        m = self.regex.fullmatch(text)
        if m is None:
            return None
        return {name: self.fields[name].parse(raw) for name, raw in m.groupdict().items() if raw is not None}


class Item:
    """One line-level entry in a body, setting fields on the enclosing component. `only` limits it to
    some component types, for a field whose syntax differs between types sharing it."""

    fields: tuple[str, ...] = ()

    def __init__(self, only: type | tuple[type, ...] | None = None):
        self.only = only

    def applies_to(self, component_type: type[BaseModel], params: frozenset[str] = frozenset()) -> bool:
        """Whether every field is the component's own, or one of the enclosing block's path `params`."""
        if self.only is not None and not issubclass(component_type, self.only):
            return False
        return set(self.fields) - params <= component_type.model_fields.keys()

    def render(self, values: dict[str, Any]) -> list[str]:
        raise NotImplementedError

    def match(self, text: str) -> "dict[str, Any] | Capture | None":
        """Field values one stripped line sets, or a `Capture` when the following raw lines belong to
        this item until it closes."""
        raise NotImplementedError

    def defaults(self) -> dict[str, Any]:
        """Field values the device implies when none of this item's lines are present."""
        return {}


class Line(Item):
    """A line pattern for one or more fields: `Line("switchport access vlan {access_vlan:int}")`.
    `aliases` are other spellings of the same line, read but never written (`ip domain name` beside
    `ip domain-name`). Keyword arguments other than `only` and `aliases` are per-field tokens."""

    def __init__(
        self,
        pattern: str,
        only: type | tuple[type, ...] | None = None,
        aliases: tuple[str, ...] = (),
        **tokens: Token,
    ):
        super().__init__(only)
        self.pattern = Pattern(pattern, tokens)
        self.fields = tuple(self.pattern.fields)
        self.aliases = tuple(Pattern(alias, tokens) for alias in aliases)
        for alias in self.aliases:
            if set(alias.fields) != set(self.fields):
                raise ValueError(f"{alias.text!r}: an alias must set the same fields as {pattern!r}")

    def render(self, values: dict[str, Any]) -> list[str]:
        line = self.pattern.render(values)
        return [] if line is None else [line]

    def match(self, text: str) -> dict[str, Any] | None:
        return next((m for p in (self.pattern, *self.aliases) if (m := p.match(text)) is not None), None)


class Flag(Item):
    """A boolean field written as the presence of a line: `on` when true, `off` when false (either may
    be omitted). `default` is what the device means when neither line is present."""

    def __init__(
        self,
        name: str,
        on: str | None = None,
        off: str | None = None,
        default: bool | None = None,
        only: type | tuple[type, ...] | None = None,
    ):
        super().__init__(only)
        self.name = name
        self.fields = (name,)
        self.lines = {value: line for value, line in ((True, on), (False, off)) if line is not None}
        self.default = default

    def render(self, values: dict[str, Any]) -> list[str]:
        line = self.lines.get(values.get(self.name))
        return [] if line is None else [line]

    def match(self, text: str) -> dict[str, Any] | None:
        return next(({self.name: value} for value, line in self.lines.items() if text == line), None)

    def defaults(self) -> dict[str, Any]:
        return {} if self.default is None else {self.name: self.default}


class Delimiter(Token):
    regex = r"\^C|\S"


class Multiline(Item):
    """A text field spanning lines between a start line and a delimiter, e.g. `banner motd ^C ... ^C`.
    `start` holds one `{delim}`: parse reads whatever delimiter the config uses, render writes `delimiter`."""

    def __init__(self, name: str, start: str, delimiter: str = "^C", only: type | tuple[type, ...] | None = None):
        super().__init__(only)
        self.name = name
        self.fields = (name,)
        self.delimiter = delimiter
        self.start = Pattern(start, {"delim": Delimiter()})
        if set(self.start.fields) != {"delim"}:
            raise ValueError(f"{start!r}: a multiline start must hold exactly one {{delim}} and no other fields")

    def render(self, values: dict[str, Any]) -> list[str]:
        value = values.get(self.name)
        if value is None:
            return []
        return [self.start.render({"delim": self.delimiter}), *value.split("\n"), self.delimiter]

    def match(self, text: str) -> "Capture | None":
        match = self.start.match(text)
        return None if match is None else Capture(self.name, match["delim"])


@dataclass
class Capture:
    """An open multiline field collecting raw lines until its delimiter."""

    name: str
    delimiter: str
    lines: list[str] = field(default_factory=list)

    def feed(self, raw: str) -> dict[str, Any] | None:
        """Take one raw line; the field's value once the delimiter closed it."""
        text = raw.rstrip()
        if not text.endswith(self.delimiter):
            self.lines.append(raw)
            return None
        if text[: -len(self.delimiter)]:
            self.lines.append(text[: -len(self.delimiter)])
        return {self.name: "\n".join(self.lines)}


class Mount(Item):
    """A line saying the enclosing component is a member of a collection elsewhere in the tree. The
    membership is stored there as a `Reference` back to the component, keyed by the component's own
    key — the shape a backend `ReferenceFrom` produces.

    `at` is a dotted path from the root to that collection; its `{field}` segments are dict keys taken
    from the line. `default` is the membership when no line is present (an interface without
    `vrf forwarding` belongs to `global`), and renders nothing.
    """

    def __init__(
        self,
        pattern: str,
        at: str,
        default: dict[str, str] | None = None,
        only: type | tuple[type, ...] | None = None,
        **tokens: Token,
    ):
        super().__init__(only)
        self.pattern = Pattern(pattern, tokens)
        self.at = tuple(at.split("."))
        self.default = default
        params = {segment[1:-1] for segment in self.at if segment.startswith("{")}
        if params != set(self.pattern.fields):
            raise ValueError(
                f"{pattern!r}: fields {sorted(self.pattern.fields)} must be the `at` keys {sorted(params)}"
            )

    def render(self, values: dict[str, Any]) -> list[str]:
        return []  # memberships live outside the component; the renderer asks `bindings` instead

    def match(self, text: str) -> dict[str, Any] | None:
        return self.pattern.match(text)

    def prefix(self, name: str) -> str:
        """The dotted path to the collection whose keys `{name}` takes."""
        return ".".join(self.at[: self.at.index(f"{{{name}}}")])

    def collection(self, root: BaseModel, binding: dict[str, str]) -> Any:
        return Tree.walk(root, tuple(segment.format(**binding) for segment in self.at))

    def bindings(self, root: BaseModel, key: str, pointer: str) -> list[dict[str, str]]:
        """Every binding of `at` whose collection holds a reference to `pointer` under `key`."""
        return list(self._bindings(root, self.at, {}, key, pointer))

    def _bindings(self, node: Any, segments: tuple[str, ...], binding: dict, key: str, pointer: str) -> Iterator[dict]:
        if node is None:
            return
        if not segments:
            reference = node.get(key) if isinstance(node, dict) else None
            if isinstance(reference, Reference) and reference.pointer == pointer:
                yield binding
            return
        head, rest = segments[0], segments[1:]
        if head.startswith("{"):
            for name, child in (node or {}).items():
                yield from self._bindings(child, rest, {**binding, head[1:-1]: name}, key, pointer)
        else:
            yield from self._bindings(Tree.get(node, head), rest, binding, key, pointer)


class Section:
    """A syntax-only sub-block: its header opens lines that still belong to the enclosing component,
    e.g. `address-family ipv4` under `vrf definition`. `footer` is a closing line written at the
    header's depth (Cisco `exit-address-family`). `always` renders the section even when empty."""

    def __init__(self, header: str, body: tuple = (), footer: str | None = None, always: bool = False):
        self.header = Pattern(header)
        self.body = body
        self.footer = footer
        self.always = always

    def applies_to(self, component_type: type[BaseModel]) -> bool:
        fields = set(self.header.fields) <= component_type.model_fields.keys()
        return fields and (self.always or any(entry.applies_to(component_type) for entry in self.body))

    def entries(self, component_type: type[BaseModel]) -> tuple:
        return tuple(entry for entry in self.body if entry.applies_to(component_type))


class Dispatch:
    """Picks the component type from a header field, first matching regex wins:
    `Dispatch("name", {r"^Vlan\\d+$": L3IpvlanInterface, r"": EthernetCsmacdInterface})`."""

    def __init__(self, name: str, types: dict[str, type[BaseModel]]):
        self.name = name
        self.rules = [(re.compile(regex), component_type) for regex, component_type in types.items()]
        self.types = tuple(dict.fromkeys(types.values()))

    def resolve(self, fields: dict[str, Any]) -> type[BaseModel] | None:
        value = str(fields[self.name])
        return next((t for regex, t in self.rules if regex.search(value)), None)


class Block:
    """Syntax for one component type, or a family of them via `Dispatch`, at `path` below the
    enclosing component (the root for a top-level block). `path` is dotted, and a segment may be a dict
    key (`network_instances.global.vlans`). A block takes one of three shapes:

    - With a `header`, `path` is a keyed collection. The header line opens one component and its body
      follows one indent level deeper. `key` names the header field used as the dict key (default: the
      first); it may be a key-only field the model doesn't carry. When the key's token reads a `Range`
      (`line vty 0 4`), the header opens every component in it, and consecutive components that render
      alike are written as one range.
    - With a `key` but no header, `path` is a keyed collection whose lines each carry the key and sit at
      the enclosing level (`standby 1 ip …`); lines with the same key build one component. Such a path
      may hold `{param}` segments: dict levels bound per line from the line's field of that name, matched
      against the entry's field of the same name, or the one named after a colon (`{vrf:name}`).
      `implied` holds what a line leaving a parameter out stands for, and that value is never written.
    - With neither, `path` is a single object whose lines sit at the enclosing level: a top-level
      singleton, or a sub-model like an interface's storm-control settings.

    A body holds `Item`s, nested `Block`s and `Section`s; declaration order is render order. `when`
    limits a nested block to enclosing components with those values. Subclasses may override
    `complete` to fill fields the text doesn't carry, `derive` to fill values the model doesn't carry,
    and `includes` to leave components unrendered.
    """

    path: str
    component: type[BaseModel] | Dispatch
    header: Line | None = None
    key: str | None = None
    implied: dict[str, Any] = {}
    when: dict[str, Any] = {}
    body: tuple = ()

    def __init__(self):
        name = type(self).__name__
        self.segments = tuple(self.path.split("."))
        self.params = {i: self._param(segment) for i, segment in enumerate(self.segments) if segment.startswith("{")}
        self.param_names = frozenset(param for param, _ in self.params.values())
        self.dispatch = self.component if isinstance(self.component, Dispatch) else None
        self.types = self.dispatch.types if self.dispatch else (self.component,)
        self.flat = self.header is None and self.key is not None
        self.keyed = self.header is not None or self.flat
        if self.header is not None:
            self.key = self.key or self.header.fields[0]
        self.ranged = self.header is not None and isinstance(self.header.pattern.fields.get(self.key), Range)
        self.entries = {t: tuple(entry for entry in self.body if self._fits(entry, t)) for t in self.types}
        self.defaults = {t: self._defaults(self.entries[t], t) for t in self.types}

        if self.params and not self.flat:
            raise ValueError(f"{name}: only a block whose lines carry their key binds path parameters")
        if self.header is None:
            if self.dispatch is not None:
                raise ValueError(f"{name}: a block without a header has a single component type")
            if any(not isinstance(entry, Item) or isinstance(entry, Mount) for entry in self.body):
                raise ValueError(f"{name}: a block without a header holds only Line, Flag and Multiline")
        else:
            if self.dispatch and self.dispatch.name not in self.header.fields:
                raise ValueError(f"{name}: dispatch field {self.dispatch.name!r} must be a header field")
            for t in self.types:
                missing = set(self.header.fields) - {self.key} - t.model_fields.keys()
                if missing:
                    raise ValueError(f"{name}: header fields {sorted(missing)} are not on {t.__name__}")
        if self.flat and self.key not in self.types[0].model_fields:
            raise ValueError(f"{name}: key {self.key!r} is not on {self.types[0].__name__}")
        for entry in self.body:
            if not any(self._fits(entry, t) for t in self.types):
                raise ValueError(f"{name}: {type(entry).__name__} {self._describe(entry)} fits none of {self.types}")

    def _param(self, segment: str) -> tuple[str, str]:
        param, _, field = segment[1:-1].partition(":")
        return param, field or param

    def _fits(self, entry: Any, component_type: type[BaseModel]) -> bool:
        return (
            entry.applies_to(component_type, self.param_names)
            if isinstance(entry, Item)
            else entry.applies_to(component_type)
        )

    def _defaults(self, entries: tuple, component_type: type[BaseModel]) -> dict[str, Any]:
        defaults: dict[str, Any] = {}
        for entry in entries:
            if isinstance(entry, Section):
                defaults |= self._defaults(entry.entries(component_type), component_type)
            elif isinstance(entry, Item):
                defaults |= entry.defaults()
        return defaults

    def _describe(self, entry: Any) -> str:
        if isinstance(entry, Block):
            return entry.path
        if isinstance(entry, Section):
            return entry.header.text
        return str(entry.fields)

    def applies_to(self, component_type: type[BaseModel]) -> bool:
        return self.segments[0] in component_type.model_fields

    def active(self, values: dict[str, Any]) -> bool:
        return all(values.get(name) == value for name, value in self.when.items())

    def complete(self, fields: dict[str, Any], position: int, context: Any) -> dict[str, Any]:
        """Fill fields the text doesn't carry before the component is created. `position` is how many
        components the collection already holds; `context` is what was passed to `Mapper.parse`."""
        return fields

    def derive(self, values: dict[str, Any], context: Any) -> dict[str, Any] | None:
        """Fill values the model doesn't carry before the component is rendered, e.g. a name computed
        from hardware. `context` is what was passed to `Mapper.render`; None leaves the component out."""
        return values

    def includes(self, key: str | None, component: BaseModel) -> bool:
        """Whether a component in the tree is rendered."""
        return True

    def type_for(self, fields: dict[str, Any]) -> type[BaseModel] | None:
        return self.dispatch.resolve(fields) if self.dispatch else self.types[0]

    def locate(self, parent: Any, create: bool = False) -> Any:
        """The collection (keyed) or object (not) this block covers below `parent`, for a path without
        parameters. `create` makes the last step if it's missing."""
        node = Tree.walk(parent, self.segments[:-1])
        if node is None:
            return None
        target = Tree.get(node, self.segments[-1])
        if target is None and create:
            target = {} if self.keyed else self.types[0](**self.defaults[self.types[0]])
            Tree.put(node, self.segments[-1], target)
        return target

    def placements(self, parent: Any) -> Iterator[tuple[dict[str, Any], tuple[str, ...], dict]]:
        """Every collection the path reaches below `parent`: the parameters bound on the way, the
        segments walked, and the collection."""
        yield from self._placements(parent, 0, {}, ())

    def _placements(self, node: Any, i: int, binding: dict, walked: tuple) -> Iterator[tuple[dict, tuple, dict]]:
        if node is None:
            return
        if i == len(self.segments):
            if isinstance(node, dict):
                yield binding, walked, node
            return
        if i not in self.params:
            yield from self._placements(Tree.get(node, self.segments[i]), i + 1, binding, walked + (self.segments[i],))
            return
        param, field = self.params[i]
        for key, entry in node.items():
            value = Tree.value(entry, field)
            yield from self._placements(
                entry, i + 1, {**binding, param: key if value is None else value}, walked + (key,)
            )

    def place(self, parent: Any, binding: dict[str, Any]) -> tuple[dict, tuple[str, ...]] | None:
        """The collection a line with path parameters `binding` belongs in and the segments leading to it.
        Missing levels are created where the schema allows; None when one can't be, e.g. an entry that
        needs more fields than the bound one."""
        node, walked, schema = parent, (), None
        for i, segment in enumerate(self.segments):
            if i in self.params:
                param, field = self.params[i]
                value = binding[param]
                key = next((k for k, entry in node.items() if Tree.value(entry, field) == value), str(value))
                if key not in node:
                    try:
                        node[key] = typing.get_args(schema)[1](**{field: value})
                    except ValidationError:
                        return None
                node, walked = node[key], walked + (key,)
                continue
            child = Tree.get(node, segment)
            if child is None:
                child = Tree.create(node, segment)
                if child is None:
                    return None
                Tree.put(node, segment, child)
            schema = Tree.schema(type(node), segment) if isinstance(node, BaseModel) else None
            node, walked = child, walked + (segment,)
        return node, walked

    def components(self, parent: Any, values: dict[str, Any]) -> list[tuple[str | None, BaseModel]]:
        if not self.active(values):
            return []
        target = self.locate(parent)
        if target is None:
            return []
        if not self.keyed:
            return [(None, target)] if self.includes(None, target) else []
        return [(k, c) for k, c in target.items() if type(c) in self.types and self.includes(k, c)]

    def create(self, component_type: type[BaseModel], fields: dict[str, Any], position: int, context: Any) -> BaseModel:
        fields = self.complete({**self.defaults[component_type], **fields}, position, context)
        return component_type(**{k: v for k, v in fields.items() if k in component_type.model_fields})

    def values(self, component: BaseModel, key: str | None) -> dict[str, Any]:
        """The component's field values, unwrapped, plus its key under the key field's name."""
        values = {k: v.get_value() if isinstance(v, AttributeValue) else v for k, v in component}
        if key is not None:
            values.setdefault(self.key, key)
        return values
