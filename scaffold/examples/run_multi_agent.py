"""
Worked example #2 — orchestrator-worker multi-agent (the rarer, justified case).

A research task decomposed into independent READ subtasks run in PARALLEL, each
by a balanced-tier worker with an isolated context window and a crisp delegation
contract. A single FRONTIER synthesis step writes the final answer — because
writing does not parallelize safely.

Runs fully offline on MockProvider.

    python examples/run_multi_agent.py
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from harness import (  # noqa: E402
    HarnessConfig, MockProvider, LLMResponse, ToolCall,
    Tool, ToolRegistry, SideEffect, Orchestrator, SubAgentSpec,
)


# --- a search tool with canned corpus ------------------------------------- #
CORPUS = {
    "battery": "Solid-state batteries reached pilot production in 2025; ~2x energy density.",
    "charging": "350kW chargers are now common on highways; 10-80% in ~18 minutes.",
    "policy": "Several regions set 2035 phase-out dates for new combustion vehicles.",
}


def search(args: dict) -> str:
    q = args["query"].lower()
    hits = [v for k, v in CORPUS.items() if k in q]
    return " ".join(hits) if hits else "No results; try a broader query."


search_tool = Tool(
    name="search",
    description="Search the research corpus. Use a short, broad query first.",
    handler=search,
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    },
    side_effect=SideEffect.READ,
)


# --- mock behavior for BOTH worker and synthesis -------------------------- #
def policy(messages, meta):
    system = meta["system"].lower()

    # synthesis agent: no tools; compose a clean report from the findings
    if "synthesis" in system:
        task_msg = next((m.content for m in messages if m.role == "user"), "")
        points = [ln.split("Summary:", 1)[-1].strip()
                  for ln in task_msg.splitlines() if "Summary:" in ln]
        report = "EV technology & policy in 2025 (synthesized):\n" + \
                 "\n".join(f"- {p}" for p in points)
        return LLMResponse(text=report)

    # worker agent: search once, then return a short summary
    has_result = any(m.role == "tool" and not m.content.startswith("ERROR") for m in messages)
    if not has_result:
        objective = " ".join(m.content for m in messages if m.role == "user").lower()
        topic = next((k for k in CORPUS if k in objective), "battery")
        return LLMResponse(tool_calls=[ToolCall(id="s1", name="search",
                                                arguments={"query": topic})])
    result = next(m.content for m in messages if m.role == "tool")
    return LLMResponse(text=f"Summary: {result}")


WORKER_SYSTEM = """You are a research worker. Research ONLY your assigned objective.
Use the search tool (broad query first). Return a concise summary of findings."""

SYNTHESIS_SYSTEM = """You are the synthesis agent. Combine the workers' findings into
one coherent report. Resolve conflicts and remove duplication. (single-threaded write)"""


def main():
    provider = MockProvider(policy)
    registry = ToolRegistry([search_tool])
    config = HarnessConfig(max_iterations=6)
    orch = Orchestrator(
        provider,
        worker_system_prompt=WORKER_SYSTEM,
        synthesis_system_prompt=SYNTHESIS_SYSTEM,
        registry=registry,
        config=config,
        max_parallel=3,
    )

    task = "Summarize the state of electric-vehicle technology and policy in 2025."
    subagents = [
        SubAgentSpec(objective="EV battery technology advances"),
        SubAgentSpec(objective="EV charging infrastructure"),
        SubAgentSpec(objective="EV-related government policy"),
    ]

    result = orch.run(task, subagents)
    print("--- sub-agent findings (parallel reads) ---")
    for i, s in enumerate(result.sub_results, 1):
        print(f"  worker {i}: {s}")
    print("\n--- synthesized answer (single-threaded write) ---")
    print(result.output)
    print("\nusage:", result.usage.as_dict())
    print("note: multi-agent spends far more tokens — justify it with task value.")


if __name__ == "__main__":
    main()
