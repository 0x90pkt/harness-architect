# Decision Rules

Explicit, walkable decision ladders for the highest-leverage architecture
choices. The Architect outputs a verdict for each ladder, with the rationale.
These encode the evidence in `harness-engineering-principles.md`.

---

## Ladder 1 — Do you even need an agent?

Climb only as high as the task forces you. Stop at the first rung that works.

```
Rung 0: Single augmented LLM call (prompt + retrieval + maybe one tool)
        → Use when the task is one well-scoped transformation/answer.

Rung 1: Workflow — fixed code path orchestrating LLM calls:
        • Prompt chaining     → cleanly decomposes into fixed sequential steps
        • Routing             → distinct input categories handled separately
        • Parallelization     → independent subtasks, or voting for confidence
        • Orchestrator-workers→ subtasks can't be predicted in advance
        • Evaluator-optimizer → clear criteria + iterative refinement helps
        → Use when steps are predictable; you want determinism, lower cost,
          and easy debugging.

Rung 2: Single agent in a loop (gather → act → verify → repeat)
        → Use when step count is unpredictable and the model must decide the
          path dynamically using tools, with some trust in its decisions.

Rung 3: Tiered single agent (one loop, multiple model tiers + sub-agents
        for context isolation)
        → Use when one agent is right but some steps are cheap/parallel reads
          or need a stronger model.

Rung 4: Multi-agent (orchestrator-worker or manager/decentralized)
        → Use ONLY when Ladder 2 says yes.
```

**Heuristic:** if you can write the control flow as ordinary code with a few LLM
calls inside it, do that. "The best agents are mostly software with LLM steps at
the right points." Going to a full agent is a real cost in latency, $, and
predictability — pay it only for genuine open-endedness.

---

## Ladder 2 — Single agent vs. multi-agent

Default: **single agent.** Recommend multi-agent only if **every** box is checked:

- [ ] **Decomposable into independent parallel threads** (not a tightly coupled,
      sequential, or shared-state task).
- [ ] **Read/research-heavy, not write-heavy.** (Reading parallelizes; writing
      creates merge/coherence conflicts. Keep synthesis single-threaded.)
- [ ] **Exceeds a single context window** or needs **many complex tools** that
      benefit from isolated sub-contexts.
- [ ] **High enough value** to justify ~10–15× the token cost of a single chat,
      and ~4× that of a single agent.
- [ ] **Sub-tasks have clean boundaries** you can specify precisely (objective,
      output format, tools/sources, what's out of scope).

If any box is unchecked → **single agent** (optionally tiered). If you build
multi-agent, still **do the writing/synthesis in one agent**, parallelize only
the reading, and pass references (not giant payloads) between agents.

**Topology pick (if multi-agent):**

| Topology | Edges are… | Use when |
|---|---|---|
| Orchestrator-workers / Manager | tool calls from a lead to workers | Central control & synthesis; workers are interchangeable researchers/specialists |
| Decentralized / handoff | control transfers between peers | Distinct phases own the whole task in turn (e.g., triage → specialist) |

Prefer orchestrator-workers; it keeps one coherent decision-maker. Avoid free
peer-to-peer "discussion" loops — in current models they disperse decisions and
get fragile.

---

## Ladder 3 — Tiering (model + effort)

Tier by **capability needed per step**, then by **cost/latency budget**.

```
Frontier tier  → orchestration, planning, hard reasoning, final synthesis,
                 ambiguous judgment, code architecture.
Balanced tier  → routine sub-steps, worker/sub-agent execution, most tool use.
Fast/cheap tier→ classification, routing, intent detection, extraction,
                 guardrail/safety checks, simple formatting.
```

**Effort scaling (bake numbers into prompts, don't leave it to the model):**

| Task complexity | Suggested budget |
|---|---|
| Simple fact-find | 1 agent, ~3–10 tool calls |
| Direct comparison / a few facets | 2–4 sub-agents, ~10–15 calls each |
| Complex, open-ended | 10+ sub-agents, clearly divided responsibilities |

Always pair tiering with a **cost & latency estimate** in the blueprint. Tiering
is the primary lever for hitting a budget without gutting capability.

> ⚠ Name current models only after verifying them by search. Express the design
> in tiers/roles so it survives the next model release.

---

## Ladder 4 — Long-running (multi-session) or not?

```
Does the task reliably finish within ONE context window?
  YES → standard single loop with compaction as a safety net.
  NO  → use the two-phase long-running pattern:

    Initializer (first session, special prompt):
      • write a STRUCTURED task/feature list (prefer JSON; mark each not-done)
      • write an env setup/run script (e.g., init.sh)
      • write a progress log file
      • make an initial version-control commit
      • lay foundations for ALL features, not just the first

    Worker (every later session):
      • get bearings: check dir, read progress log + VCS history, read task list
      • run a quick end-to-end smoke test of current state; fix if broken
      • pick the HIGHEST-PRIORITY unfinished item; do ONLY that
      • self-verify end-to-end before marking it done
      • leave a clean, mergeable state: commit + update progress log
```

This directly counters the four long-running failure modes (premature "done,"
buggy/undocumented hand-offs, unverified completion, wasted re-orientation).

---

## Ladder 5 — Context strategy

```
Is the relevant data small & stable enough to load up front?
  YES → load it up front (a brief / CLAUDE.md-style preamble).
  NO  → just-in-time agentic retrieval (give file/URL/query identifiers + tools).
        Add semantic/embedding search ONLY if you need speed AND can maintain it.
HYBRID is the common best answer: small brief up front + JIT retrieval for the rest.

Will the run exceed the window?
  → add compaction (summarize near the limit) + tool-result clearing
  → add structured note-taking / external memory for cross-session state
  → consider read-only sub-agents to isolate large exploratory context
```

---

## Ladder 6 — Verification design

Pick the **cheapest sufficient** check for each output, layered:

```
1. Rules / deterministic   → schema validation, type checks, linters, unit tests,
                             compilers, business-rule assertions.  (Prefer these.)
2. Environment ground truth→ run it, query it, diff it, take a screenshot, hit
                             the real endpoint.  (Truth beats opinion.)
3. LLM-as-judge            → only for fuzzy criteria (tone, completeness,
                             helpfulness). Single judge, rubric, 0–1 + pass/fail.
                             Accept latency/cost; don't over-trust.
```

Every verification check should map to a **specific failure mode** you're worried
about. If you can't name the failure it catches, you probably don't need it.

---

## Ladder 7 — Human-in-the-loop placement

Insert a human checkpoint when **any** is true: the action is destructive or
irreversible; the cost of error is high; the agent's confidence/verification is
weak; or policy/compliance requires sign-off. Implement HITL as a **tool call**
(the agent requests approval) so it composes with the loop and is traceable.
Otherwise, prefer autonomy with strong verification + bounded blast radius.
