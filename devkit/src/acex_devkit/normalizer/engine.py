"""Stateless rule engine and data types for config normalization.

Two independent passes:
    normalize_pass  — drops lines/blocks that are not intent-config
    mask_pass       — rewrites lines to redact secrets

The passes are isolated: normalize never touches content it keeps,
mask never drops lines. This makes the operations order-independent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Rule types ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LineRule:
    """Matches a full line → the line is dropped."""
    name: str
    pattern: re.Pattern


@dataclass(frozen=True)
class BlockRule:
    """Matches a block header → header + indented body are dropped."""
    name: str
    pattern: re.Pattern


@dataclass(frozen=True)
class RewriteRule:
    """Rewrites a line (e.g. redact secrets)."""
    name: str
    pattern: re.Pattern
    replacement: str


# ── Result types ──────────────────────────────────────────────────────

@dataclass
class OpStats:
    lines_in: int = 0
    lines_out: int = 0
    lines_dropped: int = 0
    blocks_dropped: int = 0
    lines_redacted: int = 0
    by_rule: dict[str, int] = field(default_factory=dict)

    def _bump(self, rule: str) -> None:
        self.by_rule[rule] = self.by_rule.get(rule, 0) + 1


@dataclass
class OpResult:
    config: str
    operation: str  # "normalize" or "mask"
    stats: OpStats


# ── Engine ────────────────────────────────────────────────────────────

class NormalizerEngine:
    """Stateless rule engine used by BaseNormalizer subclasses."""

    def normalize_pass(
        self,
        raw: str,
        *,
        line_rules: list[LineRule],
        block_rules: list[BlockRule],
        is_block_continuation,
        is_block_terminator,
    ) -> tuple[list[str], OpStats]:
        stats = OpStats()
        lines = raw.splitlines()
        stats.lines_in = len(lines)
        out: list[str] = []

        i = 0
        while i < len(lines):
            line = lines[i]

            block_hit = next(
                (r for r in block_rules if r.pattern.match(line)), None
            )
            if block_hit:
                stats.blocks_dropped += 1
                stats._bump(f"block:{block_hit.name}")
                stats.lines_dropped += 1
                i += 1
                while i < len(lines) and (
                    is_block_continuation(lines[i])
                    or is_block_terminator(lines[i])
                ):
                    stats.lines_dropped += 1
                    i += 1
                continue

            line_hit = next(
                (r for r in line_rules if r.pattern.match(line)), None
            )
            if line_hit:
                stats.lines_dropped += 1
                stats._bump(f"line:{line_hit.name}")
                i += 1
                continue

            out.append(line)
            i += 1

        return out, stats

    def mask_pass(
        self,
        raw: str,
        *,
        rewrite_rules: list[RewriteRule],
    ) -> tuple[list[str], OpStats]:
        stats = OpStats()
        lines = raw.splitlines()
        stats.lines_in = len(lines)
        out: list[str] = []

        for line in lines:
            rewritten = line
            for rule in rewrite_rules:
                new = rule.pattern.sub(rule.replacement, rewritten)
                if new != rewritten:
                    stats.lines_redacted += 1
                    stats._bump(f"redact:{rule.name}")
                    rewritten = new
                    break
            out.append(rewritten)

        stats.lines_out = len(out)
        return out, stats

    @staticmethod
    def collapse_and_trim(
        lines: list[str],
        stats: OpStats,
        comment_marker: str = "!",
    ) -> list[str]:
        collapsed: list[str] = []
        prev_marker = False
        for line in lines:
            is_marker = line.strip() == comment_marker
            if is_marker and prev_marker:
                stats.lines_dropped += 1
                stats._bump("post:collapse_comment")
                continue
            collapsed.append(line)
            prev_marker = is_marker

        while collapsed and collapsed[0].strip() in ("", comment_marker):
            collapsed.pop(0)
        while collapsed and collapsed[-1].strip() in ("", comment_marker):
            collapsed.pop()
        return collapsed
