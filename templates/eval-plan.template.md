# Evaluation Plan — <AGENT NAME>

> Start small (~20 realistic cases) on day one. Judge outcomes, not rigid paths.
> Hold out a test set. Grow the suite from real failures.

## 1. North-star success criterion
<The single outcome that defines success — mirrors BLUEPRINT §1.>

## 2. Dataset
- **Source:** <real usage / representative tasks; avoid toy sandbox prompts>
- **Size:** <~20 to start; split train/dev vs. held-out test>
- **Format:** one record per case:
```json
{
  "id": "case-001",
  "input": "<realistic task prompt>",
  "expected": "<verifiable outcome OR rubric-graded answer>",
  "expected_tools": ["<optional: tools you'd expect>"],
  "difficulty": "simple|comparison|complex",
  "notes": "<provenance / why this case matters>"
}
```
> Strong cases often require many tool calls and mirror real complexity.

## 3. Grading method
Pick the cheapest sufficient method per case:

- **Exact/structural** — string/JSON match (tolerant of formatting/punctuation).
- **Programmatic** — run code/tests, query state, diff outputs.
- **End-state** — for state-mutating agents: assert the final state / checkpoints.
- **LLM-as-judge** — for free-form outputs. Single judge, rubric below, returns a
  0.0–1.0 score + pass/fail.

## 4. LLM-judge rubric
| Dimension | What it measures | Weight |
|---|---|---|
| Factual accuracy | Claims match sources / ground truth | <…> |
| Completeness | All requested aspects covered | <…> |
| Citation/attribution | Sources support the claims (if applicable) | <…> |
| Source/output quality | Primary/authoritative; well-formed | <…> |
| Tool efficiency | Right tools, reasonable number of calls | <…> |
| Safety/guardrails | No unsafe or out-of-scope actions | <…> |

Judge prompt skeleton:
```
You are grading an agent's output against a rubric. Be strict but fair; do not
penalize valid alternative phrasings or formatting.
TASK: {input}
GROUND TRUTH / EXPECTATIONS: {expected}
AGENT OUTPUT: {output}
For each rubric dimension, give a 0.0–1.0 score with one-line justification.
Then output overall_score (0.0–1.0) and pass (true/false, threshold {t}).
Return JSON: {"scores": {...}, "overall_score": x, "pass": bool, "notes": "..."}
```

## 5. Metrics tracked (beyond pass rate)
- success rate (pass/total)
- mean tokens per task (and per tier)
- mean tool calls per task; tool error rate
- p50/p95 latency per task
- estimated cost per task
> Redundant calls → fix pagination/limits. Invalid-param errors → fix tool docs.

## 6. Process
- [ ] Run dev set on every change; record metric deltas.
- [ ] Read failing transcripts (including tool calls/results) — the model's
      reasoning often reveals the fix.
- [ ] Periodically run the **held-out** set to check for overfitting.
- [ ] Add new cases whenever a novel failure appears in dev/prod.
- [ ] Keep a human spot-check — automation misses bias/edge cases.

## 7. Acceptance bar
- **Ship when:** <e.g., ≥ X% pass on held-out, ≤ $Y/run, ≤ Z s p95>.
