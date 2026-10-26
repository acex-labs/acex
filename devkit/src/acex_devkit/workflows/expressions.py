"""The workflow expression language: read artifacts and compute a value, nothing else.

An expression is parsed into a tree of known parts and walked by `Expression.evaluate`; nothing ever reaches
Python's eval or exec, and anything unknown is refused when the expression is parsed. Regular expressions
run on re2, in time linear in the text, so no pattern can hang a worker.

    success_rate >= 80                       a node's own value of artifact success_rate, node by node
    config[core-1] contains "ntp server"     a named node's value
    percent(reachable) >= 95                 across nodes
    regex(result.output, "Version (\\S+)")    in a step's own artifact rows: what the step just did

Artifacts are named by the steps that leave them and read by name; a name followed by `(` is a function.
`Template` renders text with expressions in braces, e.g. the commands of an execute step:
`show interface {iface}`.
"""

import re
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Protocol

import re2


class ExpressionError(ValueError):
    """An expression that can't be parsed, or can't be evaluated against the artifacts at hand."""


class Artifacts(Protocol):
    """Where an expression reads artifacts from, by name. Nodes are named by hostname."""

    def nodes(self, name: str) -> list[str]:
        """The nodes an artifact has a value for, in order; empty for one with a single value, or none yet."""

    def get(self, name: str, node: str | None) -> Any:
        """An artifact's value for one node, or its single value for None; None if there is none."""


@dataclass(frozen=True)
class Literal:
    value: Any


@dataclass(frozen=True)
class Ref:
    name: str
    host: str | None
    path: tuple[str, ...]


@dataclass(frozen=True)
class Call:
    name: str
    args: tuple


@dataclass(frozen=True)
class Not:
    operand: Any


@dataclass(frozen=True)
class BoolOp:
    op: str
    operands: tuple


@dataclass(frozen=True)
class Compare:
    op: str
    left: Any
    right: Any


@dataclass(frozen=True)
class Token:
    kind: str  # name, number, string, host, op
    value: Any
    position: int


class Lexer:
    """Splits an expression into tokens. A host in brackets is taken as written, so `[core-1]` needs no quotes."""

    PATTERN = re.compile(
        r"\s*(?:(?P<number>\d+(?:\.\d+)?)"
        r"""|(?P<string>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')"""
        r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
        r"|(?P<op>==|!=|<=|>=|[<>(),.\[\]]))"
    )

    def __init__(self, text: str):
        self.text = text

    def tokens(self) -> list[Token]:
        tokens, position = [], 0
        while position < len(self.text):
            if self.text[position:].strip() == "":
                break
            if tokens and tokens[-1].value == "[" and tokens[-1].kind == "op":
                end = self.text.find("]", position)
                if end < 0:
                    raise ExpressionError(f"unclosed '[' at {position}")
                tokens.append(Token("host", self.text[position:end].strip().strip("\"'"), position))
                position = end
                continue
            match = self.PATTERN.match(self.text, position)
            if match is None or match.end() == position:
                raise ExpressionError(f"unexpected {self.text[position:].strip()[:10]!r} at {position}")
            kind = match.lastgroup
            raw = match.group(kind)
            value = float(raw) if kind == "number" and "." in raw else int(raw) if kind == "number" else raw
            if kind == "string":
                # Only quotes and backslashes are escaped, so a pattern keeps its \S and \d.
                value = re.sub(r"\\([\"'\\\\])", r"\1", raw[1:-1])
            tokens.append(Token(kind, value, match.start(kind)))
            position = match.end()
        return tokens


class Parser:
    """Builds the tree. Precedence, loosest first: or, and, not, comparisons, then values and calls."""

    COMPARISONS = ("==", "!=", "<=", ">=", "<", ">", "contains", "matches")
    LITERALS = {"true": True, "false": False, "null": None}
    KEYWORDS = ("and", "or", "not", "contains", "matches")

    def __init__(self, text: str):
        self.text = text
        self.tokens = Lexer(text).tokens()
        self.index = 0

    def parse(self) -> Any:
        if not self.tokens:
            raise ExpressionError("empty expression")
        tree = self.disjunction()
        if self.index < len(self.tokens):
            token = self.tokens[self.index]
            raise ExpressionError(f"unexpected {token.value!r} at {token.position}")
        return tree

    def peek(self) -> Token | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self, value: str | None = None, kind: str | None = None) -> Token:
        token = self.peek()
        if token is None or (value is not None and token.value != value) or (kind is not None and token.kind != kind):
            expected = value or kind
            found = f"{token.value!r} at {token.position}" if token else "the end"
            raise ExpressionError(f"expected {expected!r}, found {found}")
        self.index += 1
        return token

    def accept(self, value: str) -> bool:
        token = self.peek()
        if token is not None and token.value == value and token.kind in ("op", "name"):
            self.index += 1
            return True
        return False

    def disjunction(self) -> Any:
        operands = [self.conjunction()]
        while self.accept("or"):
            operands.append(self.conjunction())
        return operands[0] if len(operands) == 1 else BoolOp("or", tuple(operands))

    def conjunction(self) -> Any:
        operands = [self.negation()]
        while self.accept("and"):
            operands.append(self.negation())
        return operands[0] if len(operands) == 1 else BoolOp("and", tuple(operands))

    def negation(self) -> Any:
        return Not(self.negation()) if self.accept("not") else self.comparison()

    def comparison(self) -> Any:
        left = self.value()
        token = self.peek()
        if token is not None and token.value in self.COMPARISONS and token.kind in ("op", "name"):
            self.index += 1
            return Compare(token.value, left, self.value())
        return left

    def value(self) -> Any:
        token = self.peek()
        if token is None:
            raise ExpressionError("expected a value, found the end")
        if token.kind in ("number", "string"):
            self.index += 1
            return Literal(token.value)
        if self.accept("("):
            tree = self.disjunction()
            self.take(")")
            return tree
        if token.kind == "name" and token.value in self.LITERALS:
            self.index += 1
            return Literal(self.LITERALS[token.value])
        following = self.tokens[self.index + 1] if self.index + 1 < len(self.tokens) else None
        if token.kind == "name" and following is not None and following.value == "(" and following.kind == "op":
            if token.value not in Expression.FUNCTIONS:
                raise ExpressionError(f"unknown function {token.value}() at {token.position}")
            return self.call()
        if token.kind == "name" and token.value not in self.KEYWORDS:
            return self.reference()
        raise ExpressionError(f"unexpected {token.value!r} at {token.position}")

    def reference(self) -> Ref:
        name = self.take(kind="name").value
        host = None
        if self.accept("["):
            host = self.take(kind="host").value
            self.take("]")
        path = []
        while self.accept("."):
            token = self.take()
            if token.kind not in ("name", "number"):
                raise ExpressionError(f"expected a field name at {token.position}")
            path.append(str(token.value))
        return Ref(name, host, tuple(path))

    def call(self) -> Call:
        name = self.take(kind="name").value
        self.take("(")
        args = [] if self.accept(")") else None
        if args is None:
            args = [self.disjunction()]
            while self.accept(","):
                args.append(self.disjunction())
            self.take(")")
        low, high = Expression.FUNCTIONS[name]
        if not low <= len(args) <= high:
            raise ExpressionError(f"{name}() takes {low if low == high else f'{low} to {high}'} arguments")
        return Call(name, tuple(args))


@dataclass
class Expression:
    """A parsed expression. `names` are the artifacts it reads node by node outside an aggregate: when any of
    them has values per node, it is evaluated once per node."""

    MAX_LENGTH = 2000
    MAX_TEXT = 10_000_000
    #: name: (fewest, most) arguments. all/any/percent and one-argument count run their argument per node.
    FUNCTIONS = {
        "regex": (2, 2),
        "lines": (1, 2),
        "count": (1, 2),
        "column": (2, 3),
        "all": (1, 1),
        "any": (1, 1),
        "percent": (1, 1),
    }
    AGGREGATES = ("all", "any", "percent")
    #: What an artifact can't be named: the language's own words, and `result`, a step's own result.
    RESERVED = frozenset({*Parser.KEYWORDS, *Parser.LITERALS, "result"})

    text: str
    tree: Any = field(init=False)
    names: list[str] = field(init=False)

    def __post_init__(self):
        if len(self.text) > self.MAX_LENGTH:
            raise ExpressionError(f"expression longer than {self.MAX_LENGTH} characters")
        self.tree = Parser(self.text).parse()
        self.names = list(dict.fromkeys(self.free_names(self.tree)))
        self.check_patterns(self.tree)

    # ------------------------------------------------------------------ structure

    @classmethod
    def is_aggregate(cls, node: Any) -> bool:
        return isinstance(node, Call) and (
            node.name in cls.AGGREGATES or (node.name == "count" and len(node.args) == 1)
        )

    @classmethod
    def free_names(cls, node: Any) -> list[str]:
        """Artifacts read node by node outside an aggregate, in the order they appear."""
        if isinstance(node, Ref):
            return [node.name] if node.host is None else []
        if cls.is_aggregate(node):
            return []
        return [name for child in cls.children(node) for name in cls.free_names(child)]

    @staticmethod
    def children(node: Any) -> tuple:
        if isinstance(node, Call):
            return node.args
        if isinstance(node, Not):
            return (node.operand,)
        if isinstance(node, BoolOp):
            return node.operands
        if isinstance(node, Compare):
            return (node.left, node.right)
        return ()

    def references(self, node: Any = None) -> list[Ref]:
        """Every artifact reference, for checking that the artifacts exist."""
        node = self.tree if node is None else node
        if isinstance(node, Ref):
            return [node]
        return [ref for child in self.children(node) for ref in self.references(child)]

    def check_patterns(self, node: Any) -> None:
        """Compile every literal pattern now, so a bad one is refused when the expression is saved."""
        if isinstance(node, Call) and node.name in ("regex", "lines", "count") and len(node.args) == 2:
            if isinstance(node.args[1], Literal):
                self.pattern(node.args[1].value)
        if isinstance(node, Compare) and node.op == "matches" and isinstance(node.right, Literal):
            self.pattern(node.right.value)
        for child in self.children(node):
            self.check_patterns(child)

    @staticmethod
    @cache
    def pattern(text: Any) -> Any:
        try:
            return re2.compile(str(text))
        except re2.error as exc:
            raise ExpressionError(f"bad pattern {text!r}: {exc}") from None

    # ------------------------------------------------------------------ evaluation

    def nodes(self, artifacts: Artifacts) -> list[str] | None:
        """The nodes to evaluate per node, or None to evaluate once: when it reads no artifact node by node,
        or only artifacts with a single value."""
        nodes = list(dict.fromkeys(node for name in self.names for node in artifacts.nodes(name)))
        return nodes or None

    def evaluate(self, artifacts: Artifacts, node: str | None = None) -> Any:
        return self.walk(self.tree, artifacts, node)

    def walk(self, tree: Any, artifacts: Artifacts, node: str | None) -> Any:
        if isinstance(tree, Literal):
            return tree.value
        if isinstance(tree, Ref):
            return self.resolve(tree, artifacts, node)
        if isinstance(tree, Not):
            return not self.walk(tree.operand, artifacts, node)
        if isinstance(tree, BoolOp):
            values = (self.walk(operand, artifacts, node) for operand in tree.operands)
            return all(values) if tree.op == "and" else any(values)
        if isinstance(tree, Compare):
            return self.compare(tree.op, self.walk(tree.left, artifacts, node), self.walk(tree.right, artifacts, node))
        if self.is_aggregate(tree):
            return self.aggregate(tree, artifacts)
        args = [self.walk(arg, artifacts, node) for arg in tree.args]
        return getattr(self, f"fn_{tree.name}")(*args)

    def resolve(self, ref: Ref, artifacts: Artifacts, node: str | None) -> Any:
        """A reference's value: the named node's, the current node's, or the artifact's single value. An
        artifact not made yet, or a field it doesn't have, is None."""
        host = ref.host or node
        value = artifacts.get(ref.name, host) if host is not None else None
        if value is None:
            value = artifacts.get(ref.name, None)
        if value is None and host is None and artifacts.nodes(ref.name):
            raise ExpressionError(f"{ref.name} is per node: name one, {ref.name}[host], or use all/any/percent")
        for part in ref.path:
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
                value = value[int(part)]
            else:
                return None
        return value

    def aggregate(self, call: Call, artifacts: Artifacts) -> Any:
        inner = call.args[0]
        names = list(dict.fromkeys(self.free_names(inner)))
        nodes = list(dict.fromkeys(n for name in names for n in artifacts.nodes(name)))
        results = []
        for node in nodes:
            value = self.walk(inner, artifacts, node)
            if value is not None and not isinstance(value, bool):
                raise ExpressionError(
                    f"{call.name}() needs true or false per node, but got {self.describe(value)} on {node}: "
                    f"compare it, e.g. {call.name}(x == ...)"
                )
            results.append(bool(value))
        if call.name == "all":
            return all(results)
        if call.name == "any":
            return any(results)
        if call.name == "count":
            return sum(results)
        return round(sum(results) / len(results) * 100, 1) if results else 0.0

    @classmethod
    def compare(cls, op: str, left: Any, right: Any) -> bool:
        if op == "contains":
            if isinstance(left, list):
                return any(str(item) == str(right) for item in left)
            return left is not None and str(right) in cls.text_of(left, "contains")
        if op == "matches":
            return left is not None and cls.pattern(right).search(cls.text_of(left, "matches")) is not None
        left, right = cls.comparable(left), cls.comparable(right)
        if op in ("==", "!="):
            return (left == right) == (op == "==")
        if left is None or right is None or type(left) is not type(right):
            return False
        return {"<": left < right, "<=": left <= right, ">": left > right, ">=": left >= right}[op]

    @staticmethod
    def comparable(value: Any) -> Any:
        """Numbers compare as numbers, also when one side is a number written as text."""
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return value
        return value

    @classmethod
    def text_of(cls, value: Any, used_by: str = "text") -> str:
        """A value as text: a list one item per line, nothing as empty. An object is refused rather than written
        out as Python would, which would read like text but not match like it."""
        if isinstance(value, dict) or (isinstance(value, list) and any(isinstance(i, dict | list) for i in value)):
            raise ExpressionError(f"{used_by} needs text, but got {cls.describe(value)}")
        text = "\n".join(map(str, value)) if isinstance(value, list) else "" if value is None else str(value)
        if len(text) > cls.MAX_TEXT:
            raise ExpressionError(f"text longer than {cls.MAX_TEXT} characters")
        return text

    @staticmethod
    def describe(value: Any) -> str:
        """What a value is, for an error: an object names its fields, so the right one can be picked."""
        if isinstance(value, dict):
            fields = ", ".join(list(value)[:8]) + (", ..." if len(value) > 8 else "")
            return f"an object with fields {fields}: read one, e.g. x.{next(iter(value), 'field')}"
        if isinstance(value, list):
            return f"a list of {len(value)}"
        return f"{type(value).__name__} {value!r}"[:120]

    def inputs(self, artifacts: Artifacts, nodes: list[str] | None = None, limit: int = 20) -> dict[str, dict]:
        """What the expression read, to see why it came out as it did: each reference as written and its value,
        per node, by default on every node the references have values for; "" holds them when there are none."""
        refs = list({self.ref_text(ref): ref for ref in self.references()}.items())
        if nodes is None:
            nodes = list(dict.fromkeys(n for _, ref in refs if ref.host is None for n in artifacts.nodes(ref.name)))
        values = {}
        for node in nodes[:limit] or [None]:
            shown = {}
            for text, ref in refs:
                try:
                    shown[text] = self.resolve(ref, artifacts, node)
                except ExpressionError as exc:
                    shown[text] = f"({exc})"
            values[node or ""] = shown
        return values

    @staticmethod
    def ref_text(ref: Ref) -> str:
        return ref.name + (f"[{ref.host}]" if ref.host else "") + "".join(f".{part}" for part in ref.path)

    # ------------------------------------------------------------------ functions

    def fn_regex(self, text: Any, pattern: Any) -> Any:
        """The first match's first group, or the whole match without groups; None without a match."""
        match = self.pattern(pattern).search(self.text_of(text, "regex()"))
        if match is None:
            return None
        return match.group(1) if match.groups() else match.group(0)

    def fn_lines(self, text: Any, pattern: Any = None) -> list[str]:
        lines = self.text_of(text, "lines() and count()").splitlines()
        return lines if pattern is None else [line for line in lines if self.pattern(pattern).search(line)]

    def fn_count(self, text: Any, pattern: Any = None) -> int:
        return len(self.fn_lines(text, pattern))

    def fn_column(self, text: Any, number: Any, separator: Any = None) -> list[str]:
        """Field `number` (from 1) of every line that has one, split on whitespace or `separator`."""
        index = int(self.comparable(number)) - 1
        lines = self.text_of(text, "column()").splitlines()
        fields = (line.split(separator) if separator else line.split() for line in lines)
        return [parts[index].strip() for parts in fields if 0 <= index < len(parts)]


@dataclass
class Template:
    """Text with expressions in braces, rendered per node; `{{` and `}}` are literal braces. A value that is
    None renders empty, and a list renders one item per line."""

    PART = re.compile(r"\{\{|\}\}|\{([^{}]*)\}")

    text: str
    expressions: list[Expression] = field(init=False)

    def __post_init__(self):
        self.expressions = [
            Expression(m.group(1).strip()) for m in self.PART.finditer(self.text) if m.group(1) is not None
        ]

    @property
    def names(self) -> list[str]:
        return list(dict.fromkeys(name for expression in self.expressions for name in expression.names))

    def references(self) -> list[Ref]:
        return [ref for expression in self.expressions for ref in expression.references()]

    def render(self, artifacts: Artifacts, node: str | None = None) -> str:
        values = iter(expression.evaluate(artifacts, node) for expression in self.expressions)
        parts, last = [], 0
        for match in self.PART.finditer(self.text):
            literal = match.group(1) is None
            parts += [
                self.text[last : match.start()],
                match.group(0)[0] if literal else self.text_of(next(values), "{...}"),
            ]
            last = match.end()
        return "".join([*parts, self.text[last:]])

    @staticmethod
    def text_of(value: Any, used_by: str = "{...}") -> str:
        return Expression.text_of(value, used_by)
