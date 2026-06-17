"""
Weighted rubric scoring for LLM-as-judge grading.

Anthropic's research eval used a single judge call returning per-dimension scores
plus an overall pass/fail. This mirrors that: define weighted dimensions, compute
a weighted overall score, and pass/fail against a threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RubricResult:
    overall_score: float
    passed: bool
    scores: dict[str, float] = field(default_factory=dict)
    notes: str = ""


@dataclass
class Rubric:
    # dimension -> weight (weights are normalized automatically)
    dimensions: dict[str, float] = field(default_factory=lambda: {
        "factual_accuracy": 1.0,
        "completeness": 1.0,
        "citation_accuracy": 1.0,
        "source_quality": 0.5,
        "tool_efficiency": 0.5,
    })
    threshold: float = 0.7

    def score(self, dimension_scores: dict[str, float], notes: str = "") -> RubricResult:
        total_w = sum(self.dimensions.values()) or 1.0
        overall = 0.0
        for dim, weight in self.dimensions.items():
            overall += dimension_scores.get(dim, 0.0) * (weight / total_w)
        return RubricResult(
            overall_score=round(overall, 4),
            passed=overall >= self.threshold,
            scores=dimension_scores,
            notes=notes,
        )

    def judge_prompt(self, task: str, output: str, expected: str = "") -> str:
        dims = ", ".join(self.dimensions)
        exp = f"\nGROUND TRUTH / EXPECTATIONS:\n{expected}\n" if expected else ""
        return (
            "You are grading an agent's output against a rubric. Be strict but "
            "fair; do not penalize valid alternative phrasings or formatting.\n"
            f"TASK:\n{task}\n{exp}\nAGENT OUTPUT:\n{output}\n\n"
            f"Score each dimension ({dims}) from 0.0 to 1.0. Return ONLY JSON:\n"
            '{"scores": {dim: float, ...}, "notes": "one-line justification"}'
        )
