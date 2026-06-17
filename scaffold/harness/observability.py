"""
Observability — structured tracing + token/cost accounting.

Agents are non-deterministic between runs; without tracing you cannot debug "it
didn't find the obvious thing." Every step appends a structured event. Usage
accumulates tokens/calls/errors so you can price runs and spot regressions.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    tool_errors: int = 0
    llm_calls: int = 0
    seconds: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add_llm(self, usage: dict, seconds: float = 0.0) -> None:
        self.input_tokens += usage.get("input", 0)
        self.output_tokens += usage.get("output", 0)
        self.llm_calls += 1
        self.seconds += seconds

    def add_tool(self, is_error: bool) -> None:
        self.tool_calls += 1
        if is_error:
            self.tool_errors += 1

    def merge(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.tool_calls += other.tool_calls
        self.tool_errors += other.tool_errors
        self.llm_calls += other.llm_calls
        self.seconds += other.seconds

    def as_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "tool_errors": self.tool_errors,
            "seconds": round(self.seconds, 3),
        }


# price table: model -> (usd_per_1M_input, usd_per_1M_output)
# ⚠ TIME-SENSITIVE: verify current prices before trusting cost numbers.
def estimate_cost(usage: Usage, model: str, price_table: dict[str, tuple[float, float]]) -> float:
    if model not in price_table:
        return 0.0
    pin, pout = price_table[model]
    return usage.input_tokens / 1_000_000 * pin + usage.output_tokens / 1_000_000 * pout


@dataclass
class Tracer:
    """Append-only structured trace. Writes JSONL if `path` is set; always keeps
    an in-memory copy for tests/inspection."""
    path: Optional[str | Path] = None
    events: list[dict] = field(default_factory=list)
    _t0: float = field(default_factory=time.time)

    def event(self, type: str, **data) -> None:
        evt = {"t": round(time.time() - self._t0, 4), "type": type, **data}
        self.events.append(evt)
        if self.path:
            with Path(self.path).open("a", encoding="utf-8") as f:
                f.write(json.dumps(evt, default=str) + "\n")

    def by_type(self, type: str) -> list[dict]:
        return [e for e in self.events if e["type"] == type]
