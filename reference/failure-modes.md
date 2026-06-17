# Failure-Mode Catalog & Pre-Handoff Checklist

A catalog of the failure modes that recur in real agent harnesses, each paired
with the harness-level fix. The Architect uses the bottom checklist before
declaring any design done. Sources are in `harness-engineering-principles.md`.

---

## A. Loop & control-flow failures

| # | Failure mode | Symptom | Harness fix |
|---|---|---|---|
| A1 | **Premature "done"** | Agent declares the task complete before it is | Explicit task/feature list as ground truth; require end-to-end self-verification before marking done |
| A2 | **Runaway loop** | Agent never stops; burns budget | Hard max-iterations, token/cost ceiling, and a "no-progress" detector |
| A3 | **One-shotting** | Tries to do everything in one turn; runs out of context mid-task | Force incremental progress (one item at a time); leave clean state each turn |
| A4 | **Thrashing / oscillation** | Repeats the same failing action | Compact the error into context with guidance; after N retries, escalate or change strategy |
| A5 | **No verification phase** | Output looks plausible but is wrong | Add a real verify phase (rules → ground truth → judge); never skip it |

## B. Context failures

| # | Failure mode | Symptom | Harness fix |
|---|---|---|---|
| B1 | **Context overflow** | Hits window limit; truncation loses key info | Compaction near the limit (recall-first prompt); tool-result clearing |
| B2 | **Context rot** | Recall/quality degrades in a long window | Keep the window tight; offload to memory; isolate exploration in sub-agents |
| B3 | **Lost decisions across sessions** | Next session re-derives or contradicts prior work | Structured note-taking / progress file + version-control history read on startup |
| B4 | **Stale/irrelevant context** | Acts on outdated pre-loaded data | Prefer just-in-time retrieval; timestamp/metadata signals; re-fetch on demand |
| B5 | **Brute-force reading** | Loads everything, reasons token-by-token | Tools that search/filter and return only relevant slices |

## C. Tool / ACI failures

| # | Failure mode | Symptom | Harness fix |
|---|---|---|---|
| C1 | **Tool ambiguity** | Calls the wrong tool among overlapping ones | Few, sharp, non-overlapping tools; namespacing; clear "when to use vs. sibling" notes |
| C2 | **Bad parameters** | Invalid/mis-typed tool inputs | Unambiguous param names (`user_id`), strict schemas, `poka-yoke` (e.g., absolute paths), examples in description |
| C3 | **Token-bloated responses** | One tool call floods the window | Pagination/filtering/truncation with sane defaults; concise/detailed modes |
| C4 | **Opaque errors** | Agent can't recover from a tool error | Actionable error messages stating the fix, not raw tracebacks |
| C5 | **Cryptic identifiers** | Hallucinates on UUIDs/mime types | Return human-legible fields; resolve IDs to names; offer detailed mode only when needed |
| C6 | **Wrong-tool-for-the-data** | Searches the web for data that lives in Slack/DB | Give explicit tool-selection heuristics; match tools to the real data sources |

## D. Multi-agent failures

| # | Failure mode | Symptom | Harness fix |
|---|---|---|---|
| D1 | **Context starvation** | Sub-agent misreads its task | Full delegation contract: objective + output format + tools/sources + boundaries; share full traces |
| D2 | **Conflicting implicit decisions** | Parallel outputs are incoherent/incompatible | Keep writing/synthesis single-threaded; parallelize only reads |
| D3 | **Duplicated work** | Multiple sub-agents do the same thing | Crisp, non-overlapping subtask boundaries from the orchestrator |
| D4 | **Over-spawning** | Spawns too many agents for a trivial query | Effort-scaling rules in the prompt (counts tied to complexity) |
| D5 | **Game of telephone** | Detail lost passing results up the chain | Write artifacts to a store; pass lightweight references |
| D6 | **Cost blowout** | 15× token spend not justified by value | Gate multi-agent behind a value threshold; otherwise single agent |

## E. Reliability / production failures

| # | Failure mode | Symptom | Harness fix |
|---|---|---|---|
| E1 | **Compounding errors** | One bad step derails the whole run | Checkpointing + resume-from-failure; deterministic retries |
| E2 | **Undebuggable** | "It didn't find the obvious thing" and you can't see why | Full structured tracing of prompts, tool calls, results, tokens |
| E3 | **Deploy breaks in-flight agents** | Updates corrupt running long jobs | Rainbow/drain deployments; versioned state |
| E4 | **Non-idempotent side effects** | Retries double-charge / double-send | Idempotency keys; classify and guard side-effecting tools |
| E5 | **Sync bottleneck** | Whole system waits on slowest worker | Consider async orchestration when value justifies the complexity |

## F. Security failures

| # | Failure mode | Symptom | Harness fix |
|---|---|---|---|
| F1 | **Indirect prompt injection** | External content hijacks the agent's goal | Treat all external content as untrusted; isolate it from instructions; filter/monitor |
| F2 | **Tool misuse / over-privilege** | Agent takes unintended high-impact actions | Least-privilege scopes; allow-lists; classify read/write/destructive |
| F3 | **Unsandboxed execution** | Generated code touches host/network freely | Sandbox tools and code execution; constrain FS/network |
| F4 | **Ungated destructive actions** | Irreversible action with no approval | Human-in-the-loop gate for destructive/irreversible ops |
| F5 | **Memory poisoning** | Bad data persisted, then trusted later | Validate before persisting; provenance on memory; periodic review |

## G. Evaluation failures

| # | Failure mode | Symptom | Harness fix |
|---|---|---|---|
| G1 | **No evals** | Can't tell if a change helped | Start with ~20 real cases on day one |
| G2 | **Path-based grading** | Penalizes valid alternative routes | Judge outcomes/end-state, not prescribed steps |
| G3 | **Overfitting to evals** | Great on dev set, bad in prod | Hold out a test set; refresh cases from real failures |
| G4 | **Over-strict verifier** | Rejects correct answers on formatting | Tolerant matching; LLM-judge for fuzzy criteria |

---

## Pre-handoff checklist (run before declaring a harness done)

**Simplicity & fit**
- [ ] Could a simpler rung (augmented call / workflow / single agent) do this? If
      so, recommended that instead.
- [ ] Multi-agent (if used) passes every box in Ladder 2; writing stays
      single-threaded.

**The four loop phases**
- [ ] Gather: context strategy defined (up-front vs. JIT vs. hybrid; budget set).
- [ ] Act: tool set is minimal, sharp, namespaced; each tool unambiguous *to me*.
- [ ] Verify: a real verification phase exists, each check tied to a failure mode.
- [ ] Repeat: stopping conditions, max iterations, and budgets are explicit.

**Context & memory**
- [ ] Compaction / tool-result clearing planned if runs can be long.
- [ ] Cross-session state persists via notes/progress file/store and is read on
      startup.

**Tools**
- [ ] Parameters unambiguous and schema-enforced; errors are actionable.
- [ ] Responses token-bounded; concise/detailed modes where useful.

**Orchestration**
- [ ] Every actor has the context/decisions it needs (full delegation contracts).
- [ ] Large outputs passed by reference, not copied.

**Reliability & security**
- [ ] Checkpoint/resume; idempotent side effects; graceful tool-failure handling.
- [ ] External content treated as untrusted; tools least-privileged; destructive
      actions gated; loop bounded; execution sandboxed.
- [ ] Structured tracing/observability is in place.

**Evaluation & cost**
- [ ] ~20 realistic eval cases + rubric + judge + metrics (tokens, calls, errors,
      latency).
- [ ] Held-out set exists.
- [ ] Cost & latency envelope estimated and stated.

**Code**
- [ ] The provided code actually runs (against the mock provider, zero keys).
- [ ] Provider swap is documented.
- [ ] The tuning playbook names the single highest-leverage next improvement.
