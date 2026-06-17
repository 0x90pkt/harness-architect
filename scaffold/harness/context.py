"""
Context management — treat the window as a finite attention budget.

Implements three of the levers from the reference:
  - token budgeting (know how full the window is)
  - tool-result clearing (the lightest-touch compaction: drop raw bytes of old
    tool results once they're deep in history)
  - compaction (summarize older turns into one message, keep recent ones verbatim)

The ContextManager owns the running message list. `render()` returns the messages
to actually send to the model on the next turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .providers import LLMProvider, Message, estimate_tokens


@dataclass
class ContextManager:
    token_budget: int = 100_000
    # when used tokens exceed this fraction of the budget, compaction triggers
    compaction_threshold: float = 0.8
    # keep this many of the most recent messages verbatim during compaction
    keep_recent: int = 6
    # after this many tool results, clear the raw content of older ones
    clear_tool_results_after: int = 8
    messages: list[Message] = field(default_factory=list)
    _summary: Optional[str] = None

    def add(self, message: Message) -> None:
        self.messages.append(message)

    def used_tokens(self) -> int:
        total = estimate_tokens(self._summary or "")
        for m in self.messages:
            total += estimate_tokens(m.content)
            for tc in m.tool_calls:
                total += estimate_tokens(str(tc.arguments))
        return total

    def fraction_used(self) -> float:
        return self.used_tokens() / max(1, self.token_budget)

    def should_compact(self) -> bool:
        return self.fraction_used() >= self.compaction_threshold

    def clear_old_tool_results(self) -> int:
        """
        Replace the content of all-but-the-last-N tool results with a placeholder.
        Returns how many were cleared. Cheap and safe: keeps the structure, frees
        the tokens.
        """
        idxs = [i for i, m in enumerate(self.messages) if m.role == "tool"]
        to_clear = idxs[:-self.clear_tool_results_after] if len(idxs) > self.clear_tool_results_after else []
        for i in to_clear:
            if not self.messages[i].content.startswith("[cleared"):
                original = estimate_tokens(self.messages[i].content)
                self.messages[i].content = f"[cleared tool result — freed ~{original} tokens]"
        return len(to_clear)

    def compact(self, provider: LLMProvider, *, system: str = "", model: str = "") -> None:
        """
        Summarize older messages into a single high-fidelity note and drop them,
        keeping the most recent `keep_recent` messages verbatim. Tune the prompt
        for recall first, then precision.
        """
        if len(self.messages) <= self.keep_recent:
            return
        old = self.messages[:-self.keep_recent]
        recent = self.messages[-self.keep_recent:]
        transcript = _render_for_summary(old)
        prompt = (
            "Summarize the conversation below into a compact, high-fidelity note "
            "for continuing the task. PRESERVE: goals, decisions made, unresolved "
            "problems, key facts/IDs, and current state. DISCARD: redundant tool "
            "output and chit-chat. Be thorough on anything that affects future "
            "steps.\n\n" + transcript
        )
        resp = provider.complete([Message("user", prompt)], system=system, model=model)
        merged = (self._summary + "\n\n" if self._summary else "") + resp.text.strip()
        self._summary = merged
        self.messages = recent

    def render(self) -> list[Message]:
        """Messages to send next turn (summary prepended as a system-ish note)."""
        out: list[Message] = []
        if self._summary:
            out.append(Message("user", f"[Context summary of earlier work]\n{self._summary}"))
        out.extend(self.messages)
        return out


def _render_for_summary(messages: list[Message]) -> str:
    lines = []
    for m in messages:
        if m.tool_calls:
            calls = "; ".join(f"{tc.name}({tc.arguments})" for tc in m.tool_calls)
            lines.append(f"{m.role} -> tool_call: {calls}")
        else:
            lines.append(f"{m.role}: {m.content}")
    return "\n".join(lines)
