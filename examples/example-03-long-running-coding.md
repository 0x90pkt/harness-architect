# Worked Blueprint — Long-Running Build Agent (multi-session, initializer + worker)

> A filled-in example of the **long-running** pattern (Ladder 4). It solves the
> "work across many context windows / sessions" problem with a two-phase harness:
> an initializer that builds durable scaffolding, and a worker that makes
> incremental, verified progress each session. Pattern source: Anthropic,
> *Effective harnesses for long-running agents*.

## 0. One-liner
Builds a non-trivial software project (or any large artifact) over many sessions,
making steady, verified progress without losing the plot between context resets.

## 1. Goal & success definition
- **Objective:** complete a multi-feature build to a "mergeable" quality bar.
- **Done looks like:** every item in the feature list passes its end-to-end test;
  the repo is clean, documented, and runnable from scratch.
- **Non-goals:** one-shotting the whole project; marking features done untested.

## 2. Operating context
- **Trigger:** an initial spec, then repeated worker sessions (manual or cron).
- **Session shape:** **long-running across many context windows** — the defining
  constraint. Each session starts with no memory of the last.
- **Inputs:** a high-level spec (session 1); the repo + artifacts (later sessions).
- **Systems:** file system, shell, version control, a browser/automation tool for
  end-to-end testing, the language toolchain.
- **Constraints:** quality > speed; must never leave a broken main state.
- **Stakes:** medium — bad commits cost future-session time, but VCS makes them
  recoverable.

## 3. Architecture verdict
- **Ladder 1:** Rung 2/3 — a single capable agent in a loop, run repeatedly.
- **Ladder 2:** single agent (writing-heavy → do NOT parallelize). Optional future:
  a separate test/QA agent, but start single.
- **Ladder 3:** FRONTIER tier (coding + architecture is the hard-reasoning case).
- **Ladder 4: YES → two-phase pattern.** This is the whole point.
- **Topology:**
```
session 1:  [INITIALIZER] ─▶ feature_list.json (all "passes": false)
                           ─▶ init.sh (build/run/test)
                           ─▶ progress.log + initial VCS commit
session N:  [WORKER] ─▶ get bearings (pwd, read progress+VCS, read feature_list)
                     ─▶ smoke-test current state; fix if broken
                     ─▶ pick ONE highest-priority unfinished feature
                     ─▶ implement + self-verify end-to-end
                     ─▶ mark passes:true; commit; append progress.log
```
> Note: initializer and worker are the **same harness** (same tools/system prompt);
> only the **initial prompt** differs.

## 4. Control loop (per session)
- gather (read artifacts) → act (implement one feature) → verify (end-to-end) →
  leave clean state. Stop after one feature or when blocked.
- **Stop conditions:** feature done & committed | blocked (log + exit) | budget.

## 5. System prompts (two initial prompts, one harness)
**Initializer (excerpt):**
```
Set up the project foundation for the ENTIRE spec before writing features.
Produce: (1) feature_list.json — a comprehensive list of end-to-end features,
each {id, description, steps, passes:false}; (2) init.sh that installs, runs, and
smoke-tests the app; (3) progress.log; (4) an initial version-control commit.
Lay foundations for ALL features; do not implement them yet.
```
**Worker (excerpt):**
```
1. Run pwd. Read progress.log and the VCS log to learn what happened.
2. Read feature_list.json. Run init.sh and smoke-test; if broken, FIX FIRST.
3. Choose the single highest-priority feature with passes:false. Implement ONLY it.
4. Verify it end-to-end as a real user would (use the browser/automation tool),
   not just unit tests. Only then set passes:true.
5. Commit with a descriptive message and append a progress.log entry.
It is unacceptable to edit/remove tests to make features "pass."
```

## 6. Tools (ACI)
| Tool | Purpose | Side-effect |
|---|---|---|
| `read_file` / `search_files` | gather code context just-in-time | read |
| `write_file` / `edit_file` | make changes | write |
| `run_shell` | build, run, test (sandboxed) | write |
| `vcs_commit` | checkpoint progress | write |
| `browser_test` | end-to-end verification as a user | read |

## 7. Context & memory (the crux)
- **Durable, external memory IS the design:** `feature_list.json` (JSON, because
  models rewrite it less than Markdown), `progress.log`, and VCS history are the
  cross-session memory.
- Within a session: just-in-time file retrieval; compaction as a safety net.
- Each session reconstructs state from artifacts, not from a (nonexistent) prior
  context.

## 8. Orchestration
- Single agent. (If you later add a QA/test/cleanup specialist, give it the same
  artifacts and keep writing single-threaded.)

## 9. Verification (the failure-mode killer)
| Output | Method | Catches |
|---|---|---|
| Feature works end-to-end | `browser_test` (environment ground truth) | premature "done" (A1) |
| Build still runs | `init.sh` smoke test on startup | undocumented breakage (B3) |
| Code quality | linter/type-check via `run_shell` | sloppy hand-off |
| Only one feature touched | rule (diff scope) | one-shotting (A3) |

## 10. Guardrails & security
- `run_shell` is **sandboxed** (no host/prod access). VCS gives cheap rollback.
- Never edit/delete tests to force a pass (explicit prompt rule).

## 11–12. Observability & reliability
- progress.log + VCS history ARE the trace across sessions. Each session is
  resumable by construction. Commit after every feature = frequent checkpoints.

## 13. Evaluation
- Track features-passing over sessions (should monotonically increase).
- Per-session: did it leave a clean, runnable state? (binary check).
- End: full feature list passes; fresh clone runs via init.sh.

## 14. Cost & latency
- Many sessions × frontier tier = the dominant cost; bounded per session.
- (⚠ verify current model prices.) Optimize by making "get bearings" cheap
  (read summaries, not whole files).

## 15. Tuning playbook
1. If it declares done early → the feature list is incomplete; improve the
   initializer prompt.
2. If sessions start by re-fixing breakage → strengthen the "leave clean state"
   + end-of-session commit discipline.
3. If features regress → add the smoke test to startup (catch breakage before new
   work).
- **Highest-leverage next step:** invest in the initializer's feature list quality
  — it governs the whole run.

## 16. Risk register
| Risk | L | I | Mitigation |
|---|---|---|---|
| Drift / lost context between sessions | M | H | external memory (feature list, progress log, VCS) read on startup |
| Premature completion | M | H | comprehensive feature list + end-to-end verify |
| Broken main between sessions | M | M | startup smoke test + commit discipline |
