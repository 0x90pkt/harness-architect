import sys
import pathlib
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from harness import (  # noqa: E402
    AgentLoop, HarnessConfig, ModelTier, MockProvider, LLMResponse, ToolCall,
    Tool, ToolRegistry, SideEffect, RuleVerifier,
)
from harness.verify import rule_contains  # noqa: E402


def make_tool(name="get_thing", side=SideEffect.READ):
    return Tool(name=name, description="get a thing",
                handler=lambda a: "the thing is 42",
                parameters={"type": "object", "properties": {}},
                side_effect=side)


class TestLoop(unittest.TestCase):
    def test_tool_then_answer(self):
        def policy(messages, meta):
            if not any(m.role == "tool" for m in messages):
                return LLMResponse(tool_calls=[ToolCall("c", "get_thing", {})])
            return LLMResponse(text="The answer is 42.")
        loop = AgentLoop(MockProvider(policy), "sys", ToolRegistry([make_tool()]),
                         HarnessConfig(max_iterations=5))
        r = loop.run("what is the thing?")
        self.assertTrue(r.success)
        self.assertEqual(r.stop_reason, "done")
        self.assertIn("42", r.output)
        self.assertEqual(r.usage.tool_calls, 1)
        self.assertGreaterEqual(r.usage.llm_calls, 2)

    def test_verification_retry_then_pass(self):
        def policy(messages, meta):
            has_tool = any(m.role == "tool" for m in messages)
            retried = any("did not pass verification" in m.content for m in messages)
            if not has_tool:
                return LLMResponse(tool_calls=[ToolCall("c", "get_thing", {})])
            if not retried:
                return LLMResponse(text="incomplete answer")  # missing 'pack'
            return LLMResponse(text="here is the pack list")  # passes
        loop = AgentLoop(MockProvider(policy), "sys", ToolRegistry([make_tool()]),
                         HarnessConfig(max_iterations=6, max_verify_retries=2),
                         verifier=RuleVerifier([rule_contains("pack")]))
        r = loop.run("make a packing list")
        self.assertTrue(r.success)
        self.assertIn("pack", r.output)
        # exactly one retry happened
        self.assertEqual(len([e for e in r.trace if e["type"] == "verify"]), 2)

    def test_verification_exhausts_retries(self):
        def policy(messages, meta):
            return LLMResponse(text="never contains the word")
        loop = AgentLoop(MockProvider(policy), "sys", config=HarnessConfig(max_verify_retries=1),
                         verifier=RuleVerifier([rule_contains("pack")]))
        r = loop.run("make a packing list")
        self.assertFalse(r.success)
        self.assertEqual(r.stop_reason, "verification_failed")

    def test_max_iterations_stop(self):
        def policy(messages, meta):
            return LLMResponse(tool_calls=[ToolCall("c", "get_thing", {})])  # never finishes
        loop = AgentLoop(MockProvider(policy), "sys", ToolRegistry([make_tool()]),
                         HarnessConfig(max_iterations=3))
        r = loop.run("loop forever")
        self.assertFalse(r.success)
        self.assertEqual(r.stop_reason, "max_iterations")
        self.assertEqual(r.iterations, 3)

    def test_destructive_tool_denied_in_loop(self):
        def policy(messages, meta):
            if not any(m.role == "tool" for m in messages):
                return LLMResponse(tool_calls=[ToolCall("c", "delete_all", {})])
            return LLMResponse(text="could not delete; done")
        loop = AgentLoop(MockProvider(policy), "sys",
                         ToolRegistry([make_tool("delete_all", SideEffect.DESTRUCTIVE)]),
                         HarnessConfig(max_iterations=5))
        r = loop.run("delete everything")
        tool_events = [e for e in r.trace if e["type"] == "tool"]
        self.assertTrue(tool_events[0]["is_error"])
        self.assertEqual(r.usage.tool_errors, 1)

    def test_partial_model_config_falls_back(self):
        # Only FRONTIER configured; requesting FAST must not KeyError.
        captured = {}

        def policy(messages, meta):
            captured["model"] = meta["model"]
            return LLMResponse(text="ok")
        cfg = HarnessConfig(models={ModelTier.FRONTIER: "F"})
        r = AgentLoop(MockProvider(policy), "sys", config=cfg, tier=ModelTier.FAST).run("hi")
        self.assertTrue(r.success)
        self.assertEqual(captured["model"], "F")  # fell back to the only model

    def test_tier_selects_model(self):
        captured = {}

        def policy(messages, meta):
            captured["model"] = meta["model"]
            return LLMResponse(text="ok")
        cfg = HarnessConfig(models={ModelTier.FRONTIER: "F", ModelTier.BALANCED: "B",
                                    ModelTier.FAST: "S"})
        AgentLoop(MockProvider(policy), "sys", config=cfg, tier=ModelTier.FAST).run("hi")
        self.assertEqual(captured["model"], "S")


if __name__ == "__main__":
    unittest.main()
