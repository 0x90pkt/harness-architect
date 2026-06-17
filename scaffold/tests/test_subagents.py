import sys
import pathlib
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from harness import (  # noqa: E402
    HarnessConfig, MockProvider, LLMResponse, ToolCall,
    Tool, ToolRegistry, SideEffect, Orchestrator, SubAgentSpec,
)


def search(args):
    return f"result for {args['query']}"


search_tool = Tool(name="search", description="search", handler=search,
                   parameters={"type": "object",
                               "properties": {"query": {"type": "string"}},
                               "required": ["query"]},
                   side_effect=SideEffect.READ)


def policy(messages, meta):
    if "synthesis" in meta["system"].lower():
        task_msg = next((m.content for m in messages if m.role == "user"), "")
        n = task_msg.count("[Finding")
        return LLMResponse(text=f"SYNTHESIS of {n} findings")
    # worker
    if not any(m.role == "tool" for m in messages):
        return LLMResponse(tool_calls=[ToolCall("s", "search", {"query": "topic"})])
    res = next(m.content for m in messages if m.role == "tool")
    return LLMResponse(text=f"Summary: {res}")


class TestOrchestrator(unittest.TestCase):
    def test_parallel_read_single_synthesis(self):
        orch = Orchestrator(
            MockProvider(policy),
            worker_system_prompt="research worker",
            synthesis_system_prompt="synthesis agent",
            registry=ToolRegistry([search_tool]),
            config=HarnessConfig(max_iterations=5),
            max_parallel=3,
        )
        specs = [SubAgentSpec(objective=f"sub {i}") for i in range(3)]
        result = orch.run("overall task", specs)
        self.assertEqual(len(result.sub_results), 3)
        self.assertTrue(all("Summary" in s for s in result.sub_results))
        self.assertIn("SYNTHESIS of 3 findings", result.output)
        # multi-agent spends more than a single worker would
        self.assertGreater(result.usage.total_tokens, 0)
        self.assertGreaterEqual(result.usage.tool_calls, 3)


if __name__ == "__main__":
    unittest.main()
