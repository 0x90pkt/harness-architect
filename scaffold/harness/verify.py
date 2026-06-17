"""
Verification — the reliability multiplier.

Layer the cheapest sufficient check first:
  1. RuleVerifier      - deterministic predicates (schema/format/business rules).
  2. (environment)     - run/query/diff/screenshot happens inside your tools.
  3. LLMJudgeVerifier  - fuzzy criteria only (tone, completeness), via a rubric.

CompositeVerifier runs them in order and stops at the first failure, so you don't
pay for an LLM judge when a cheap rule already caught the problem.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

from .providers import LLMProvider, Message


@dataclass
class VerificationResult:
    passed: bool
    score: float = 1.0
    feedback: str = ""
    detail: dict = field(default_factory=dict)


class Verifier(Protocol):
    def verify(self, output: str, task: str) -> VerificationResult: ...


# Rule = (name, predicate). predicate(output, task) -> (ok: bool, message: str)
Rule = tuple[str, Callable[[str, str], "tuple[bool, str]"]]


class RuleVerifier:
    def __init__(self, rules: list[Rule]):
        self.rules = rules

    def verify(self, output: str, task: str) -> VerificationResult:
        failures = []
        for name, pred in self.rules:
            ok, msg = pred(output, task)
            if not ok:
                failures.append(f"- {name}: {msg}")
        if failures:
            return VerificationResult(
                passed=False,
                score=1.0 - len(failures) / max(1, len(self.rules)),
                feedback="Verification failed:\n" + "\n".join(failures),
                detail={"failures": failures},
            )
        return VerificationResult(True, 1.0, "All rules passed.")


class LLMJudgeVerifier:
    """
    A single-call LLM judge against a rubric. Returns a 0..1 score and pass/fail.
    Keep it for fuzzy criteria; don't over-trust it (it adds latency and cost).
    """

    def __init__(self, provider: LLMProvider, *, model: str = "",
                 dimensions: Optional[list[str]] = None, threshold: float = 0.7):
        self.provider = provider
        self.model = model
        self.dimensions = dimensions or [
            "accuracy", "completeness", "relevance", "safety"
        ]
        self.threshold = threshold

    def verify(self, output: str, task: str) -> VerificationResult:
        rubric = ", ".join(self.dimensions)
        prompt = (
            "You are grading an agent's output. Be strict but fair; do not "
            "penalize valid alternative phrasings or formatting.\n"
            f"TASK:\n{task}\n\nAGENT OUTPUT:\n{output}\n\n"
            f"Score each dimension ({rubric}) from 0.0 to 1.0. Then return ONLY "
            'JSON: {"scores": {dim: float, ...}, "overall_score": float, '
            '"pass": bool, "notes": "short justification"}.'
        )
        resp = self.provider.complete([Message("user", prompt)], model=self.model)
        data = _parse_json(resp.text)
        if data is None:
            # Fail closed but explain — a malformed judge response is itself a signal.
            return VerificationResult(False, 0.0,
                                      "Judge returned unparseable output.",
                                      {"raw": resp.text})
        score = float(data.get("overall_score", 0.0))
        passed = bool(data.get("pass", score >= self.threshold))
        return VerificationResult(passed, score, data.get("notes", ""), data)


class CompositeVerifier:
    def __init__(self, verifiers: list[Verifier]):
        self.verifiers = verifiers

    def verify(self, output: str, task: str) -> VerificationResult:
        worst: Optional[VerificationResult] = None
        for v in self.verifiers:
            r = v.verify(output, task)
            if not r.passed:
                return r  # stop at first failure (cheap-first ordering)
            worst = r if worst is None or r.score < worst.score else worst
        return worst or VerificationResult(True, 1.0, "No verifiers configured.")


def _parse_json(text: str) -> Optional[dict]:
    text = text.strip()
    # tolerate code fences / surrounding prose
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


# ---- handy ready-made rules ------------------------------------------------ #

def rule_nonempty() -> Rule:
    return ("non_empty", lambda out, _t: (bool(out.strip()), "output is empty"))


def rule_contains(substr: str, *, case_insensitive: bool = True) -> Rule:
    def pred(out: str, _t: str):
        hay = out.lower() if case_insensitive else out
        needle = substr.lower() if case_insensitive else substr
        return (needle in hay, f"output must mention '{substr}'")
    return (f"contains[{substr}]", pred)


def rule_max_words(n: int) -> Rule:
    return (f"max_words[{n}]",
            lambda out, _t: (len(out.split()) <= n, f"output exceeds {n} words"))


def rule_valid_json() -> Rule:
    def pred(out: str, _t: str):
        try:
            json.loads(out)
            return (True, "")
        except json.JSONDecodeError as e:
            return (False, f"not valid JSON: {e}")
    return ("valid_json", pred)
