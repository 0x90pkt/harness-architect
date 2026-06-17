import sys
import pathlib
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from harness.context import ContextManager  # noqa: E402
from harness.providers import Message, MockProvider, LLMResponse  # noqa: E402


class TestContext(unittest.TestCase):
    def test_used_tokens_and_fraction(self):
        ctx = ContextManager(token_budget=100)
        ctx.add(Message("user", "x" * 400))  # ~100 tokens
        self.assertGreaterEqual(ctx.used_tokens(), 90)
        self.assertGreaterEqual(ctx.fraction_used(), 0.9)

    def test_should_compact(self):
        ctx = ContextManager(token_budget=100, compaction_threshold=0.8)
        self.assertFalse(ctx.should_compact())
        ctx.add(Message("user", "x" * 400))
        self.assertTrue(ctx.should_compact())

    def test_clear_old_tool_results(self):
        ctx = ContextManager(clear_tool_results_after=2)
        for i in range(5):
            ctx.add(Message("tool", "big result " * 50, tool_call_id=f"c{i}"))
        cleared = ctx.clear_old_tool_results()
        self.assertEqual(cleared, 3)  # 5 - 2 kept
        cleared_msgs = [m for m in ctx.messages if m.content.startswith("[cleared")]
        self.assertEqual(len(cleared_msgs), 3)

    def test_compact_summarizes_and_keeps_recent(self):
        provider = MockProvider(lambda msgs, meta: LLMResponse(text="SUMMARY"))
        ctx = ContextManager(keep_recent=2)
        for i in range(6):
            ctx.add(Message("user", f"msg {i}"))
        ctx.compact(provider, system="sys", model="m")
        self.assertEqual(len(ctx.messages), 2)        # kept recent
        rendered = ctx.render()
        self.assertTrue(any("SUMMARY" in m.content for m in rendered))
        self.assertEqual(rendered[-1].content, "msg 5")

    def test_compact_noop_when_small(self):
        provider = MockProvider(lambda msgs, meta: LLMResponse(text="SUMMARY"))
        ctx = ContextManager(keep_recent=6)
        ctx.add(Message("user", "only one"))
        ctx.compact(provider, system="", model="")
        self.assertEqual(len(ctx.messages), 1)


if __name__ == "__main__":
    unittest.main()
