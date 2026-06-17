# Harness Engineering — Principles & Evidence

This is the evidence base behind the Harness Architect agent. It is deliberately
dense and citation-backed so that every design recommendation can be defended,
not asserted. It is **platform-agnostic**: the principles hold whether you run on
a raw provider API, the Claude Agent SDK, OpenAI's Agents SDK, LangGraph, or a
hand-rolled loop.

> **A note on sourcing.** Where a claim comes from a primary source, it is cited
> inline as `[Sn]` and listed in **Sources** at the end. Specific model names,
> prices, and benchmark numbers age quickly — they are flagged `⚠ time-sensitive`.
> When building a real harness, re-verify those by searching; do not trust a
> cached number.

---

## 1. What a "harness" is

The **model** is raw capability. The **harness** is the engineered system around
it that turns capability into reliable behavior. Anthropic describes the Claude
Agent SDK as "a powerful, general-purpose agent **harness** … adept at coding, as
well as other tasks that require the model to use tools to gather context, plan,
and execute," with context-management capabilities like compaction. [S7]

A harness comprises, at minimum:

- a **control loop** (what runs, in what order, when it stops);
- a **system prompt / instructions** (how the model should behave);
- **tools** and their interfaces (how the model perceives and acts);
- a **context strategy** (what tokens are present at each step, and how they're
  curated, retrieved, compacted, and offloaded);
- **memory** (what persists beyond the live window);
- an **orchestration topology** (one agent, tiered, or many);
- **verification** (how output is checked);
- **guardrails & security** (what's allowed, what's sandboxed, what's gated);
- **evaluation & observability** (how you measure and debug it).

The central engineering claim of this whole field: **a mediocre model in an
excellent harness routinely beats an excellent model in a poor one.** Most of the
quality of an agentic product lives in the harness, not the weights.

---

## 2. The agent loop

> In Claude Code, Claude often operates in a specific feedback loop:
> **gather context → take action → verify work → repeat.** [S7]

This four-phase loop is the spine of every agent. Designing a harness means
designing each phase deliberately:

- **Gather context** — agentic search over a file system / metadata, semantic
  (embedding) search, sub-agents with isolated windows, and compaction to stay
  within budget. [S7]
- **Take action** — tools, bash/scripts, code generation, and external
  integrations (e.g., MCP). Tools are "the primary actions Claude will consider
  when deciding how to complete a task." [S7]
- **Verify work** — rules-based feedback (linters, type checks, tests,
  validators), visual feedback (screenshots/renders), and LLM-as-judge for fuzzy
  criteria. "Agents that can check and improve their own output are fundamentally
  more reliable — they catch mistakes before they compound." [S7]
- **Repeat** — until a stopping condition (task done, max iterations, budget,
  or a human checkpoint).

The barest version of an agent, in code, is famously small [S8]:

```python
context = [initial_event]
while True:
    next_step = llm.determine_next_step(context)   # LLM picks a tool (structured output)
    context.append(next_step)
    if next_step.intent == "done":
        return next_step.final_answer
    result = execute_step(next_step)               # deterministic code runs it
    context.append(result)
```

Anthropic's working definition has converged to the same thing: **"agents are
LLMs autonomously using tools in a loop."** [S2]

Most observed agent failures localize to one weak phase — most often **verify**
(the agent declares victory without checking), then **gather** (it acts on missing
context). Diagnose by phase.

---

## 3. Workflows vs. agents, and the five workflow patterns

Anthropic draws an architectural line [S1]:

- **Workflows**: LLMs and tools orchestrated through **predefined code paths**.
- **Agents**: LLMs that **dynamically direct their own processes and tool usage**.

> "Find the simplest solution possible, and only increase complexity when needed.
> This might mean not building agentic systems at all." [S1]

The augmented LLM (an LLM + retrieval + tools + memory) is the basic building
block. On top of it, five **workflow** patterns cover most needs before you reach
for a true agent [S1]:

| Pattern | What it is | Use when |
|---|---|---|
| **Prompt chaining** | Decompose into fixed sequential steps; gate between them | Task cleanly splits into fixed subtasks; trade latency for accuracy |
| **Routing** | Classify input, send to a specialized path | Distinct categories handled better separately; cheap vs. capable model routing |
| **Parallelization** | Run subtasks (sectioning) or repeats (voting) in parallel, aggregate | Subtasks independent; or multiple attempts raise confidence |
| **Orchestrator-workers** | A central LLM dynamically decomposes and delegates, then synthesizes | Subtasks can't be predicted up front (e.g., edits across an unknown set of files) |
| **Evaluator-optimizer** | One LLM generates, another critiques, loop | Clear eval criteria exist and iterative refinement measurably helps |

Three core principles Anthropic follows when an actual agent is warranted:
**(1) keep the design simple; (2) prioritize transparency by showing the agent's
planning steps; (3) carefully craft the agent-computer interface (ACI) through
thorough tool documentation and testing.** [S1]

OpenAI's guidance agrees on the trajectory: start with a **single agent** with
tools added incrementally; move to multi-agent only when a single agent's logic
gets unwieldy. Their two multi-agent shapes are the **Manager pattern** (a central
agent calls specialized agents as tools) and the **Decentralized pattern** (peer
agents hand off control to each other). Layered **guardrails** (input filtering,
tool-use limits, human-in-the-loop) are emphasized throughout. [S6]

---

## 4. Context engineering

Anthropic frames **context engineering** as the successor to prompt engineering:
"the set of strategies for curating and maintaining the optimal set of tokens
(information) during LLM inference." The question shifts from "what words go in
the prompt?" to **"what configuration of the whole context is most likely to
produce the desired behavior?"** [S3]

**Context is a finite resource with diminishing returns.** As tokens grow,
recall degrades — the **"context rot"** phenomenon. The mechanism is
architectural: transformer attention forms n² pairwise relationships across n
tokens, so attention gets "stretched thin," and models have seen fewer long
sequences in training. The result is "a performance gradient rather than a hard
cliff." Treat the window as an **attention budget**. [S3]

> The guiding rule: **find the smallest set of high-signal tokens that maximize
> the likelihood of the desired outcome.** ("Minimal" ≠ "short" — give enough to
> fully specify the behavior, and no more.) [S3]

Component-by-component [S3]:

- **System prompts — the "right altitude."** Avoid both extremes: brittle,
  hardcoded if-else logic (fragile, high-maintenance) *and* vague high-level
  guidance (no concrete signal). Aim between: specific enough to steer, flexible
  enough to let the model reason. Organize into delineated sections (e.g.
  `<background>`, `<instructions>`, `## Tool guidance`, `## Output`); use XML tags
  or Markdown headers. Start minimal with the best model, then add instructions
  only where failure modes appear.
- **Tools.** Self-contained, robust to error, minimal overlap. "If a human
  engineer can't definitively say which tool to use in a situation, an AI agent
  can't be expected to do better." Bloated/overlapping tool sets are a top
  failure mode. [S3]
- **Examples (few-shot).** Curate a few diverse, canonical examples rather than
  stuffing every edge case. "Examples are the 'pictures' worth a thousand
  words." [S3]

### 4.1 Retrieval: just-in-time vs. up-front

Two strategies, often combined [S3]:

- **Up-front / pre-inference retrieval** (e.g., classic embedding RAG): fetch
  relevant chunks before the model runs. Faster, but risks stale indexes and
  loading irrelevant tokens.
- **Just-in-time ("agentic") retrieval**: keep lightweight identifiers (file
  paths, queries, links) and let the agent load data on demand with tools. This
  mirrors human cognition (we use file systems and bookmarks, not total recall)
  and enables **progressive disclosure** — the agent discovers structure
  incrementally; file names, sizes, timestamps, and folder hierarchy are
  themselves signal. Slower per step, and requires good tools/heuristics so the
  agent doesn't chase dead ends.
- **Hybrid** (recommended default for many cases): drop a little context up front
  (e.g., a `CLAUDE.md`-style brief) and let the agent retrieve the rest
  just-in-time (e.g., `glob`/`grep`). [S3]

Anthropic's own steer: prefer **agentic search first**; add semantic/embedding
search only if you need faster results — it's "faster … but less accurate, more
difficult to maintain, and less transparent." [S7]

### 4.2 Long-horizon techniques

When a task exceeds a single window, three techniques (combinable) [S3]:

- **Compaction** — summarize the conversation near the limit and reinitialize a
  fresh window with the summary (preserve decisions, unresolved bugs, key
  details; drop redundant tool output). "Tool-result clearing" is the
  lightest-touch form: once a tool result is deep in history, you rarely need its
  raw bytes again. Tune compaction prompts by **maximizing recall first, then
  improving precision.**
- **Structured note-taking (agentic memory)** — the agent writes notes/`NOTES.md`/
  a to-do list to external storage and reads them back later. Cheap, persistent,
  and powerful (Claude playing Pokémon maintains maps and tallies across
  thousands of steps this way).
- **Sub-agent architectures** — specialized sub-agents work in clean, isolated
  windows and return only a condensed distillation (often ~1–2k tokens from tens
  of thousands explored). Clean separation of concerns; detailed search context
  stays out of the lead agent.

Selection guide [S3]: compaction for conversational back-and-forth; note-taking
for iterative work with clear milestones; multi-agent for parallelizable
research/analysis.

---

## 5. Tool design (the agent-computer interface)

Tools are "a new kind of software which reflects a contract between deterministic
systems and non-deterministic agents." Design them **for agents**, not by
reflexively wrapping existing API endpoints. [S4]

The iterative process Anthropic recommends: **prototype → evaluate (with realistic
tasks) → collaborate with the model to improve the tools.** [S4]

Five principles [S4]:

1. **Choose the right tools — more tools ≠ better.** Build a few sharp tools for
   high-impact workflows. **Consolidate** multi-step operations: prefer
   `schedule_event` over `list_users` + `list_events` + `create_event`; prefer
   `search_logs` (returns only relevant lines) over `read_logs`; prefer
   `get_customer_context` over three separate fetches. Each tool earns its place
   and has a distinct purpose. (Reasoning: agents have limited context where
   computers have cheap memory — a tool that dumps all rows forces brute-force,
   token-by-token reading.)
2. **Namespace** related tools under common prefixes (`asana_search`,
   `asana_projects_search`) so the agent picks the right one among dozens.
   Prefix vs. suffix has measurable, model-dependent effects — test it.
3. **Return meaningful context.** High-signal fields (`name`, `file_type`,
   `image_url`) over low-level identifiers (`uuid`, `mime_type`, `256px_url`).
   Resolving cryptic UUIDs to natural-language identifiers measurably reduces
   hallucination. Offer a `response_format` enum (`concise` | `detailed`) so the
   agent controls verbosity.
4. **Optimize for token efficiency.** Paginate, filter, range-select, truncate
   with sensible defaults. (Claude Code caps tool responses at ~25k tokens by
   default.) When you truncate, *tell the agent how to get more* (filters,
   pagination). [S4]
5. **Prompt-engineer the descriptions.** Write each tool description like a
   docstring for a new hire: make implicit context explicit, name parameters
   unambiguously (`user_id` not `user`), enforce with strict schemas. "Even small
   refinements to tool descriptions can yield dramatic improvements." [S4]

**Error messages are part of the interface.** Return actionable, specific errors
("invalid date format; expected YYYY-MM-DD") not opaque tracebacks — they steer
the agent toward correct behavior. [S4]

**Format choices matter.** Give the model tokens to "think" before committing;
keep formats close to what appears naturally in training data; avoid formats with
high overhead (e.g., requiring exact line counts in diffs, or heavy
string-escaping of code inside JSON). `Poka-yoke` the inputs — make mistakes hard
(e.g., require absolute file paths so the agent can't be confused by a changed
working directory). Anthropic "spent more time optimizing tools than the overall
prompt" for SWE-bench. [S1]

---

## 6. Multi-agent: the debate, reconciled

Two influential 2025 posts landed with opposite titles — Anthropic's *"How we
built our multi-agent research system"* [S5] and Cognition's *"Don't Build
Multi-Agents"* [S9]. They actually agree on the underlying mechanics. [S10]

### 6.1 The case *for* (Anthropic's research system) [S5]

- **Architecture:** orchestrator-worker. A lead agent plans, spawns parallel
  sub-agents that search with isolated context windows, then synthesizes.
- **Result:** a multi-agent system (frontier lead + balanced sub-agents)
  outperformed a single frontier agent by **90.2%** on their internal research
  eval. ⚠ time-sensitive
- **Why it works — token economics:** on BrowseComp, **token usage alone explained
  ~80% of performance variance**; token usage + tool calls + model choice
  explained ~95%. Multi-agent is a way to *spend more tokens effectively* via
  parallel windows. ⚠ time-sensitive
- **The cost:** agents use ~4× the tokens of chat; multi-agent ~15× — so it only
  pays off on **high-value tasks**. ⚠ time-sensitive
- **Where it fits:** "valuable tasks that involve heavy parallelization,
  information that exceeds single context windows, and interfacing with numerous
  complex tools." **Poor fit:** tasks needing shared context or with many
  inter-agent dependencies — "most coding tasks involve fewer truly
  parallelizable tasks than research, and LLM agents are not yet great at
  coordinating and delegating to other agents in real time." [S5]

Eight prompt-engineering lessons for orchestration [S5]: think like your agents
(simulate and watch them fail); teach the orchestrator to delegate (each
sub-agent needs **objective + output format + tool/source guidance + boundaries**);
**scale effort to complexity** (simple fact-find ≈ 1 agent / 3–10 calls;
comparison ≈ 2–4 sub-agents / 10–15 calls each; complex ≈ 10+ sub-agents with
divided responsibility); tool design is critical; let agents improve their own
prompts/tools; start wide then narrow; guide the thinking process (extended
thinking as a scratchpad); parallelize tool calls (3–5 sub-agents, 3+ tools each
→ up to 90% time reduction). [S5]

### 6.2 The case *against* (Cognition) [S9]

Two principles so important you should "by default rule out any agent
architectures that don't abide by them":

1. **Share context** — and share *full agent traces*, not just individual
   messages. Sub-agents that only see their narrow subtask misinterpret it.
2. **Actions carry implicit decisions; conflicting decisions carry bad results.**
   Parallel agents making independent implicit choices (e.g., two different visual
   styles for one app) produce incoherent output that's hard to merge.

The conclusion: a **single-threaded linear agent** is the reliable default. For
tasks too long for one window, introduce a dedicated **context-compression model**
(possibly fine-tuned) rather than spraying work across uncoordinated agents.
Multi-agent collaboration in 2025 tends to be fragile because "decision-making
ends up being too dispersed and context isn't shared thoroughly enough." [S9]

### 6.3 The reconciliation [S10]

Both camps actually agree:

- **Context engineering is the #1 job** whether single- or multi-agent.
- **Reading parallelizes; writing does not (easily).** Read actions are
  independent; conflicting *write* actions create incompatible outputs.
  Tellingly, Anthropic's research system parallelizes the **reading** (research)
  but does the **writing** (final synthesis) in a *single* agent call. [S10]

**Practical rule for the harness:** parallelize breadth-first *reading/research*
across sub-agents with crisp delegation contracts; keep *writing, synthesis, and
state mutation* in one coherent thread. Reach for multi-agent only when the value
justifies ~10–15× tokens and the work is genuinely parallel and read-heavy.

### 6.4 Multi-agent reliability tips [S5]

- **End-state evaluation** for agents that mutate state: judge the final state,
  not the exact path; use discrete checkpoints rather than per-step validation.
- **Long-horizon conversation management:** summarize completed phases to external
  memory; spawn fresh sub-agents with clean contexts via careful handoffs.
- **Write large outputs to a store, pass references** to avoid the "game of
  telephone" — subagents persist artifacts and return lightweight pointers.

---

## 7. Long-running harnesses (across many context windows)

The hardest harness problem: an agent that must work for hours/days across
discrete sessions, each starting with **no memory of the last** — "like a software
project staffed by engineers working in shifts, where each new engineer arrives
with no memory of what happened on the previous shift." Compaction alone is
insufficient. [S11]

Anthropic's two-part solution (with a runnable quickstart) [S11]:

- **Initializer agent** (first session only, special prompt): build durable
  scaffolding — a setup script (`init.sh`), a progress log (`claude-progress.txt`),
  an initial version-control commit, and crucially a **structured feature/task
  list** (they used JSON with 200+ end-to-end features, each marked
  `passes: false`). JSON beat Markdown because the model is less likely to
  inappropriately rewrite it.
- **Worker agent** (every subsequent session): **make incremental progress on one
  item**, then leave a **clean, mergeable state** — commit to version control with
  descriptive messages, update the progress file, and only mark an item done after
  **end-to-end self-verification**.

Each session **gets its bearings** first: check the working directory, read the
progress log + version-control history, read the task list, pick the
highest-priority unfinished item, and run a quick end-to-end smoke test before
starting new work. [S11]

The four canonical long-running failure modes and their fixes [S11]:

| Failure | Fix in the harness |
|---|---|
| Declares the whole project done too early | Initializer writes a complete feature list; worker reads it and picks one item |
| Leaves the environment buggy/undocumented | Initializer seeds VCS + progress file; worker reads them in, smoke-tests, and commits + logs out |
| Marks features done prematurely | Worker must self-verify end-to-end before marking `passing` |
| Wastes tokens figuring out how to run things | Initializer writes `init.sh`; worker reads it first |

Note: in that design the "initializer" and "worker" are the *same* harness (same
tools, same system prompt) — only the **initial user prompt** differs. [S11]

---

## 8. Evaluation

> "Good evaluations are essential for building reliable AI applications, and
> agents are no different." [S5]

Core practices, drawn from Anthropic's tools and multi-agent work and echoed by
LangChain [S4][S5][S10]:

- **Start immediately, start small.** ~20 cases drawn from real usage is enough to
  see big effects early (a prompt tweak might move success 30% → 80%). Don't wait
  for hundreds. [S5]
- **Judge outcomes, not rigid paths.** Multi-agent (and most agentic) systems take
  different valid routes to the same goal. Evaluate whether the **right outcome**
  was reached via a **reasonable process** — not whether prescribed steps were
  followed. [S5]
- **End-state evaluation** for state-mutating agents (judge the final state /
  checkpoints). [S5]
- **LLM-as-judge, done well.** A single judge call against a rubric, emitting a
  0.0–1.0 score plus a pass/fail, was more consistent than multiple judges for
  Anthropic's research eval. Rubric dimensions used: **factual accuracy, citation
  accuracy, completeness, source quality, tool efficiency.** Avoid overly strict
  verifiers that punish formatting/phrasing differences. [S5][S4]
- **Keep human evaluation in the loop.** Humans catch what automation misses —
  e.g., a systematic bias toward SEO content farms over authoritative sources.
  [S5]
- **Track the right metrics**, not just top-line accuracy: total tokens, tool-call
  count, per-call and per-task latency, and tool error rate. Redundant calls hint
  at pagination/limit issues; invalid-parameter errors hint at unclear tool
  descriptions. [S4]
- **Hold out a test set** to avoid overfitting your prompts/tools to the
  "training" eval. [S4]

For tool-specific evals, write **realistic, complex tasks** (often needing many
tool calls) over toy "sandbox" prompts, each paired with a verifiable
outcome. [S4]

---

## 9. Reliability & production

The "last mile" is most of the journey — "the gap between prototype and production
is often wider than anticipated." [S5]

- **Agents are stateful; errors compound.** "Minor system failures can be
  catastrophic for agents." Don't restart from scratch on error — build systems
  that **resume from where the agent was** (checkpoints) and let the model **adapt
  to tool failures** (tell it a tool failed and let it route around). Combine
  AI adaptability with deterministic safeguards (retries, checkpoints). [S5]
- **Compact errors into context.** Rather than crashing, feed the error back so
  the agent can self-correct; only escalate/halt when needed. (12-Factor's
  Factor 9.) [S8]
- **Observability/tracing is non-negotiable.** Agents are non-deterministic
  between runs; full production tracing of decisions, tool calls, and results is
  how you diagnose "it didn't find the obvious thing." [S5][S10]
- **Durable execution** (launch/pause/resume) belongs in the orchestration layer
  for any long-running agent. [S8][S10]
- **Deployment of stateful agents** needs care — e.g., **rainbow deployments**
  that keep old and new versions running while draining, so in-flight agents
  aren't broken by a deploy. [S5]
- **Sync vs. async orchestration:** synchronous sub-agents simplify coordination
  but bottleneck on the slowest worker and prevent mid-flight steering;
  asynchronous adds parallelism at the cost of harder state/error coordination.
  [S5]

### 9.1 The 12-Factor Agents checklist [S8]

A widely used, framework-agnostic distillation of what makes LLM software
production-grade. The factors:

1. Natural language → tool calls
2. **Own your prompts** (don't bury them in a framework)
3. **Own your context window** (context engineering is yours, not the framework's)
4. **Tools are just structured outputs** (a tool call is JSON your code executes)
5. Unify execution state and business state
6. Launch / pause / resume with simple APIs
7. Contact humans with tool calls (human-in-the-loop as a first-class action)
8. Own your control flow
9. Compact errors into the context window
10. **Small, focused agents** (prefer narrow, composable agents over one
    god-agent)
11. Trigger from anywhere; meet users where they are
12. Make your agent a stateless reducer (`(state, event) → new_state`)

Two meta-lessons from the same source [S8]: (a) the best "agents" are **mostly
deterministic software with LLM steps inserted at the right points** — not "here's
a prompt and a bag of tools, loop forever"; (b) frameworks get you to ~70–80%
fast, but the last 20% often requires reverse-engineering the framework, so
**keep ownership of prompts, context, and control flow**.

---

## 10. Security & guardrails

A harness is an attack surface. Treat security as a design layer, not a patch.

- **Indirect prompt injection is the #1 risk.** OWASP classifies prompt injection
  as **LLM01**, and the **OWASP Top 10 for Agentic Applications** adds agent-
  specific risks including **Agent Goal Hijack (ASI01), Tool Misuse (ASI02), and
  Memory Poisoning (ASI06).** Any external content (web pages, emails, files,
  tool outputs, third-party MCP responses) is **untrusted input** that may carry
  instructions. [S12] ⚠ time-sensitive (frameworks evolve)
- **Defense in depth across the pipeline** [S12]: input validation/filtering →
  model-behavior control → tool/API control (allow-lists, schemas) → runtime
  monitoring → evaluation & red-teaming → protocol trust. No single layer
  suffices.
- **Least privilege & treat the agent as an untrusted third party.** Give each
  tool the narrowest scope it needs; apply the same identity/access controls,
  token lifecycle management, and audit logging you'd apply to an external
  contractor. [S12]
- **Sandbox side effects.** Run code/tools in isolated environments; constrain
  file-system and network reach. (Anthropic recommends "extensive testing in
  sandboxed environments, along with the appropriate guardrails" for autonomous
  agents.) [S1]
- **Gate destructive/irreversible actions** behind human approval or hard
  constraints. Classify every tool by side-effect: read / write / destructive.
  Layered guardrails (input, tool-use, human-in-the-loop) compound. [S6]
- **Bound the loop.** Max iterations, token/cost budgets, and rate limits prevent
  runaway behavior and contain the blast radius of a hijack.

---

## 11. Model tiering & token economics

- **Token budget dominates capability on hard agentic tasks** — to first order,
  spending more tokens effectively (more reasoning, more parallel exploration)
  buys performance, and architecture is largely a way to deploy tokens well. [S5]
- **But better models are efficiency multipliers**: a model-generation upgrade can
  beat doubling the token budget on the prior model. Choose the model *and* the
  budget together. [S5] ⚠ time-sensitive
- **Tier by capability-per-step, not by habit** [S1]:
  - **Frontier tier** — orchestration, planning, hard reasoning, final synthesis.
  - **Balanced tier** — routine sub-steps, most worker/sub-agent work.
  - **Fast/cheap tier** — classification, routing, extraction, guardrail checks.
  Anthropic's routing example explicitly sends easy/common queries to a small
  cheap model and hard/unusual ones to a capable model; their research system
  pairs a frontier lead with balanced sub-agents. [S1][S5]
- **Always estimate cost & latency** for a design, and let the chosen tiering be
  the main lever for hitting a budget.

> ⚠ Model names, context-window sizes, prices, and benchmark scores change on the
> order of months. The Architect should name *current* models in a blueprint only
> after verifying them, and should always express the **design** in terms of
> tiers/roles so it survives the next model release.

---

## 12. Quick-reference: principle → design move

| Principle | Concrete move in the harness |
|---|---|
| Simplest thing that works | Try augmented call / workflow before a looping agent; single agent before multi |
| Loop = gather/act/verify | Explicitly design all four phases; never ship without a real verify phase |
| Context is finite | Token budget + compaction + tool-result clearing + JIT retrieval |
| Right-altitude prompt | Sectioned system prompt; heuristics over brittle rules; minimal-but-sufficient |
| Tools are a product | Few sharp consolidated tools; namespaced; concise/detailed outputs; actionable errors |
| Share context / implicit decisions | Full delegation contracts; one writer thread; references not copies |
| Read ∥, write serial | Parallel research sub-agents; single synthesis agent |
| Verification multiplies | Rules → environment ground truth → LLM-judge, each tied to a failure mode |
| Eval from day one | ~20 real cases, outcome-judged, held-out set, tracked metrics |
| Errors compound | Checkpoints, resume, compact-errors-into-context, graceful tool failure |
| Security is a layer | Untrusted external content, least-privilege tools, sandbox, gate destructive acts |
| Tier the models | Frontier orchestrate / balanced workers / cheap classify; estimate cost+latency |

---

## Sources

- **[S1]** Anthropic, *Building Effective AI Agents* (Dec 19, 2024).
  https://www.anthropic.com/engineering/building-effective-agents
- **[S2]** Anthropic, *Effective context engineering for AI agents* (Sep 29, 2025).
  https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- **[S3]** Same as [S2] (context-engineering specifics).
- **[S4]** Anthropic, *Writing effective tools for AI agents — with agents*
  (Sep 11, 2025). https://www.anthropic.com/engineering/writing-tools-for-agents
- **[S5]** Anthropic, *How we built our multi-agent research system* (Jun 13, 2025).
  https://www.anthropic.com/engineering/multi-agent-research-system
- **[S6]** OpenAI, *A Practical Guide to Building Agents* (2025).
  https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf
- **[S7]** Anthropic / Claude, *Building agents with the Claude Agent SDK*
  (Sep 29, 2025). https://claude.com/blog/building-agents-with-the-claude-agent-sdk
- **[S8]** HumanLayer (Dex Horthy), *12-Factor Agents* (2025).
  https://github.com/humanlayer/12-factor-agents
- **[S9]** Cognition (Walden Yan), *Don't Build Multi-Agents* (Jun 12, 2025).
  https://cognition.ai/blog/dont-build-multi-agents
- **[S10]** LangChain (Harrison Chase), *How and when to build multi-agent systems*
  (Jun 16, 2025). https://www.langchain.com/blog/how-and-when-to-build-multi-agent-systems
- **[S11]** Anthropic, *Effective harnesses for long-running agents* (Nov 26, 2025).
  https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- **[S12]** OWASP Top 10 for LLM Applications (LLM01: Prompt Injection) and OWASP
  Top 10 for Agentic Applications (ASI01 Agent Goal Hijack, ASI02 Tool Misuse,
  ASI06 Memory Poisoning); summarized via 2025 security surveys. Verify current
  list at https://owasp.org before relying on specific item numbers.
