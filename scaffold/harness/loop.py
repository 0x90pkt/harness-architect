"""
The single-agent control loop: gather context -> take action -> verify -> repeat.

This is intentionally small and readable — per the field's strongest advice, an
agent is "an LLM using tools in a loop," and you should own this loop rather than
hide it inside a framework. Everything reliability-related hangs off it:
stopping conditions, budgets, tracing, compaction, verification, and approval.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from .config import HarnessConfig, ModelTier
from .context import ContextManager
from .observability import Tracer, Usage, estimate_cost
from .providers import LLMProvider, Message
from .tools import ApprovalFn, ToolRegistry
from .verify import Verifier


@dataclass
class RunResult:
    output: str
    success: bool
    iterations: int
    usage: Usage
    stop_reason: str
    cost: float = 0.0
    trace: list[dict] = field(default_factory=list)


class AgentLoop:
    """
    A reusable single-agent harness. Construct once, call `run(task)` per task.

    Parameters
    ----------
    provider      : the LLM provider (Mock/Anthropic/OpenAI/your own)
    system_prompt : the system instructions (keep at the "right altitude")
    registry      : tools available to the agent (may be empty)
    config        : bounds, tiers, budgets, safety toggles
    tier          : which model tier this loop runs on (default FRONTIER)
    verifier      : optional output verification (the reliability multiplier)
    approve       : optional approval callback for destructive tools
    tracer        : optional shared tracer (one is created if omitted)
    """

    def __init__(
        self,
        provider: LLMProvider,
        system_prompt: str,
        registry: Optional[ToolRegistry] = None,
        config: Optional[HarnessConfig] = None,
        *,
        tier: ModelTier = ModelTier.FRONTIER,
        verifier: Optional[Verifier] = None,
        approve: Optional[ApprovalFn] = None,
        tracer: Optional[Tracer] = None,
    ):
        self.provider = provider
        self.system_prompt = system_prompt
        self.registry = registry or ToolRegistry()
        self.config = config or HarnessConfig()
        self.tier = tier
        self.verifier = verifier
        self.approve = approve
        self.tracer = tracer or Tracer(path=self.config.trace_path)

    def run(self, task: str) -> RunResult:
        cfg = self.config
        model = cfg.model_for(self.tier)
        ctx = ContextManager(
            token_budget=cfg.token_budget,
            compaction_threshold=cfg.compaction_threshold,
            keep_recent=cfg.keep_recent,
        )
        ctx.add(Message("user", task))
        usage = Usage()
        tools_schema = self.registry.to_schema()
        verify_retries = 0
        self.tracer.event("run_start", task=task[:200], model=model, tier=self.tier.value)

        stop_reason = "max_iterations"
        final_output = ""

        for i in range(1, cfg.max_iterations + 1):
            # ---- budget guard (a stopping condition) ----
            if ctx.used_tokens() > cfg.token_budget:
                stop_reason = "token_budget_exceeded"
                self.tracer.event("stop", reason=stop_reason, iteration=i)
                break

            # ---- GATHER: compact/clear context if we're getting full ----
            if ctx.should_compact():
                cleared = ctx.clear_old_tool_results()
                self.tracer.event("context_clear", cleared=cleared, frac=round(ctx.fraction_used(), 3))
                if ctx.should_compact():
                    ctx.compact(self.provider, system=self.system_prompt, model=model)
                    self.tracer.event("context_compact", frac=round(ctx.fraction_used(), 3))

            # ---- call the model ----
            t0 = time.time()
            resp = self.provider.complete(
                ctx.render(),
                system=self.system_prompt,
                tools=tools_schema,
                model=model,
                temperature=cfg.temperature,
                max_tokens=cfg.max_response_tokens,
            )
            dt = time.time() - t0
            usage.add_llm(resp.usage, dt)
            self.tracer.event("llm", iteration=i, wants_tools=resp.wants_tools,
                              text=resp.text[:200], tokens=resp.usage)

            # record the assistant turn
            ctx.add(Message("assistant", resp.text, tool_calls=resp.tool_calls))

            # ---- ACT: run tools, append results ----
            if resp.wants_tools:
                for call in resp.tool_calls:
                    result = self.registry.execute(call, approve=self.approve)
                    usage.add_tool(result.is_error)
                    self.tracer.event("tool", iteration=i, name=call.name,
                                      args=call.arguments, is_error=result.is_error,
                                      result=result.content[:200])
                    ctx.add(Message("tool", result.content, tool_call_id=call.id))
                continue  # loop back: gather (with new tool results) -> act/verify

            # ---- no tool calls => candidate final answer ----
            final_output = resp.text

            # ---- VERIFY ----
            if self.verifier is not None:
                vr = self.verifier.verify(final_output, task)
                self.tracer.event("verify", iteration=i, passed=vr.passed,
                                  score=round(vr.score, 3), feedback=vr.feedback[:200])
                if not vr.passed and verify_retries < cfg.max_verify_retries:
                    verify_retries += 1
                    ctx.add(Message(
                        "user",
                        f"Your output did not pass verification.\n{vr.feedback}\n"
                        "Revise and try again.",
                    ))
                    continue
                stop_reason = "done" if vr.passed else "verification_failed"
            else:
                stop_reason = "done"

            self.tracer.event("stop", reason=stop_reason, iteration=i)
            break

        cost = estimate_cost(usage, model, cfg.price_table) if cfg.price_table else 0.0
        success = stop_reason == "done"
        self.tracer.event("run_end", success=success, stop_reason=stop_reason,
                          usage=usage.as_dict(), cost=round(cost, 4))
        return RunResult(
            output=final_output,
            success=success,
            iterations=i,
            usage=usage,
            stop_reason=stop_reason,
            cost=cost,
            trace=self.tracer.events,
        )
