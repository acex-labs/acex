"""The tools a model is offered: local ones handled in-process, and MCP's."""

import json

from fastmcp import Client

from .events import NavigateEvent, PlanEvent, ToolCallEvent
from .types import ToolCall, ToolResult, ToolSpec

#: Suggests a page to the user. Calling it does not navigate anything
#: server-side — the loop intercepts the call and signals the suggestion to
#: the frontend. Deliberately conservative: only off a clear, direct request.
NAVIGATE_TOOL = ToolSpec(
    name="navigate_to",
    description=(
        "Suggest opening another page in the web UI for the user. This does NOT "
        "navigate anything by itself — it shows the user a clickable link; they "
        "decide whether to follow it. Only call this when the user has directly "
        "asked to go to / open / see a specific, known page or entity. If it's not "
        "a clear, direct request, do not call this tool — instead ask in your reply "
        "whether they'd like you to open it, and wait for their confirmation."
    ),
    parameters={
        "type": "object",
        "properties": {
            "page": {
                "type": "string",
                "enum": ["node_detail", "site_detail", "nodes_list", "sites_list", "dashboard"],
                "description": "Which known page to open.",
            },
            "id": {
                "type": "string",
                "description": (
                    "Entity id, for node_detail/site_detail — only if you actually have "
                    "the id itself (e.g. from a tool result). Prefer `name` otherwise."
                ),
            },
            "name": {
                "type": "string",
                "description": (
                    "Entity name, for node_detail/site_detail — use this instead of `id` "
                    "whenever you only know it by name (site name, node hostname), which is "
                    "the common case. The UI looks up the id itself. Give the exact name as "
                    "shown, not a guess."
                ),
            },
            "view": {
                "type": "string",
                "enum": [
                    "overview",
                    "desired_config",
                    "observed_config",
                    "config_drift",
                    "config_history",
                    "hardware",
                    "lldp",
                ],
                "description": (
                    "Optional part of node_detail to open: desired_config (what ACE-X intends), "
                    "observed_config (the latest snapshot from the device), config_drift (desired "
                    "against observed), config_history (snapshots over time), hardware, lldp "
                    "(neighbours) or overview."
                ),
            },
            "label": {
                "type": "string",
                "description": "Short link text for the button, e.g. 'Open node SW-CORE-1'.",
            },
        },
        "required": ["page", "label"],
    },
)

#: Commits the model to an approach before acting. The steps become a
#: checklist in the UI that the following tool calls tick off. Planning also
#: improves the work: naming the lookups up front is what turns "this might
#: affect downstream devices" into actually checking each neighbour.
PLAN_TOOL = ToolSpec(
    name="plan",
    description=(
        "State the lookups you are about to make, before making them. Call this FIRST "
        "whenever answering will take more than one tool call — for example a "
        "configuration change whose impact depends on other devices, where you need to "
        "work out which neighbours to check and then check each one. Listing the steps "
        "is how you commit to verifying something instead of speculating about it. "
        "The steps are shown to the user as a checklist which ticks off as you go, so "
        "do not repeat the plan in your reply text. Skip this tool for anything a "
        "single lookup answers."
    ),
    parameters={
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "One short line naming what you are trying to establish.",
            },
            "steps": {
                "type": "array",
                "description": (
                    "The steps, in the order you will do them. Be concrete: name the "
                    "device, port or snapshot each step concerns rather than writing "
                    "'check the neighbours'. If a step depends on what an earlier step "
                    "returns, say so in its description."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "What this step establishes, in a few words.",
                        },
                        "tool": {
                            "type": "string",
                            "description": (
                                "The tool you intend to use for this step, if you already "
                                "know which one. Use the exact tool name."
                            ),
                        },
                    },
                    "required": ["description"],
                },
            },
        },
        "required": ["steps"],
    },
)

#: Tools implemented in-process. Never forwarded to MCP, so they work even
#: when MCP is unconfigured or unreachable.
LOCAL_TOOLS: dict[str, ToolSpec] = {tool.name: tool for tool in (NAVIGATE_TOOL, PLAN_TOOL)}

#: Which local tools each task is offered. `navigate_to` is a web-UI affordance
#: and has no meaning in an analysis; planning helps both.
CHAT_LOCAL_TOOLS = ("plan", "navigate_to")
ANALYSIS_LOCAL_TOOLS = ("plan",)


class Toolbox:
    """The tools of one request and how to run a call to each."""

    def __init__(self, local: tuple[str, ...], mcp: Client | None = None, mcp_tools: list | None = None):
        self.mcp = mcp
        self.specs = [self.from_mcp(tool) for tool in mcp_tools or []] + [LOCAL_TOOLS[name] for name in local]

    @staticmethod
    def from_mcp(tool) -> ToolSpec:
        """MCP calls the JSON schema `inputSchema`; providers call it `parameters`."""
        return ToolSpec(tool.name, tool.description or "", tool.inputSchema or {"type": "object", "properties": {}})

    async def run(self, call: ToolCall):
        """Run one call. Yields UI events, and the ToolResult for the model last."""
        if call.arguments is None:
            yield ToolResult(call.id, call.name, self.encode({"error": "arguments were not a valid JSON object"}))
            return

        if call.name == "navigate_to":
            yield NavigateEvent(call.arguments)
            yield ToolResult(
                call.id,
                call.name,
                self.encode(
                    {
                        "status": "shown_to_user",
                        "note": (
                            "A link to this page is already shown to the user in the UI. Don't repeat "
                            "the raw page/id/path in your reply — just briefly confirm in one short sentence."
                        ),
                    }
                ),
            )
            return

        if call.name == "plan":
            steps = [step for step in (call.arguments.get("steps") or []) if isinstance(step, dict)]
            yield PlanEvent(call.arguments.get("goal"), steps)
            yield ToolResult(
                call.id,
                call.name,
                self.encode(
                    {
                        "status": "shown_to_user",
                        "note": (
                            "The plan is now a checklist in the UI. Carry out step one; the checklist "
                            "ticks off as you call each tool. Don't restate the plan in your reply — "
                            "report what you found. If a lookup changes the picture, follow the new "
                            "lead rather than the original list."
                        ),
                    }
                ),
            )
            return

        if self.mcp is None:
            yield ToolCallEvent(call.name, "error", "MCP tool server unavailable")
            yield ToolResult(call.id, call.name, self.encode({"error": "MCP tool server unavailable"}))
            return

        yield ToolCallEvent(call.name, "running")
        try:
            result = await self.mcp.call_tool(call.name, arguments=call.arguments)
        except Exception as exc:
            yield ToolCallEvent(call.name, "error", str(exc))
            yield ToolResult(call.id, call.name, self.encode({"error": str(exc)}))
            return
        text = "".join(c.text for c in result.content if hasattr(c, "text")).strip()
        try:
            output = json.loads(text)
        except json.JSONDecodeError:
            output = text
        yield ToolCallEvent(call.name, "ok")
        yield ToolResult(call.id, call.name, self.encode(output))

    @staticmethod
    def encode(value) -> str:
        return json.dumps(value)
