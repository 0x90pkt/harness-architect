# Worked Blueprint — Customer-Support Triage Agent (single agent, tiered)

> A filled-in example of `templates/harness-blueprint.template.md`. It shows the
> **default, most common** answer: one agent, tiered models, strong verification.
> This is what most "build me an agent" requests should become.

## 0. One-liner
Resolves inbound support tickets end-to-end: understands the issue, pulls account
context, takes safe actions (refunds within policy, ticket updates), and escalates
the rest to a human.

## 1. Goal & success definition
- **Objective:** correctly resolve or correctly route every ticket.
- **Done looks like:** ticket closed with a correct resolution, OR escalated with a
  complete summary. User-visible metric: % auto-resolved without re-open within 7 days.
- **Non-goals:** no marketing, no actions outside documented policy, no refunds
  above the auto-approve threshold without a human.

## 2. Operating context
- **Trigger:** new ticket (webhook) or chat message.
- **Session shape:** multi-turn within a ticket; not multi-day.
- **Inputs:** ticket text, customer ID.
- **Systems:** CRM (read), billing (read + refund), KB (read), ticketing (write).
- **Constraints:** p95 < 20 s to first response; cost target < $0.05/ticket.
- **Stakes:** refunds move money → destructive; everything else reversible.

## 3. Architecture verdict
- **Ladder 1:** Rung 2 (single agent in a loop). Step count varies per ticket;
  not a fixed workflow. NOT multi-agent.
- **Ladder 2:** single agent. Fails the multi-agent test on "parallel/independent"
  and "value justifies 10–15× tokens" — a ticket is sequential and cheap.
- **Ladder 3 (tiering):**
  - FAST tier → intent classification + guardrail/PII checks on every message.
  - BALANCED tier → the main resolution loop (tool use, drafting replies).
  - FRONTIER tier → only on escalation-judgment / ambiguous policy calls.
- **Ladder 4:** not long-running.
- **Topology:**
```
ticket ─▶ [FAST: classify + safety] ─▶ [BALANCED: resolve loop ⟲ tools]
                                              │
                                  refund > threshold? ──▶ [human approval]
                                              │
                                       resolve or ──▶ [escalate w/ summary]
```

## 4. Control loop
- gather (CRM/KB) → act (reply/refund/update) → verify (policy + draft quality) → repeat.
- **Stop:** ticket marked resolved | escalated | max_iterations=8 | budget.
- **Human checkpoint:** any refund above the auto-approve threshold (a tool call).

## 5. System prompt (excerpt, "right altitude")
```
You are a support agent for <Company>. Resolve the customer's issue using the
tools provided, or escalate with a clear summary if you cannot.

Heuristics (not rigid rules):
- Read the customer's account context before proposing a resolution.
- Prefer the smallest action that fully resolves the issue.
- Refunds up to $<T> are auto-approved; above $<T>, call request_approval first.
- If policy is ambiguous or the customer is at churn risk, escalate.
Always end by either closing the ticket (with resolution) or escalating (with a
summary of what you tried and why).
```

## 6. Tools (ACI)
| Tool | Purpose | Output (bounded) | Side-effect |
|---|---|---|---|
| `get_customer_context` | One call: profile + recent orders + open tickets | high-signal fields only; concise default | read |
| `search_kb` | Return only relevant KB passages | top-k passages, ~1k tokens | read |
| `issue_refund` | Refund within policy | confirmation id | **destructive** (gated) |
| `update_ticket` | Set status / add note | ok | write |
| `request_approval` | Ask a human to approve an action | approval decision | write (HITL) |

Consolidated per the tool principle: `get_customer_context` replaces three
separate fetches. `issue_refund` is `requires_approval` above threshold.

## 7. Context & memory
- Up-front: the ticket + a short policy brief.
- JIT: customer context and KB fetched on demand (don't preload the CRM).
- Budget: 100k; compaction unlikely to trigger in a single ticket.

## 8. Orchestration
- None (single agent). Tiering is via per-step model selection, not sub-agents.

## 9. Verification
| Output | Method | Catches |
|---|---|---|
| Refund amount ≤ policy | rule | over-refund (F4/F2) |
| No PII leaked in reply | rule (regex/classifier) | data leak |
| Reply addresses the question | LLM-judge (completeness, tone) | unhelpful reply (G4) |
| Ticket left in valid end-state | rule (status set) | premature done (A1) |

## 10. Guardrails & security
- All ticket text is **untrusted** (prompt-injection surface) — never let it
  expand the agent's authority. Tools are least-privilege (billing scope = refund
  only, capped). Refund gated by approval. Loop bounded at 8 iterations.

## 11–12. Observability & reliability
- Trace every step (JSONL). Idempotency key on `issue_refund` (no double refunds).
- Retry transient CRM/billing failures; on repeated failure, escalate gracefully.

## 13. Evaluation
- ~20 real anonymized tickets across intents (billing, bug, how-to, cancel).
- Grader: end-state (correct status + action) + LLM-judge for reply quality.
- Metrics: auto-resolution rate, escalation precision, tokens, refund-policy
  violations (must be 0), p95 latency.

## 14. Cost & latency
- ~5–8k tokens/ticket on BALANCED + a few FAST calls → well under $0.05.
  (⚠ verify current per-token prices.) p95 dominated by tool latency, not the model.

## 15. Tuning playbook
1. Watch escalations that *should* have auto-resolved → usually missing KB or
   unclear tool description. Fix the tool/desc first.
2. Watch auto-resolutions that re-open → tighten the verify rubric.
- **Highest-leverage next step:** sharpen `get_customer_context` to return exactly
  the fields the model uses (measure which it cites).

## 16. Risk register
| Risk | L | I | Mitigation |
|---|---|---|---|
| Injection via ticket text | M | H | untrusted-content handling; capped tool scopes |
| Over-refund | L | H | policy rule + approval gate + idempotency |
| Wrong escalation | M | M | LLM-judge on escalation decision; human feedback loop |
