# Harness Architect

A toolkit whose one job is to **design, engineer, and tune production-grade agent
harnesses** from a goal. Point it at "I want an agent that does X" and it returns
a complete blueprint — control loop, system prompt, tools, context/memory
strategy, orchestration (single, tiered, or multi-agent), evaluation suite, and a
tuning plan — plus **runnable, provider-agnostic code**.

It is built to be the **base layer** under other projects: opinionated where the
evidence is strong, explicit about trade-offs, and honest when the right answer is
"don't build the complicated thing."

> The model is raw capability. The **harness** is everything around it that makes
> capability reliable. A mediocre model in an excellent harness beats an excellent
> model in a poor one — so most of the engineering lives here.

---

## What's in the box

```
harness-architect/
├── harness-architect.agent.md            # THE AGENT (full edition) — pairs with the folders below
├── harness-architect-standalone.agent.md # self-contained single-file edition (drop-in, no folders needed)
├── README.md                             # you are here
├── reference/                     # the cited evidence base it reasons from
│   ├── harness-engineering-principles.md   # deep, sourced principles
│   ├── decision-rules.md                   # the explicit decision ladders
│   └── failure-modes.md                    # failure catalog + pre-handoff checklist
├── templates/                     # fill-in skeletons it produces
│   ├── harness-blueprint.template.md
│   ├── tool-spec.template.md
│   └── eval-plan.template.md
├── examples/                      # worked blueprints (few-shot + reference)
│   ├── example-01-single-agent-tiered-support.md
│   ├── example-02-multi-agent-research.md
│   └── example-03-long-running-coding.md
└── scaffold/                      # runnable, provider-agnostic reference harness
    ├── harness/                   #   loop, tools, context, memory, verify, subagents…
    ├── evals/                     #   eval runner + rubric + starter dataset
    ├── examples/                  #   run_single_agent.py, run_multi_agent.py
    └── tests/                     #   30 offline unit tests (all green)
```

## Two editions (deployment options)

There are two agent files; pick by how portable you need the deployment to be.

| | `harness-architect.agent.md` (full) | `harness-architect-standalone.agent.md` (single-file) |
|---|---|---|
| **Drop-in** | needs the `harness-architect/` folder present | just copy the one `.md` into `.claude/agents/` |
| **Methodology** | embedded | embedded |
| **Deep reference / templates / examples** | read from sibling folders | inlined (condensed) |
| **Runnable scaffold code** | adapts the tested `scaffold/` | **generates** equivalent code on demand |
| **If the toolkit folder is also present** | uses it | detects and uses it (graceful upgrade) |
| **Best for** | a stable home (repo, committed toolkit) | portability across many projects / quick installs |

The standalone edition has a **distinct agent name** (`harness-architect-standalone`),
so you can have both registered at once without a name clash. It does one quick
check for the optional toolkit folder and otherwise proceeds entirely from itself —
no dead-link thrashing.

## Simple start (no technical background needed)

Think of this as **an expert you talk to that designs AI agents for you.** You
describe the helper you wish you had — *"an agent that sorts my inbox and drafts
replies"* — it asks a few quick questions, and it hands back a clear plan plus
ready-to-use starter files. You don't need to write any code.

**Step 1 — Put one piece in place (one-time, ~2 minutes).**
Choose the option that fits, then add it where your AI assistant keeps its
specialized helpers (its "agents" folder). If you're not sure where that is, ask
whoever set up your AI tools — it's a quick, one-time step.

- **Easiest — the single file.** Use `harness-architect-standalone.agent.md`. Copy
  that one file in. Nothing else needed.
- **Most complete — the whole folder.** Copy the entire `harness-architect` folder
  in. Same setup, but it can also hand you tested, ready-to-run starter code.

**Step 2 — Just talk to it.** Start a chat and describe what you want, in your own
words. For example:

> "Design an agent that reads our incoming support emails, drafts a reply, and
> flags anything about refunds for a person to approve first."

**Step 3 — Answer a few quick questions.** It asks a handful of plain-English
questions (what "done" looks like, how cautious it should be, what it's allowed to
do). Answer however you'd explain it to a coworker.

**Step 4 — Get your blueprint.** It produces an easy-to-read plan (`BLUEPRINT.md`)
that spells out exactly how the agent works, plus the starter files. Hand those to
whoever builds your tools — or come right back and ask it to explain or change
anything.

**Which option should I pick?**

- Want the simplest possible install? → the **single file**.
- Want the most complete result (including ready-to-run code)? → the **whole folder**.
- Have both in place? Great — the single file automatically uses the folder when
  it's there, so you get the best of both.

---

## How to use it (for technical users)

**As an agent.** Either agent file is a complete definition with frontmatter — drop
it into a Claude Code / Agent SDK `agents/` directory (or paste its body as a system
prompt anywhere). Use the **standalone** file if you're copying just one file; use
the **full** file when the `harness-architect/` folder lives alongside it. Then ask:

> "Design a harness for an agent that triages my inbound sales emails and drafts replies."

It will elicit the few decisions that matter, classify the problem against the
decision ladders, design every layer, and emit a `BLUEPRINT.md` + runnable code
adapted from `scaffold/`.

**As a library of patterns.** Even without running the agent, the `reference/`,
`templates/`, and `examples/` folders are a standalone playbook for building
agents, and `scaffold/` is a working harness you can fork.

## Try the runnable scaffold right now (zero dependencies)

```bash
cd scaffold
python examples/run_single_agent.py        # tiered single agent + eval
python examples/run_multi_agent.py          # orchestrator-worker (parallel read, single write)
python -m unittest discover -s tests -v     # 30 tests, offline
```

Everything runs on the Python standard library against a built-in mock model — no
API keys. Swap in a real provider (Anthropic/OpenAI/your own) with a one-line
change; see `scaffold/README.md`.

## The ideas it's built on (and won't let you skip)

1. **Simplest thing that works.** Augmented call → workflow → single agent →
   tiered → multi-agent, in that order. Add complexity only when it pays for itself.
2. **The loop is gather → act → verify → repeat.** Design all four; most failures
   are a missing *verify*.
3. **Context is a finite budget.** Curate ruthlessly; retrieve just-in-time;
   compact; offload to memory; isolate in sub-agents.
4. **Tools are a product.** Few, sharp, namespaced, token-efficient, with
   actionable errors and side-effect classes.
5. **Read parallelizes; writing doesn't.** Parallel research workers, single-
   threaded synthesis.
6. **Verification is the reliability multiplier.** Rules → environment truth →
   LLM-judge.
7. **Evaluate from day one.** ~20 real cases, judge outcomes, hold out a test set.
8. **Errors compound.** Checkpoints, resumability, graceful failure, tracing.
9. **Security is a layer.** Untrusted external content, least-privilege tools,
   sandboxing, gated destructive actions, bounded loops.
10. **Tier the models** by capability-per-step, and always estimate cost + latency.

Full evidence and citations: [`reference/harness-engineering-principles.md`](reference/harness-engineering-principles.md).

## Provenance

The principles are distilled from primary sources, not invented — Anthropic's
*Building Effective Agents*, *Effective Context Engineering*, *Writing Effective
Tools*, *Multi-Agent Research System*, and *Effective Harnesses for Long-Running
Agents*; OpenAI's *Practical Guide to Building Agents*; Cognition's *Don't Build
Multi-Agents*; LangChain's reconciliation of the two; and the *12-Factor Agents*
framework. Each is cited inline in the reference doc. Model names, prices, and
benchmarks are flagged as time-sensitive — the agent is instructed to **search
and verify, never guess** when those matter.
