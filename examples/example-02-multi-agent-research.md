# Worked Blueprint — Deep-Research Agent (multi-agent, orchestrator-worker)

> A filled-in example showing the **justified** multi-agent case. Mirrors the
> architecture validated by Anthropic's research system: parallel READ workers +
> single-threaded synthesis. Maps to `scaffold/harness/subagents.py`.

## 0. One-liner
Answers broad, open-ended research questions by exploring many sources in parallel
and synthesizing a single cited report.

## 1. Goal & success definition
- **Objective:** a comprehensive, accurate, well-cited answer to a research query.
- **Done looks like:** report covers all sub-questions, every claim is attributable
  to a source, no major omissions. Judged by the rubric in §13.
- **Non-goals:** real-time data, transactional actions, anything write-heavy.

## 2. Operating context
- **Trigger:** a user research query (chat/API).
- **Session shape:** minutes-long, single session (with compaction).
- **Inputs:** a natural-language question, optional scope hints.
- **Systems:** web search + document/corpus search (read-only).
- **Constraints:** high value per query justifies high token spend; latency
  budget ~minutes, not seconds.
- **Stakes:** low side-effect risk (read-only); reputational risk if inaccurate.

## 3. Architecture verdict
- **Ladder 1:** Rung 4 (multi-agent). Open-ended, unpredictable steps.
- **Ladder 2 — passes ALL boxes:** decomposable into independent threads ✓;
  read/research-heavy ✓; exceeds one context window ✓; high value justifies
  ~10–15× tokens ✓; sub-tasks have clean boundaries ✓.
- **Ladder 3 (tiering):** FRONTIER lead (plan + synthesize); BALANCED workers
  (search + distill). This pairing is the cost sweet spot.
- **Critical constraint:** parallelize the **reading**; do the **writing**
  (synthesis) in ONE frontier agent. Never parallelize the write.
- **Topology:**
```
query ─▶ [LEAD: plan, decompose, set effort]
             │  spawns N workers (effort-scaled)
   ┌─────────┼───────────┬───────────┐
 [worker]  [worker]   [worker]  ...  (parallel READS, isolated context)
   └────────condensed summaries / artifact refs────────┐
                                                         ▼
                                          [LEAD/SYNTH: single-threaded write]
                                                         ▼
                                            [Citation pass] ─▶ report
```

## 4. Control loop
- Lead: gather (plan) → act (spawn workers) → verify (coverage?) → maybe spawn
  more → synthesize.
- **Effort scaling (in the lead prompt):** simple fact-find = 1 worker/3–10 calls;
  comparison = 2–4 workers/10–15 calls; complex = 10+ workers, divided.
- **Stop:** coverage satisfied | max workers reached | budget.

## 5. System prompts (two roles)
**Lead (excerpt):**
```
Decompose the query into independent, non-overlapping sub-questions. For each,
write a delegation contract: objective, output format, which sources/tools,
and explicit boundaries. Scale the number of workers to query complexity (rules
above). After workers return, decide if coverage is sufficient; if not, spawn
targeted follow-ups. Then synthesize ONE coherent, cited report yourself.
```
**Worker (excerpt):**
```
Research ONLY your assigned objective. Start with broad queries, then narrow.
Evaluate source quality (prefer primary/authoritative over SEO content farms).
Return a concise (<=200 word) summary with source references. Do not exceed
your boundaries or duplicate others' scope.
```

## 6. Tools (ACI)
| Tool | Purpose | Output | Side-effect |
|---|---|---|---|
| `web_search` | broad external search | ranked snippets + URLs | read |
| `fetch_page` | pull a page's main content | cleaned text, token-bounded | read |
| `corpus_search` | search internal docs | top-k passages | read |
| `write_artifact` | persist a long finding, return a reference | artifact id | write |

`write_artifact` implements "pass references, not payloads" to avoid the game of
telephone (D5).

## 7. Context & memory
- Lead saves its **plan to memory** immediately (so a context reset can't lose it).
- Workers run in **isolated context windows**; only condensed summaries return.
- Compaction on the lead for long runs; tool-result clearing on workers.

## 8. Orchestration
- **Topology:** orchestrator-workers.
- **Delegation contract:** objective + output format + tools/sources + boundaries
  (the #1 fix for duplicated/garbled work).
- **Return:** condensed summaries; large outputs via `write_artifact` references.
- **Read/write split:** all reading is parallel; synthesis is single-threaded.

## 9. Verification
| Output | Method | Catches |
|---|---|---|
| Each claim has a source | rule (citation present) | hallucinated claims |
| Coverage of sub-questions | LLM-judge (completeness) | gaps (D3) |
| Source quality | LLM-judge (source_quality) | content-farm bias |
| Final report quality | LLM-judge rubric | low fidelity |

## 10. Guardrails & security
- Fetched web content is **untrusted** — isolate it from instructions (injection
  is acute here). Read-only tools = limited blast radius. Cap workers + budget to
  prevent runaway spawning (D4) and cost blowout (D6).

## 11–12. Observability & reliability
- Trace lead decisions + each worker (separately). Checkpoint the lead plan;
  resume from it on failure. Sub-agents are stateless and retryable.

## 13. Evaluation
- ~20 research queries with known-correct facts where possible (e.g., "list the
  X with the largest Y").
- Single LLM-judge call, rubric: factual accuracy, citation accuracy,
  completeness, source quality, tool efficiency → 0–1 + pass/fail.
- Plus human spot-checks for source-selection bias.
- Metrics: pass rate, tokens (expect ~15× a chat), worker count, tool errors.

## 14. Cost & latency
- Dominated by token spend across workers (~15× a single chat). Justified only by
  query value. Latency cut sharply by running 3–5 workers + 3+ tools in parallel.
  (⚠ verify current model prices before quoting $.)

## 15. Tuning playbook
1. Watch for duplicated worker scopes → tighten delegation boundaries.
2. Watch for over-spawning on simple queries → fix effort-scaling rules.
3. Watch source-quality complaints → add explicit source heuristics to prompts.
- **Highest-leverage next step:** improve the lead's decomposition prompt; it
  determines everything downstream.

## 16. Risk register
| Risk | L | I | Mitigation |
|---|---|---|---|
| Cost blowout | M | M | per-query budget; gate behind value threshold |
| Injection via fetched pages | M | H | untrusted-content isolation; read-only tools |
| Incoherent synthesis | L | M | single-threaded write; citation + coverage checks |
