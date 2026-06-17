"""
Tools = the agent-computer interface (ACI).

Design rules encoded here (see ../../reference/harness-engineering-principles.md §5):
  - Few, sharp, non-overlapping tools beat many thin API wrappers.
  - Inputs are validated against a schema; bad inputs return an *actionable*
    error message (which steers the model), not a crash.
  - Responses are token-bounded (truncate with a hint on how to get more).
  - Every tool declares a side-effect class; destructive tools can require
    approval before they run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from .providers import ToolCall, estimate_tokens


class SideEffect(Enum):
    READ = "read"            # no state change
    WRITE = "write"          # reversible state change
    DESTRUCTIVE = "destructive"  # irreversible / high-impact


class ToolError(Exception):
    """Raise inside a handler to return an actionable error to the agent."""


@dataclass
class ToolResult:
    tool_call_id: str
    name: str
    content: str
    is_error: bool = False
    tokens: int = 0


@dataclass
class Tool:
    name: str
    description: str
    handler: Callable[[dict], Any]
    # JSON-schema-style parameter spec, e.g.:
    # {"type":"object","properties":{"q":{"type":"string"}},"required":["q"]}
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    side_effect: SideEffect = SideEffect.READ
    requires_approval: bool = False
    max_response_tokens: int = 4000

    def schema(self) -> dict:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


# Approval callback: given (tool, arguments) -> bool (allow?). Default: deny
# destructive actions in non-interactive contexts.
ApprovalFn = Callable[[Tool, dict], bool]


def deny_destructive(tool: Tool, args: dict) -> bool:
    return tool.side_effect is not SideEffect.DESTRUCTIVE


class ToolRegistry:
    def __init__(self, tools: Optional[list[Tool]] = None):
        self._tools: dict[str, Tool] = {}
        for t in (tools or []):
            self.register(t)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool name: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def to_schema(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]

    def execute(self, call: ToolCall, approve: Optional[ApprovalFn] = None) -> ToolResult:
        """
        Run a tool call safely. Never raises for ordinary tool failures — returns
        an error ToolResult so the agent can read it and adapt.
        """
        tool = self._tools.get(call.name)
        if tool is None:
            avail = ", ".join(sorted(self._tools)) or "(none)"
            return self._err(call, f"Unknown tool '{call.name}'. Available tools: {avail}.")

        # 1) validate inputs against the schema -> actionable error
        problem = _validate(call.arguments, tool.parameters)
        if problem:
            return self._err(call, f"Invalid arguments for '{tool.name}': {problem}")

        # 2) approval gate for destructive/approval-required tools
        if tool.requires_approval or tool.side_effect is SideEffect.DESTRUCTIVE:
            allow = (approve or deny_destructive)(tool, call.arguments)
            if not allow:
                return self._err(
                    call,
                    f"Action '{tool.name}' was not approved. It is "
                    f"{tool.side_effect.value}; a human must approve it first.",
                )

        # 3) run the handler; convert ToolError to an actionable result
        try:
            raw = tool.handler(call.arguments)
        except ToolError as e:
            return self._err(call, str(e))
        except Exception as e:  # unexpected -> still don't crash the loop
            return self._err(call, f"Tool '{tool.name}' raised {type(e).__name__}: {e}")

        content = raw if isinstance(raw, str) else _to_text(raw)
        content = _truncate(content, tool.max_response_tokens)
        return ToolResult(call.id, tool.name, content, is_error=False,
                          tokens=estimate_tokens(content))

    def _err(self, call: ToolCall, msg: str) -> ToolResult:
        return ToolResult(call.id, call.name, f"ERROR: {msg}", is_error=True,
                          tokens=estimate_tokens(msg))


# --------------------------------------------------------------------------- #
# Minimal JSON-schema validation (enough to give the model useful feedback)
# --------------------------------------------------------------------------- #

_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


def _validate(args: dict, schema: dict) -> Optional[str]:
    if not isinstance(args, dict):
        return "arguments must be an object"
    props = schema.get("properties", {})
    required = schema.get("required", [])
    for key in required:
        if key not in args:
            return f"missing required parameter '{key}'"
    for key, val in args.items():
        spec = props.get(key)
        if spec is None:
            # Unknown params are tolerated but flagged if additionalProperties is False
            if schema.get("additionalProperties") is False:
                allowed = ", ".join(props) or "(none)"
                return f"unexpected parameter '{key}'. Allowed: {allowed}"
            continue
        t = spec.get("type")
        if t and not _check_type(val, t):
            return f"parameter '{key}' must be of type {t}"
        if "enum" in spec and val not in spec["enum"]:
            return f"parameter '{key}' must be one of {spec['enum']}"
    return None


def _check_type(val: Any, t: str) -> bool:
    # bool is a subclass of int in Python; reject it for numeric types explicitly.
    if t == "integer":
        return isinstance(val, int) and not isinstance(val, bool)
    if t == "number":
        return isinstance(val, (int, float)) and not isinstance(val, bool)
    if t in _TYPES:
        return isinstance(val, _TYPES[t])
    return True  # unknown/unsupported type spec -> don't enforce


def _to_text(obj: Any) -> str:
    import json
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        return str(obj)


def _truncate(text: str, max_tokens: int) -> str:
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    head = text[:max_chars]
    return (
        head
        + f"\n\n…[truncated: response exceeded ~{max_tokens} tokens. "
        + "Use filters, pagination, or a more specific query to narrow results.]"
    )
