import sys
import pathlib
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from harness import AgentLoop, MockProvider, LLMResponse  # noqa: E402
from evals.runner import (  # noqa: E402
    EvalCase, run_eval, contains_all, exact_match, load_jsonl, make_judge_grader,
)
from evals.rubric import Rubric  # noqa: E402


class TestEval(unittest.TestCase):
    def test_run_eval_contains_all(self):
        provider = MockProvider(lambda m, meta: LLMResponse(text="apple banana cherry"))
        make_loop = lambda: AgentLoop(provider, "sys")
        cases = [
            EvalCase("c1", "q", "apple|banana"),
            EvalCase("c2", "q", "mango"),
        ]
        report = run_eval(make_loop, cases, contains_all)
        self.assertEqual(report.n, 2)
        self.assertAlmostEqual(report.pass_rate, 0.5)
        agg = report.agg()
        self.assertIn("mean_tokens", agg)

    def test_exact_match(self):
        ok, score, _ = exact_match("Hello", EvalCase("c", "q", "hello"))
        self.assertTrue(ok)
        self.assertEqual(score, 1.0)

    def test_split_filter(self):
        provider = MockProvider(lambda m, meta: LLMResponse(text="x"))
        make_loop = lambda: AgentLoop(provider, "sys")
        cases = [EvalCase("a", "q", "x", split="dev"),
                 EvalCase("b", "q", "x", split="test")]
        dev = run_eval(make_loop, cases, contains_all, split="dev")
        self.assertEqual(dev.n, 1)

    def test_load_jsonl_skips_comments(self):
        ds = pathlib.Path(__file__).resolve().parents[1] / "evals" / "datasets" / "example_tasks.jsonl"
        cases = load_jsonl(ds)
        self.assertGreaterEqual(len(cases), 6)
        self.assertEqual(cases[0].id, "pack-paris-1")
        # both splits present
        self.assertTrue(any(c.split == "test" for c in cases))

    def test_judge_grader(self):
        good_json = ('{"scores": {"factual_accuracy": 1.0, "completeness": 1.0, '
                     '"citation_accuracy": 1.0, "source_quality": 1.0, '
                     '"tool_efficiency": 1.0}, "notes": "great"}')
        provider = MockProvider(lambda m, meta: LLMResponse(text=good_json))
        grader = make_judge_grader(provider, Rubric())
        passed, score, notes = grader("some answer", EvalCase("c", "task", "expected"))
        self.assertTrue(passed)
        self.assertAlmostEqual(score, 1.0)
        self.assertEqual(notes, "great")


if __name__ == "__main__":
    unittest.main()
