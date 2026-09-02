"""Declarative render+parse mapping engine for text-based config dialects.

Two small declarations are enough to drive both render and parse for a whole
`ComposedConfiguration` tree, without any imperative build/attach code per type:

- `DialectAttributeMap(component_type, attribute_name, pattern)` — one regex/template line
  bound to one attribute. The single source of truth for both directions: `pattern` compiles
  into both a renderer (`str.format`-style) and a parser (a generated regex).
- `Dialect.component_order` / `Dialect.identity_maps` — the only per-type facts that are genuinely
  vendor/syntax-specific and can't be derived from the schema: what order component types
  render in (a real running-config convention), and — for keyed-collection types only — which
  attribute's value becomes the dict key in *this dialect's* text.

Everything else — where a component type lives in the tree, and whether it's a keyed
collection (`dict[str, X]`) or a singleton (a plain nested object, e.g. `SystemConfig`) — is
derived once by walking `ComposedConfiguration`'s own pydantic schema (`COMPONENT_PATHS`
below), shared by every dialect: tree shape is vendor-agnostic, so it isn't something a Cisco
or Junos dialect should have to redeclare.

A singleton component (no identity, no dict key — it already exists by default, e.g.
`System.config: SystemConfig = SystemConfig()`) is never "created": its attribute maps just
write directly onto the existing object as soon as a line matches, immediately, with no block
open/close bookkeeping. A keyed-collection component (e.g. an interface) is built once its
identity line is seen and attached once its block closes, same as before.

`Dialect.pre_parse_hooks` / `pre_render_hooks` are an escape hatch per component type for
genuinely irregular logic (e.g. Cisco interface-name-to-type dispatch) that doesn't belong in a
regex pattern.

This is a first slice, proven for two component types (Cisco IOS interfaces and system
hostname) — see /Users/johan/.claude/plans/validated-finding-petal.md. `render_patch`/
diff-based patching is not implemented yet.
"""

from __future__ import annotations

import re
import string
import types
import typing
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Literal, Union

from pydantic import BaseModel

from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.composed_configuration import ComposedConfiguration

SyntaxPath = tuple[str, ...]
"""Addresses a component within *this dialect's* rendered/parsed text, e.g.
`("GigabitEthernet0/1",)`. Distinct from the vendor-agnostic domain path used by
`ComponentChange.path` / `Configuration.COMPONENT_MAPPING`, which addresses a component inside
the `ComposedConfiguration` Python tree — the same location, viewed from the syntax side."""

LineRole = Literal["header", "body", "trailer"]

_formatter = string.Formatter()


def _field_value(component: Any, name: str) -> Any:
    """Read a plain field's value off a component, unwrapping AttributeValue."""
    value = getattr(component, name, None)
    if value is None:
        return None
    get_value = getattr(value, "get_value", None)
    return get_value() if get_value is not None else value


@dataclass(frozen=True)
class LineRecord:
    """One rendered or parsed line, tied back to the component and syntax-path it belongs to."""

    path: SyntaxPath
    component: Any | None
    component_type: type | None
    depth: int
    role: LineRole
    line: str


@dataclass
class RenderResult:
    text: str
    lines: list[LineRecord] = field(default_factory=list)


@dataclass
class ParseResult:
    configuration: Any
    lines: list[LineRecord] = field(default_factory=list)


@dataclass
class ParseFrame:
    """One entry on the parse stack — only ever pushed for keyed-collection types (singletons
    are applied directly and never get a frame). `depth` is dialect-defined bookkeeping (e.g. an
    indentation column count for Cisco) — `Mapper` treats it as opaque and only ever asks the
    `Dialect` to interpret it via `resolve_frame`."""

    path: SyntaxPath
    component_type: type | None
    kwargs: dict[str, Any]
    depth: int


# --------------------------------------------------------------------- schema introspection


@dataclass(frozen=True)
class TreeLocation:
    """Where one component type lives in `ComposedConfiguration` — derived from the pydantic
    schema itself, not declared by hand. `path` is the dotted attribute path from the root to
    the field holding it; `kind` is `"dict"` for a keyed collection (`dict[str, X]`) or
    `"singleton"` for a plain nested object that already exists by default."""

    path: tuple[str, ...]
    kind: Literal["dict", "singleton"]


def _is_component_model(annotation: Any) -> bool:
    # AttributeValue is devkit's own leaf value-wrapper (str/int/bool/... plus metadata) — every
    # scalar field in the schema is one, so it must be excluded or the walk would treat every
    # single field as a "component" and recurse into AttributeValue's own internals.
    return (
        isinstance(annotation, type)
        and issubclass(annotation, BaseModel)
        and not issubclass(annotation, AttributeValue)
    )


def _expand_types(annotation: Any) -> list[type]:
    origin = typing.get_origin(annotation)
    if origin in (Union, types.UnionType):
        expanded: list[type] = []
        for arg in typing.get_args(annotation):
            expanded.extend(_expand_types(arg))
        return expanded
    return [annotation] if _is_component_model(annotation) else []


def _classify_field(annotation: Any) -> tuple[Literal["dict", "singleton"], list[type]] | None:
    origin = typing.get_origin(annotation)
    if origin is dict:
        _key_type, value_type = typing.get_args(annotation)
        types_ = _expand_types(value_type)
        return ("dict", types_) if types_ else None
    types_ = _expand_types(annotation)
    return ("singleton", types_) if types_ else None


def _walk_component_paths(
    model: type[BaseModel], prefix: tuple[str, ...], seen: set[type], paths: dict[type, TreeLocation]
) -> None:
    if model in seen:
        return
    seen.add(model)
    for field_name, info in model.model_fields.items():
        classified = _classify_field(info.annotation)
        if classified is None:
            continue
        kind, types_ = classified
        field_path = prefix + (field_name,)
        for t in types_:
            paths.setdefault(t, TreeLocation(path=field_path, kind=kind))
            if kind == "singleton":
                _walk_component_paths(t, field_path, seen, paths)
            # Dict-kind types are not recursed into further: a nested component under a keyed
            # collection member (e.g. subinterfaces under an interface) would need a dynamic,
            # per-instance key segment that the static schema can't express — out of scope
            # until a real nested example needs it.


COMPONENT_PATHS: dict[type, TreeLocation] = {}
_walk_component_paths(ComposedConfiguration, (), set(), COMPONENT_PATHS)


def _resolve_path(root: Any, path: tuple[str, ...]) -> Any:
    obj = root
    for segment in path:
        obj = getattr(obj, segment)
    return obj


# --------------------------------------------------------------------------- attribute maps


class DialectAttributeMap:
    """Declarative render+parse mapping for one line (or line-family) of one attribute.

    `pattern` is the single source of truth for both directions:
    - Render: `{field}` substitutes the component's own field (via `.get_value()` if it's an
      `AttributeValue`); `{ctx.field}` substitutes an inherited context field instead — needed
      for dialects (e.g. Junos flat `set` syntax) where ancestor context must repeat on every
      line rather than being implied by nesting.
    - Parse: the same placeholders compile into a regex. A placeholder's capture defaults to
      `\\S+`, except the pattern's trailing placeholder, which greedily captures the rest of the
      line — needed for free-text fields like `description`. `{field:regex}` overrides the
      capture group explicitly.

    `attribute_name` names the attribute this map is *for* — usually the pattern's only
    placeholder, but a pattern may carry other placeholders too (a line that sets several
    fields at once); all of a matched pattern's placeholders are applied/read, `attribute_name`
    just marks which one this map is registered under (relevant for identity comparison against
    `Dialect.identity_maps`).

    `value` covers a literal line with no placeholders that represents a fixed attribute value
    rather than an extracted one (e.g. Cisco's `shutdown` / `no shutdown` for a boolean
    `enabled` attribute — modeled as two maps, each a literal pattern with its own `value`): on
    parse, a match sets `attribute_name = value`; on render, the map only fires when the
    component's current value for `attribute_name` already equals `value`.
    """

    def __init__(self, component_type: type, attribute_name: str, pattern: str, value: Any = None):
        self.component_type = component_type
        self.attribute_name = attribute_name
        self.pattern = pattern
        self.value = value

        self._render_template = ""
        self.field_names: list[str] = []
        regex_parts: list[str] = []
        parsed = list(_formatter.parse(pattern))
        for i, (literal, field_name, format_spec, _conversion) in enumerate(parsed):
            self._render_template += literal
            regex_parts.append(re.escape(literal))
            if field_name is None:
                continue
            self._render_template += "{" + field_name + "}"
            self.field_names.append(field_name)
            group = field_name.replace(".", "__")
            is_trailing = i == len(parsed) - 1
            capture = format_spec if format_spec else (".+" if is_trailing else r"\S+")
            regex_parts.append(f"(?P<{group}>{capture})")
        self._regex = re.compile("^" + "".join(regex_parts) + "$")

        if not self.field_names and value is None:
            raise ValueError(
                f"{component_type.__name__}.{attribute_name}: a literal pattern (no placeholders) needs a `value`"
            )
        if self.field_names and value is not None:
            raise ValueError(
                f"{component_type.__name__}.{attribute_name}: `value` is only for literal patterns (no placeholders)"
            )

    def render_line(self, component: Any, context: dict[str, Any] | None) -> str | None:
        """Return the rendered line, or None if this map doesn't apply right now (a required
        field is unset, or — for a literal `value` map — the component's current value doesn't
        match)."""
        if self.value is not None:
            return self.pattern if _field_value(component, self.attribute_name) == self.value else None
        values: dict[str, Any] = {}
        for name in self.field_names:
            if name.startswith("ctx."):
                key = name[len("ctx.") :]
                if not context or context.get(key) is None:
                    return None
            else:
                v = _field_value(component, name)
                if v is None:
                    return None
                values[name] = v
        return self._render_template.format(ctx=SimpleNamespace(**(context or {})), **values)

    def match(self, line: str) -> dict[str, Any] | None:
        """Return extracted {attribute_name: value} fields if `line` matches, else None."""
        m = self._regex.match(line.strip())
        if m is None:
            return None
        if self.value is not None:
            return {self.attribute_name: self.value}
        fields: dict[str, Any] = {}
        for name in self.field_names:
            if name.startswith("ctx."):
                continue  # context fields flow through Dialect hooks, not component kwargs
            fields[name] = m.group(name.replace(".", "__"))
        return fields


class DialectMultilineMap:
    """One multi-line attribute: a start line, verbatim body lines, and an end line — Cisco
    `banner motd <delim> ... <delim>` is the motivating example. Unlike `DialectAttributeMap`,
    this consumes multiple physical lines to produce one value (and vice versa on render), so it
    needs its own class rather than a flag on the single-line one.

    The delimiter is chosen freely by whoever wrote the config (any single character not
    appearing in the banner text), so it can't be fixed in the dialect — `start` must contain
    exactly one `{delim}` placeholder, captured from whatever character actually follows it on
    parse. Rendering has no such text to read the delimiter from (we're generating it), so it
    always uses `default_delimiter`.
    """

    def __init__(self, component_type: type, attribute_name: str, start: str, default_delimiter: str = "#"):
        if start.count("{delim}") != 1:
            raise ValueError(
                f"""{component_type.__name__}.{attribute_name}: multiline `start` must contain exactly one """
                """{{delim}} placeholder"""
            )
        self.component_type = component_type
        self.attribute_name = attribute_name
        self.default_delimiter = default_delimiter
        self._prefix, self._suffix = start.split("{delim}")
        self._regex = re.compile(f"^{re.escape(self._prefix)}(?P<delim>\\S+){re.escape(self._suffix)}$")

    def match_start(self, line: str) -> str | None:
        """Return the captured delimiter if `line` matches the start pattern, else None."""
        m = self._regex.match(line.strip())
        return m.group("delim") if m else None

    def render_lines(self, component: Any) -> list[str] | None:
        """Return [start, *body lines, end], or None if the attribute is unset."""
        value = _field_value(component, self.attribute_name)
        if value is None:
            return None
        start_line = f"{self._prefix}{self.default_delimiter}{self._suffix}"
        return [start_line, *value.split("\n"), self.default_delimiter]


class Dialect(ABC):
    """Vendor/syntax-dialect-specific knowledge. Deliberately named `Dialect`, not `Driver` —
    it's narrower than (and composed into) a `NetworkElementDriver`, which also bundles
    transport and normalization; conflating the two names would be confusing."""

    component_order: tuple[type, ...] = ()
    identity_maps: dict[type, str] = {}
    """Per keyed-collection component type, which attribute's value becomes the dict key in
    *this dialect's* text (e.g. `"name"` for the `interface {name}` header line) — and, via
    `Mapper._flush`, also the key used when inserting the parsed component into the composed
    tree's dict. Those two roles coincide today; if a future dialect's header attribute ever
    diverges from the framework's canonical dict keying, this is the seam to split."""
    attribute_order: dict[type, tuple[str, ...]] = {}
    """Per component type, the order its own attribute maps render in — e.g. `hostname` before
    `domain_name`. Required for every type with registered maps, same as `component_order`/
    `identity_maps`: relying on the order `DialectAttributeMap`s happen to be listed in Python is
    fragile (nothing enforces it, and it's easy to reorder by accident) — this also settles
    which map renders first for a keyed-collection type, which must be its identity map."""
    pre_parse_hooks: dict[type, Callable[[str], str]] = {}
    pre_render_hooks: dict[type, Callable[[Any], Any]] = {}
    indent_unit: str = ""
    """One level's worth of leading text for a rendered line (e.g. Cisco's `" "`). Not
    abstract — it's plain string repetition, no dialect-specific logic, so `Mapper` applies it
    directly (`indent_unit * depth`). Defaults to no indentation at all, so a flat dialect
    (e.g. Junos `set` syntax) needs no override. Cisco's `resolve_frame` reads the same
    constant when measuring a parsed line's column depth, so the "what does one indent level
    look like" fact lives in exactly one place instead of two methods that could drift apart."""

    def pre_parse(self, component_type: type, line: str) -> str:
        hook = self.pre_parse_hooks.get(component_type)
        return hook(line) if hook else line

    def pre_render(self, component: Any) -> Any:
        hook = self.pre_render_hooks.get(type(component))
        return hook(component) if hook else component

    @abstractmethod
    def resolve_frame(self, line: str, stack: list[ParseFrame]) -> int:
        """Return how many frames should be popped off the stack (from the top, excluding the
        root sentinel) before `line` is matched against attribute maps. This is the one
        genuinely vendor-specific parsing decision — e.g. indentation depth for Cisco block
        syntax."""

    def negate(self, line: str) -> str:
        """Prefix a rendered line to express removal (Cisco `no `, Junos `delete `)."""
        return f"no {line}"

    def open_block(self, path: SyntaxPath, depth: int) -> str | None:
        return None

    def close_block(self, path: SyntaxPath, depth: int) -> str | None:
        return None

    def transition(self, from_path: SyntaxPath, to_path: SyntaxPath) -> list[str]:
        """Emit only what's needed to move render context from from_path to to_path. Not used
        yet (no patch rendering) — composes open_block/close_block once render_patch exists."""
        return []

    def component_separator(self) -> str | None:
        """A line emitted between (not after) consecutive top-level components when rendering
        the whole tree — e.g. Cisco's `!`. None (the default) means no separator; most dialects
        don't need one. Not meant to reproduce a real device's exact separator placement/count,
        just a readable boundary between components."""
        return None


class Mapper:
    """Binds a `Dialect` to a set of `DialectAttributeMap`s and drives render/parse from them."""

    def __init__(self, dialect: Dialect, attribute_maps: list[DialectAttributeMap]):
        self.dialect = dialect
        self.maps_by_type: dict[type, list[DialectAttributeMap]] = defaultdict(list)
        for m in attribute_maps:
            self.maps_by_type[m.component_type].append(m)

        for component_type, maps in self.maps_by_type.items():
            if component_type not in COMPONENT_PATHS:
                raise ValueError(
                    f"{component_type.__name__} isn't reachable anywhere in ComposedConfiguration's schema"
                )
            if component_type not in dialect.component_order:
                raise ValueError(
                    f"{component_type.__name__} has attribute maps but is missing from "
                    f"{type(dialect).__name__}.component_order"
                )
            if COMPONENT_PATHS[component_type].kind == "dict" and component_type not in dialect.identity_maps:
                raise ValueError(
                    f"{component_type.__name__} is a keyed collection type but has no entry in "
                    f"{type(dialect).__name__}.identity_maps"
                )

            order = dialect.attribute_order.get(component_type)
            if order is None:
                raise ValueError(
                    f"{component_type.__name__} has attribute maps but is missing from "
                    f"{type(dialect).__name__}.attribute_order"
                )
            unordered = {m.attribute_name for m in maps} - set(order)
            if unordered:
                raise ValueError(
                    f"{component_type.__name__}.attribute_order is missing {sorted(unordered)} — "
                    f"""every attribute with a map must be listed in {type(dialect).__name__}.
                    attribute_order[{component_type.__name__}]"""
                )
            maps.sort(key=lambda m: order.index(m.attribute_name))

    def supported_components(self) -> list[str]:
        """Dotted `ComposedConfiguration` paths of the component types this Mapper's
        dialect/attribute-maps cover at all — e.g. `["interfaces", "system.config"]`. A component
        with even one registered `DialectAttributeMap` counts as supported in full; this isn't
        attribute-level detail (which fields of `interfaces` specifically) — just which
        components exist for this dialect.

        Derived purely from the registered `DialectAttributeMap`s, so a dialect author gets
        accurate capability reporting for free just by declaring `INTERFACE_MAPS`/`SYSTEM_MAPS`-
        style attribute maps — nothing extra to keep in sync."""
        return sorted(".".join(COMPONENT_PATHS[component_type].path) for component_type in self.maps_by_type)

    # ---------------------------------------------------------------- render

    def render_component(self, component: Any, depth: int = 0) -> list[LineRecord]:
        """Render one component's own lines."""
        component = self.dialect.pre_render(component)
        component_type = type(component)
        identity_attr = self.dialect.identity_maps.get(component_type)
        records: list[LineRecord] = []
        path: SyntaxPath = (str(_field_value(component, identity_attr)),) if identity_attr else ()

        for m in self.maps_by_type[component_type]:
            # A singleton has no header/body distinction at all — every one of its lines is its
            # own independent top-level command (e.g. "hostname X"), not nested under anything.
            base_depth = depth if identity_attr is None else depth + 1

            if isinstance(m, DialectMultilineMap):
                lines = m.render_lines(component)
                if lines is None:
                    continue
                for i, text in enumerate(lines):
                    role: LineRole = "header" if i == 0 else ("trailer" if i == len(lines) - 1 else "body")
                    records.append(
                        LineRecord(
                            path=path,
                            component=component,
                            component_type=component_type,
                            depth=base_depth,
                            role=role,
                            line=self.dialect.indent_unit * base_depth + text,
                        )
                    )
                continue

            line = m.render_line(component, context=None)
            if line is None:
                continue
            is_header = identity_attr is not None and m.attribute_name == identity_attr
            d = depth if is_header else base_depth
            records.append(
                LineRecord(
                    path=path,
                    component=component,
                    component_type=component_type,
                    depth=d,
                    role="header" if is_header else "body",
                    line=self.dialect.indent_unit * d + line,
                )
            )
        return records

    def render(self, root: Any) -> RenderResult:
        records: list[LineRecord] = []
        separator = self.dialect.component_separator()
        for component_type in self.dialect.component_order:
            if component_type not in self.maps_by_type:
                continue
            location = COMPONENT_PATHS[component_type]
            target = _resolve_path(root, location.path)
            components = target.values() if location.kind == "dict" else [target]
            for component in components:
                if separator is not None and records:
                    records.append(
                        LineRecord(path=(), component=None, component_type=None, depth=0, role="body", line=separator)
                    )
                records.extend(self.render_component(component, depth=0))
        return RenderResult(text="\n".join(r.line for r in records), lines=records)

    # ----------------------------------------------------------------- parse

    def _flush(self, frame: ParseFrame, root: Any) -> Any:
        location = COMPONENT_PATHS[frame.component_type]
        target_collection = _resolve_path(root, location.path)
        kwargs = dict(frame.kwargs)
        model_fields = frame.component_type.model_fields
        if "index" in model_fields and "index" not in kwargs and model_fields["index"].is_required():
            kwargs["index"] = len(target_collection)
        component = frame.component_type(**kwargs)
        identity_value = kwargs[self.dialect.identity_maps[frame.component_type]]
        target_collection[identity_value] = component
        return component

    def parse(self, text: str, root_factory: Callable[[], Any]) -> ParseResult:
        root = root_factory()
        stack: list[ParseFrame] = [ParseFrame(path=(), component_type=None, kwargs={}, depth=-1)]
        records: list[LineRecord] = []
        # Multi-line capture in progress: (component_type, attribute_name, delimiter, lines so
        # far, frame to write into once closed — None means "apply directly via its tree path").
        active: tuple[type, str, str, list[str], ParseFrame | None] | None = None

        for raw_line in text.splitlines():
            if active is not None:
                t, attr, delim, collected, target_frame = active
                if raw_line.strip() == delim:
                    value = "\n".join(collected)
                    if target_frame is not None:
                        target_frame.kwargs[attr] = value
                    else:
                        setattr(_resolve_path(root, COMPONENT_PATHS[t].path), attr, AttributeValue(value=value))
                    records.append(
                        LineRecord(
                            path=stack[-1].path,
                            component=None,
                            component_type=t,
                            depth=len(stack) - 1,
                            role="trailer",
                            line=raw_line,
                        )
                    )
                    active = None
                else:
                    collected.append(raw_line)
                    records.append(
                        LineRecord(
                            path=stack[-1].path,
                            component=None,
                            component_type=t,
                            depth=len(stack) - 1,
                            role="body",
                            line=raw_line,
                        )
                    )
                continue

            if not raw_line.strip():
                continue

            pop_count = self.dialect.resolve_frame(raw_line, stack)
            for _ in range(min(pop_count, len(stack) - 1)):
                popped = stack.pop()
                component = self._flush(popped, root)
                records.append(
                    LineRecord(
                        path=popped.path,
                        component=component,
                        component_type=popped.component_type,
                        depth=len(stack) - 1,
                        role="trailer",
                        line="",
                    )
                )

            frame = stack[-1]
            current_type = frame.component_type
            matched: tuple[type, dict[str, Any], Literal["update", "open", "singleton"]] | None = None
            started_multiline = False

            if current_type is not None:
                # Inside an open keyed-collection block: only that type's own maps apply, as
                # field updates — never as a fresh identity match (that already happened).
                for m in self.maps_by_type[current_type]:
                    normalized = self.dialect.pre_parse(current_type, raw_line)
                    if isinstance(m, DialectMultilineMap):
                        delim = m.match_start(normalized)
                        if delim is not None:
                            active = (current_type, m.attribute_name, delim, [], frame)
                            started_multiline = True
                            break
                        continue
                    fields = m.match(normalized)
                    if fields is not None:
                        matched = (current_type, fields, "update")
                        break
            else:
                for t, maps in self.maps_by_type.items():
                    kind = COMPONENT_PATHS[t].kind
                    for m in maps:
                        normalized = self.dialect.pre_parse(t, raw_line)
                        if isinstance(m, DialectMultilineMap):
                            delim = m.match_start(normalized)
                            if delim is not None:
                                active = (t, m.attribute_name, delim, [], None)
                                started_multiline = True
                                break
                            continue
                        if kind == "dict" and m.attribute_name != self.dialect.identity_maps[t]:
                            continue  # only the identity map may open a new component
                        fields = m.match(normalized)
                        if fields is not None:
                            matched = (t, fields, "open" if kind == "dict" else "singleton")
                            break
                    if matched or started_multiline:
                        break

            if started_multiline:
                records.append(
                    LineRecord(
                        path=frame.path,
                        component=None,
                        component_type=active[0],
                        depth=len(stack) - 1,
                        role="header",
                        line=raw_line,
                    )
                )
                continue

            if matched is None:
                records.append(
                    LineRecord(
                        path=frame.path,
                        component=None,
                        component_type=None,
                        depth=len(stack) - 1,
                        role="body",
                        line=raw_line,
                    )
                )
                continue

            t, fields, action = matched
            if action == "update":
                frame.kwargs.update(fields)
                records.append(
                    LineRecord(
                        path=frame.path,
                        component=None,
                        component_type=t,
                        depth=len(stack) - 1,
                        role="body",
                        line=raw_line,
                    )
                )
            elif action == "open":
                identity_attr = self.dialect.identity_maps[t]
                new_frame = ParseFrame(
                    path=frame.path + (str(fields[identity_attr]),),
                    component_type=t,
                    kwargs=dict(fields),
                    depth=len(raw_line) - len(raw_line.lstrip(" ")),
                )
                stack.append(new_frame)
                records.append(
                    LineRecord(
                        path=new_frame.path,
                        component=None,
                        component_type=t,
                        depth=len(stack) - 1,
                        role="header",
                        line=raw_line,
                    )
                )
            else:  # singleton — apply directly, no frame, no deferred construction
                target = _resolve_path(root, COMPONENT_PATHS[t].path)
                for field_name, raw_value in fields.items():
                    setattr(target, field_name, AttributeValue(value=raw_value))
                records.append(
                    LineRecord(
                        path=COMPONENT_PATHS[t].path,
                        component=target,
                        component_type=t,
                        depth=len(stack) - 1,
                        role="body",
                        line=raw_line,
                    )
                )

        while len(stack) > 1:
            popped = stack.pop()
            component = self._flush(popped, root)
            records.append(
                LineRecord(
                    path=popped.path,
                    component=component,
                    component_type=popped.component_type,
                    depth=len(stack),
                    role="trailer",
                    line="",
                )
            )

        return ParseResult(configuration=root, lines=records)
