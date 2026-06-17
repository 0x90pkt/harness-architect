"""
Provider-agnostic LLM interface.

A harness must not be married to one model vendor. Everything in this file is the
thin contract between the loop and *some* model. Adapters translate that contract
to a concrete API. The MockProvider lets the entire harness + eval suite run
offline, deterministically, with zero API keys — which is also exactly what you
want for fast, cheap tests.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# --------------------------------------------------------------------------- #
# Core message types (the portable contract)
# --------------------------------------------------------------------------- #

@dataclass
class ToolCall:
    """A request from the model to run a tool. `arguments` is already parsed."""
    id: str
    name: str
    arguments: dict


@dataclass
class Message:
    """
    A single context entry. `role` is one of: system, user, assistant, tool.
    For assistant messages that call tools, `tool_calls` is populated.
    For tool-result messages, `tool_call_id` links back to the call.
    """
    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None

    def short(self, n: int = 80) -> str:
        c = self.content.replace("\n", " ")
        return c[:n] + ("…" if len(c) > n else "")


@dataclass
class LLMResponse:
    """What a provider returns for one completion."""
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    # token usage: {"input": int, "output": int}
    usage: dict = field(default_factory=lambda: {"input": 0, "output": 0})
    model: str = ""

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


def estimate_tokens(text: str) -> int:
    """
    Rough offline token estimate (~4 chars/token). Real providers report exact
    usage; this is only for budgeting/metrics when running on the mock.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


# --------------------------------------------------------------------------- #
# Provider interface
# --------------------------------------------------------------------------- #

class LLMProvider(ABC):
    """Implement `complete` to plug any model into the harness."""

    name: str = "abstract"

    @abstractmethod
    def complete(
        self,
        messages: list[Message],
        *,
        system: str = "",
        tools: Optional[list[dict]] = None,
        model: str = "",
        temperature: float = 1.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        ...


# --------------------------------------------------------------------------- #
# MockProvider — deterministic, offline, scriptable
# --------------------------------------------------------------------------- #

Policy = Callable[[list["Message"], dict], LLMResponse]


class MockProvider(LLMProvider):
    """
    A deterministic provider driven by a `policy` function:

        policy(messages, meta) -> LLMResponse

    `meta` carries {"system", "tools", "model", "call_index"} so policies can
    branch on what's been said so far. This is how the examples and tests
    simulate real agent behavior without a network call.

    If no policy is given, it echoes a trivial final answer (useful as a stub).
    """

    name = "mock"

    def __init__(self, policy: Optional[Policy] = None):
        self.policy = policy
        self._calls = 0

    def complete(
        self,
        messages: list[Message],
        *,
        system: str = "",
        tools: Optional[list[dict]] = None,
        model: str = "mock-model",
        temperature: float = 1.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        meta = {
            "system": system,
            "tools": tools or [],
            "model": model,
            "call_index": self._calls,
        }
        self._calls += 1
        if self.policy is None:
            text = "Done."
            return LLMResponse(
                text=text,
                usage={"input": _count(messages, system), "output": estimate_tokens(text)},
                model=model,
            )
        resp = self.policy(messages, meta)
        # Fill in usage if the policy didn't.
        if resp.usage == {"input": 0, "output": 0}:
            out = resp.text or json.dumps([tc.arguments for tc in resp.tool_calls])
            resp.usage = {"input": _count(messages, system), "output": estimate_tokens(out)}
        if not resp.model:
            resp.model = model
        return resp

    @staticmethod
    def scripted(responses: list[LLMResponse]) -> "MockProvider":
        """Return responses in fixed order (round-robins the last one if exhausted)."""
        seq = list(responses)

        def policy(_messages, meta):
            i = min(meta["call_index"], len(seq) - 1)
            return seq[i]

        return MockProvider(policy)


def _count(messages: list[Message], system: str) -> int:
    total = estimate_tokens(system)
    for m in messages:
        total += estimate_tokens(m.content)
        for tc in m.tool_calls:
            total += estimate_tokens(json.dumps(tc.arguments))
    return total


# --------------------------------------------------------------------------- #
# Real adapters (lazily imported; not exercised by the offline tests)
# --------------------------------------------------------------------------- #

class AnthropicProvider(LLMProvider):
    """
    Adapter for the Anthropic Messages API. Requires `pip install anthropic` and
    ANTHROPIC_API_KEY. Maps the portable contract to/from Anthropic's shape.
    """

    name = "anthropic"

    def __init__(self, api_key: Optional[str] = None):
        try:
            import anthropic  # noqa: F401
        except ImportError as e:  # pragma: no cover - integration path
            raise ImportError(
                "AnthropicProvider needs the 'anthropic' package: pip install anthropic"
            ) from e
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(self, messages, *, system="", tools=None, model="",
                 temperature=1.0, max_tokens=4096) -> LLMResponse:  # pragma: no cover
        api_msgs = _to_anthropic_messages(messages)
        api_tools = [
            {"name": t["name"], "description": t.get("description", ""),
             "input_schema": t.get("parameters", {"type": "object", "properties": {}})}
            for t in (tools or [])
        ]
        kwargs: dict[str, Any] = dict(model=model, system=system, messages=api_msgs,
                                      max_tokens=max_tokens, temperature=temperature)
        if api_tools:
            kwargs["tools"] = api_tools
        resp = self._client.messages.create(**kwargs)
        text, calls = "", []
        for block in resp.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))
        usage = {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens}
        return LLMResponse(text=text, tool_calls=calls, usage=usage, model=model)


class OpenAIProvider(LLMProvider):
    """
    Adapter for the OpenAI Chat Completions API. Requires `pip install openai`
    and OPENAI_API_KEY.
    """

    name = "openai"

    def __init__(self, api_key: Optional[str] = None):
        try:
            import openai  # noqa: F401
        except ImportError as e:  # pragma: no cover - integration path
            raise ImportError(
                "OpenAIProvider needs the 'openai' package: pip install openai"
            ) from e
        import openai
        self._client = openai.OpenAI(api_key=api_key)

    def complete(self, messages, *, system="", tools=None, model="",
                 temperature=1.0, max_tokens=4096) -> LLMResponse:  # pragma: no cover
        api_msgs = _to_openai_messages(messages, system)
        api_tools = [
            {"type": "function",
             "function": {"name": t["name"], "description": t.get("description", ""),
                          "parameters": t.get("parameters", {"type": "object", "properties": {}})}}
            for t in (tools or [])
        ]
        kwargs: dict[str, Any] = dict(model=model, messages=api_msgs,
                                      max_tokens=max_tokens, temperature=temperature)
        if api_tools:
            kwargs["tools"] = api_tools
        resp = self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0].message
        calls = []
        for tc in (choice.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        usage = {"input": resp.usage.prompt_tokens, "output": resp.usage.completion_tokens}
        return LLMResponse(text=choice.content or "", tool_calls=calls, usage=usage, model=model)


def _to_anthropic_messages(messages: list[Message]) -> list[dict]:  # pragma: no cover
    out: list[dict] = []
    for m in messages:
        if m.role == "assistant" and m.tool_calls:
            content = ([{"type": "text", "text": m.content}] if m.content else []) + [
                {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments}
                for tc in m.tool_calls
            ]
            out.append({"role": "assistant", "content": content})
        elif m.role == "tool":
            out.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}
            ]})
        else:
            out.append({"role": m.role, "content": m.content})
    return out


def _to_openai_messages(messages: list[Message], system: str) -> list[dict]:  # pragma: no cover
    out: list[dict] = []
    if system:
        out.append({"role": "system", "content": system})
    for m in messages:
        if m.role == "assistant" and m.tool_calls:
            out.append({"role": "assistant", "content": m.content or None,
                        "tool_calls": [
                            {"id": tc.id, "type": "function",
                             "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
                            for tc in m.tool_calls]})
        elif m.role == "tool":
            out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
        else:
            out.append({"role": m.role, "content": m.content})
    return out
