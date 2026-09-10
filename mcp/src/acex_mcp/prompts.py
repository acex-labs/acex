"""Reusable analysis tasks, offered to any client.

These are exposed as MCP prompts so an external client gets ACE-X's analysis
framing without having to be told it. They deliberately name no tools: the tool
descriptions carry that, and a prompt that hardcodes tool names is a prompt that
goes stale the moment one is renamed.
"""

from fastmcp import FastMCP

_FRAMING = """\
You are analysing a network device configuration change in ACE-X.

Lines starting with '-' were present before and are gone; lines starting with
'+' were added. In ACE-X, "desired" is the configuration ACE-X intends a device
to have and "observed" is a snapshot collected from the device — a diff between
two observed snapshots shows what changed on the device itself over time.

You have read-only tools for looking up nodes, their desired and observed
configurations, configuration drift, snapshot history, and LLDP neighbours. Use
them instead of hedging: if your answer would otherwise contain a conditional
like "if that VLAN is still needed downstream", look up the actual neighbour and
check its configuration, then state the verified fact. A couple of targeted
lookups, not an open-ended exploration. If a lookup comes back empty or a tool
is unavailable, say so plainly rather than restating the guess as though it were
still an open question.

Focus on functional impact over restating the diff. Use correct networking
terminology. Be concise. Flag anything risky or unusual. Reply in the same
language as the question.
"""


def register(mcp: FastMCP) -> None:

    @mcp.prompt
    def explain_config_change(diff: str, context: str = "") -> str:
        """Explain in plain language what a configuration diff actually changed."""
        return (
            f"{_FRAMING}\n"
            "Explain what changed in this configuration diff in plain language. Focus on the "
            "functional impact — what network behaviour or state actually changed? Be concise "
            "(2-4 sentences). Do not restate the raw diff lines.\n\n"
            f"{context}\nDiff:\n{diff}"
        )

    @mcp.prompt
    def assess_config_risk(diff: str, context: str = "") -> str:
        """Assess the intent and risk of a configuration change."""
        return (
            f"{_FRAMING}\n"
            "Assess the risk and likely intent of this configuration change. Cover briefly:\n"
            "1. What was the likely intent?\n"
            "2. Are there risks or concerns — outage risk, security implications, missing "
            "complementary changes?\n"
            "3. Overall risk level: LOW / MEDIUM / HIGH, with a one-line rationale.\n\n"
            f"{context}\nDiff:\n{diff}"
        )

    @mcp.prompt
    def assess_config_alignment(diff: str, context: str = "") -> str:
        """Judge whether a change moves a device toward or away from its desired state."""
        return (
            f"{_FRAMING}\n"
            "Determine whether this change moves the device TOWARD or AWAY FROM its desired "
            "state. Changes aligned with desired state are intentional and expected; changes "
            "that diverge may indicate drift, manual intervention, or misconfiguration.\n\n"
            "Respond with exactly one of these labels on the first line:\n"
            "  ALIGNED — consistent with moving toward desired state\n"
            "  DIVERGED — moves away from or conflicts with desired state\n"
            "  NEUTRAL — unrelated to desired state (operational state, log timestamps, etc.)\n\n"
            "Follow with 1-2 sentences explaining why.\n\n"
            f"{context}\nDiff:\n{diff}"
        )
