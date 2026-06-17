# Harness Blueprint — <AGENT NAME>

> Fill every section. Delete the guidance in angle brackets. A blueprint is done
> when someone else could build the agent from it without asking you questions.

## 0. One-liner
<What this agent does, in one sentence the user would recognize.>

## 1. Goal & success definition
- **Objective:** <the outcome>
- **Done looks like:** <observable success criteria — becomes the eval north star>
- **Explicit non-goals:** <what it must NOT try to do>

## 2. Operating context
- **Trigger(s):** <chat / API / cron / webhook / event>
- **Session shape:** <one-shot | multi-turn | long-running across sessions>
- **Inputs:** <what arrives, in what form>
- **Environment / systems it touches:** <files, APIs, DB, browser, code, MCPs>
- **Constraints:** <latency, cost ceiling, throughput, privacy/compliance, runtime>
- **Stakes:** <cost of a wrong action; reversibility>

## 3. Architecture verdict (with rationale)
- **Ladder 1 (need an agent?):** <rung chosen> — because <…>
- **Ladder 2 (single vs multi):** <verdict> — boxes checked: <…>
- **Ladder 3 (tiering):** orchestrate=<tier/role>, workers=<tier>, classify=<tier>
- **Ladder 4 (long-running?):** <yes/no + pattern>
- **Topology diagram:**
```
<ASCII diagram of the control flow / agent topology>
```

## 4. Control loop
- **Phases:** gather → act → verify → repeat
- **Stopping conditions:** <task-complete signal | max_iterations=N | budget>
- **Human checkpoints:** <where & why>
- **Interruption/resume:** <how state is checkpointed and resumed>

## 5. System prompt(s)
> Keep at the "right altitude." Store the real prompt in `prompts/` and reference
> it here. Include the full text for review.

```
<full system prompt — role, background, instructions, tool guidance,
 output contract, guardrails, effort-scaling heuristics>
```

## 6. Tools (ACI)
> One row per tool; attach a full spec per `tool-spec.template.md` for each.

| Tool | Purpose | Inputs | Output (shape, token bound) | Side-effect class |
|---|---|---|---|---|
| <name> | <one line> | <params> | <high-signal fields; concise/detailed> | read/write/destructive |

## 7. Context & memory strategy
- **Up-front context:** <what & why>
- **Just-in-time retrieval:** <mechanism: agentic search / embeddings / hybrid>
- **Token budget:** <per-step / per-task budget>
- **Compaction policy:** <when & what to keep/drop; tool-result clearing>
- **Memory:** <what persists, where, how it's read back>

## 8. Orchestration (if multi-agent / sub-agents)
- **Topology:** <orchestrator-workers | manager | decentralized>
- **Delegation contract (per sub-agent):** objective / output format / tools &
  sources / boundaries
- **Result return:** <condensed summaries | artifacts-by-reference>
- **Read/write split:** <what's parallel reading vs. single-thread writing>

## 9. Verification
| Output to check | Method (rules/env/judge) | Failure mode it catches |
|---|---|---|
| <…> | <…> | <…> |

## 10. Guardrails & security
- **Untrusted content handling:** <…>
- **Tool privilege scopes:** <least-privilege per tool>
- **Sandboxing:** <code/tool isolation>
- **Destructive-action gates:** <approval/HITL>
- **Loop/cost bounds:** <max iterations, budget, rate limits>

## 11. Observability
- **Traced per step:** prompt, tool calls, results, tokens, latency, errors
- **Where traces go:** <sink>
- **Key dashboards/alerts:** <…>

## 12. Reliability
- **Checkpoint/resume:** <…>
- **Retry & error compaction:** <…>
- **Idempotency for side effects:** <…>
- **Deployment strategy:** <e.g., rainbow/drain for long jobs>

## 13. Evaluation suite
- **Starter dataset:** <~20 realistic cases; where stored>
- **Rubric:** <dimensions + scoring; see eval-plan.template.md>
- **Judge:** <rules / LLM-judge prompt>
- **Metrics tracked:** success rate, tokens, tool calls, errors, latency, cost
- **Held-out test set:** <…>

## 14. Cost & latency envelope
- **Per-run estimate:** <tokens × tier pricing → $; wall-clock>
- **Main cost levers:** <tiering, sub-agent count, retrieval strategy>
> ⚠ Verify current model pricing/limits before quoting numbers.

## 15. Tuning playbook
1. Watch traces; identify the **dominant** failure mode.
2. Form the **smallest** fix (usually prompt or tool description → context
   strategy → topology).
3. Re-run evals; compare on the held-out set.
4. Repeat. Record what changed and the metric delta.
- **Highest-leverage next step:** <name it>

## 16. Risk register
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| <…> | <…> | <…> | <…> |
