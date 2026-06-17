"""
Eval runner — run an agent over a dataset, grade outcomes, aggregate metrics.

Principles encoded (see ../../templates/eval-plan.template.md):
  - Start small; ~20 realistic cases beat zero.
  - Judge OUTCOMES, not rigid step paths (pass a grader of your choice).
  - Track more than pass rate: tokens, tool calls, errors, latency, cost.
  - Support a held-out split to detect overfitting.

The grader is pluggable: pass any `grade(output, case) -> (passed, score, notes)`.
Ready-made graders: exact_match, contains_all, and make_judge_grader(provider).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from harness.loop import AgentLoop
from harness.observability import Usage
from .rubric import Rubric


@dataclass
class EvalCase:
    id: str
    input: str
    expected: str = ""
    expected_tools: list[str] = field(default_factory=list)
    difficulty: str = "simple"
    split: str = "dev"          # "dev" or "test" (held-out)
    notes: str = ""


# grader: (output, case) -> (passed, score, notes)
Grader = Callable[[str, EvalCase], "tuple[bool, float, str]"]


@dataclass
class CaseOutcome:
    id: str
    passed: bool
    score: float
    iterations: int
    usage: Usage
    seconds: float
    stop_reason: str
    notes: str = ""


@dataclass
class EvalReport:
    outcomes: list[CaseOutcome]

    @property
    def n(self) -> int:
        return len(self.outcomes)

    @property
    def pass_rate(self) -> float:
        return sum(o.passed for o in self.outcomes) / max(1, self.n)

    @property
    def mean_score(self) -> float:
        return sum(o.score for o in self.outcomes) / max(1, self.n)

    def agg(self) -> dict:
        u = Usage()
        for o in self.outcomes:
            u.merge(o.usage)
        secs = sorted(o.seconds for o in self.outcomes)
        p95 = secs[int(0.95 * (len(secs) - 1))] if secs else 0.0
        return {
            "cases": self.n,
            "pass_rate": round(self.pass_rate, 3),
            "mean_score": round(self.mean_score, 3),
            "total_tokens": u.total_tokens,
            "mean_tokens": round(u.total_tokens / max(1, self.n), 1),
            "tool_calls": u.tool_calls,
            "tool_errors": u.tool_errors,
            "p95_latency_s": round(p95, 3),
        }

    def render(self) -> str:
        lines = ["=" * 60, "EVAL REPORT", "=" * 60]
        for o in self.outcomes:
            mark = "PASS" if o.passed else "FAIL"
            lines.append(f"[{mark}] {o.id:<14} score={o.score:.2f} "
                         f"iters={o.iterations} tok={o.usage.total_tokens} "
                         f"{o.seconds:.2f}s ({o.stop_reason})"
                         + (f" — {o.notes}" if o.notes else ""))
        a = self.agg()
        lines += ["-" * 60,
                  f"pass_rate={a['pass_rate']}  mean_score={a['mean_score']}  "
                  f"mean_tokens={a['mean_tokens']}  tool_errors={a['tool_errors']}  "
                  f"p95={a['p95_latency_s']}s",
                  "=" * 60]
        return "\n".join(lines)


def run_eval(
    make_loop: Callable[[], AgentLoop],
    cases: list[EvalCase],
    grader: Grader,
    *,
    split: Optional[str] = None,
) -> EvalReport:
    """
    make_loop: a factory returning a FRESH AgentLoop per case (clean state).
    grader:    how to decide pass/score from the output.
    split:     if set, only run cases with that split ("dev"/"test").
    """
    outcomes: list[CaseOutcome] = []
    for case in cases:
        if split is not None and case.split != split:
            continue
        loop = make_loop()
        t0 = time.time()
        result = loop.run(case.input)
        secs = time.time() - t0
        passed, score, notes = grader(result.output, case)
        outcomes.append(CaseOutcome(
            id=case.id, passed=passed, score=score, iterations=result.iterations,
            usage=result.usage, seconds=secs, stop_reason=result.stop_reason, notes=notes,
        ))
    return EvalReport(outcomes)


# --------------------------------------------------------------------------- #
# Dataset loading
# --------------------------------------------------------------------------- #

def load_jsonl(path: str | Path) -> list[EvalCase]:
    cases = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        d = json.loads(line)
        cases.append(EvalCase(
            id=d["id"], input=d["input"], expected=d.get("expected", ""),
            expected_tools=d.get("expected_tools", []),
            difficulty=d.get("difficulty", "simple"),
            split=d.get("split", "dev"), notes=d.get("notes", ""),
        ))
    return cases


# --------------------------------------------------------------------------- #
# Ready-made graders
# --------------------------------------------------------------------------- #

def exact_match(output: str, case: EvalCase) -> "tuple[bool, float, str]":
    ok = output.strip().lower() == case.expected.strip().lower()
    return (ok, 1.0 if ok else 0.0, "" if ok else "did not match expected")


def contains_all(output: str, case: EvalCase) -> "tuple[bool, float, str]":
    """Pass if output contains every '|'-separated phrase in `expected`."""
    needles = [s.strip().lower() for s in case.expected.split("|") if s.strip()]
    if not needles:
        return (bool(output.strip()), 1.0, "")
    hits = [n for n in needles if n in output.lower()]
    score = len(hits) / len(needles)
    missing = [n for n in needles if n not in output.lower()]
    return (score == 1.0, score, "" if not missing else f"missing: {missing}")


def make_judge_grader(provider, rubric: Optional[Rubric] = None, model: str = "") -> Grader:
    """LLM-as-judge grader using a Rubric. Provider may be the Mock for offline runs."""
    from harness.providers import Message
    from harness.verify import _parse_json
    rub = rubric or Rubric()

    def grade(output: str, case: EvalCase):
        prompt = rub.judge_prompt(case.input, output, case.expected)
        resp = provider.complete([Message("user", prompt)], model=model)
        data = _parse_json(resp.text) or {}
        scores = data.get("scores", {})
        res = rub.score(scores, data.get("notes", ""))
        return (res.passed, res.overall_score, res.notes)

    return grade
