# Reference Harness (provider-agnostic)

A small, dependency-light, **runnable** implementation of the harness patterns in
`../reference/`. It exists so the Harness Architect can hand you working code, not
just a design — and so you can verify the patterns yourself in seconds.

> **Zero dependencies to run.** The core + tests + examples run on the Python
> standard library against a built-in `MockProvider`. No API keys, no network.
> Add a real provider only when you're ready to go live.

## Layout

```
scaffold/
  harness/            # the runtime
    providers.py      #   provider-agnostic LLM interface + Mock/Anthropic/OpenAI
    tools.py          #   tool registry, schema validation, actionable errors, side-effects
    context.py        #   token budget, compaction, tool-result clearing
    memory.py         #   file-backed notes / progress / structured task list
    verify.py         #   rule-based + LLM-as-judge verification
    observability.py  #   structured tracing + token/cost accounting
    config.py         #   tiered model config (frontier/balanced/fast)
    loop.py           #   the single-agent loop: gather -> act -> verify -> repeat
    subagents.py      #   orchestrator: parallel READ workers + single-thread synthesis
  evals/              # evaluation harness
    runner.py         #   run over a dataset, grade, aggregate metrics, report
    rubric.py         #   weighted LLM-judge rubric
    datasets/         #   example_tasks.jsonl (starter set)
  examples/
    run_single_agent.py   # the common case (tiered single agent + eval)
    run_multi_agent.py    # the justified multi-agent case
  tests/              # unittest suite (offline, deterministic)
```

## Run it

```bash
cd scaffold

# examples (offline)
python examples/run_single_agent.py
python examples/run_multi_agent.py

# tests
python -m unittest discover -s tests -v
```

## Map to the principles

| Principle (see ../reference) | Where it lives |
|---|---|
| Loop = gather → act → verify → repeat | `harness/loop.py` |
| Context is a finite budget; compaction; tool-result clearing | `harness/context.py` |
| Tools as a product: validation, actionable errors, token bounds, side-effects | `harness/tools.py` |
| Verification multiplies reliability (rules → judge) | `harness/verify.py` |
| Read parallel, write single-threaded | `harness/subagents.py` |
| Tier by capability per step | `harness/config.py`, `tier=` on `AgentLoop` |
| Memory / note-taking / structured task list (long-running) | `harness/memory.py` |
| Observability / token+cost accounting | `harness/observability.py` |
| Eval from day one: ~20 cases, outcome-judged, held-out split | `evals/` |

## Swap in a real provider

The harness only depends on the `LLMProvider` interface. To go live:

```python
from harness.providers import AnthropicProvider   # or OpenAIProvider, or your own
from harness import AgentLoop, HarnessConfig, ModelTier, ToolRegistry

provider = AnthropicProvider()        # reads ANTHROPIC_API_KEY
config = HarnessConfig(models={
    ModelTier.FRONTIER: "<current-frontier-model>",   # ⚠ verify current model names
    ModelTier.BALANCED: "<current-balanced-model>",
    ModelTier.FAST:     "<current-fast-model>",
}, trace_path="trace.jsonl")
loop = AgentLoop(provider, system_prompt="...", registry=ToolRegistry([...]), config=config)
print(loop.run("your task").output)
```

Implementing your own provider is ~20 lines: subclass `LLMProvider` and implement
`complete(messages, *, system, tools, model, temperature, max_tokens) -> LLMResponse`.

## Dependencies

- **Core / tests / examples:** none (Python ≥ 3.10 standard library).
- **Real providers (optional):** `anthropic` and/or `openai` (see `requirements.txt`).
