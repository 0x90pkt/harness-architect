"""
Orchestrator-worker multi-agent pattern — done the safe way.

The single most important rule (from the multi-agent debate) is encoded here:
**reading parallelizes; writing does not.** So this orchestrator:

  1. Plans / accepts a set of independent READ subtasks.
  2. Runs sub-agents IN PARALLEL, each with its own isolated context window and a
     crisp delegation contract (objective + output format + boundaries).
  3. Each sub-agent returns only a CONDENSED summary (token-bounded), not its
     full trace — large artifacts should be written to a store and referenced.
  4. A SINGLE synthesis agent (frontier tier) writes the final answer.

Use this only when Ladder 2 says yes: parallel, read-heavy, high-value work that
exceeds one context window.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Optional

from .config import HarnessConfig, ModelTier
from .loop import AgentLoop
from .observability import Tracer, Usage
from .providers import LLMProvider
from .tools import ToolRegistry


@dataclass
class SubAgentSpec:
    """A delegation contract for one worker. Vague specs are the #1 failure mode."""
    objective: str
    output_format: str = "A concise summary (<= 200 words) of the key findings."
    boundaries: str = "Stay strictly within your objective; do not duplicate others' work."
    tier: ModelTier = ModelTier.BALANCED

    def to_prompt(self, shared_context: str) -> str:
        return (
            f"{shared_context}\n\n"
            f"YOUR OBJECTIVE: {self.objective}\n"
            f"OUTPUT FORMAT: {self.output_format}\n"
            f"BOUNDARIES: {self.boundaries}\n"
            "Return only the requested output."
        )


@dataclass
class OrchestratorResult:
    output: str
    sub_results: list[str]
    usage: Usage
    success: bool = True


class Orchestrator:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        worker_system_prompt: str,
        synthesis_system_prompt: str,
        registry: Optional[ToolRegistry] = None,
        config: Optional[HarnessConfig] = None,
        max_parallel: int = 5,
        tracer: Optional[Tracer] = None,
    ):
        self.provider = provider
        self.worker_system_prompt = worker_system_prompt
        self.synthesis_system_prompt = synthesis_system_prompt
        self.registry = registry or ToolRegistry()
        self.config = config or HarnessConfig()
        self.max_parallel = max_parallel
        self.tracer = tracer or Tracer(path=self.config.trace_path)

    def run(self, task: str, subagents: list[SubAgentSpec],
            shared_context: Optional[str] = None) -> OrchestratorResult:
        """
        shared_context is given to EVERY sub-agent (share context!). If omitted,
        the top-level task is shared so workers can interpret their slice.
        """
        shared = shared_context or f"OVERALL TASK (shared with all workers): {task}"
        self.tracer.event("orchestrate_start", task=task[:200], n_subagents=len(subagents))
        total = Usage()

        # ---- parallel READ phase ----
        results: list[tuple[int, str, Usage]] = []

        def _run_worker(idx: int, spec: SubAgentSpec):
            loop = AgentLoop(
                self.provider,
                self.worker_system_prompt,
                registry=self.registry,
                config=self.config,
                tier=spec.tier,
                tracer=Tracer(),  # isolated trace per worker (clean context)
            )
            r = loop.run(spec.to_prompt(shared))
            return idx, r.output, r.usage

        with ThreadPoolExecutor(max_workers=self.max_parallel) as pool:
            futs = [pool.submit(_run_worker, i, s) for i, s in enumerate(subagents)]
            for fut in as_completed(futs):
                idx, out, u = fut.result()
                results.append((idx, out, u))
                total.merge(u)
                self.tracer.event("subagent_done", index=idx, summary=out[:200],
                                  tokens=u.as_dict())

        results.sort(key=lambda x: x[0])
        sub_outputs = [out for _, out, _ in results]

        # ---- single-threaded WRITE/synthesis phase ----
        joined = "\n\n".join(f"[Finding {i+1}]\n{o}" for i, o in enumerate(sub_outputs))
        synth_loop = AgentLoop(
            self.provider,
            self.synthesis_system_prompt,
            registry=ToolRegistry(),  # synthesis usually needs no tools
            config=self.config,
            tier=ModelTier.FRONTIER,
            tracer=self.tracer,
        )
        synth_task = (
            f"TASK: {task}\n\n"
            f"You have these findings from parallel research workers:\n\n{joined}\n\n"
            "Synthesize a single, coherent answer. Resolve conflicts, remove "
            "duplication, and cite which finding supports each claim."
        )
        synth = synth_loop.run(synth_task)
        total.merge(synth.usage)
        self.tracer.event("orchestrate_end", usage=total.as_dict())
        return OrchestratorResult(
            output=synth.output,
            sub_results=sub_outputs,
            usage=total,
            success=synth.success,
        )
