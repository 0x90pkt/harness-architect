"""
Worked example #1 — a single, tiered agent (the common case).

A "packing assistant": given a destination, it calls a weather tool, then gives
packing advice. It demonstrates: the gather->act->verify loop, a well-specified
tool, rule-based verification, tracing, and running an eval set.

Runs fully offline on MockProvider. To use a real model, swap the provider (see
the bottom of this file) — nothing else changes.

    python examples/run_single_agent.py
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from harness import (  # noqa: E402
    AgentLoop, HarnessConfig, ModelTier, MockProvider, LLMResponse, ToolCall,
    Tool, ToolRegistry, SideEffect, RuleVerifier,
)
from harness.verify import rule_contains  # noqa: E402
from evals.runner import load_jsonl, run_eval, contains_all  # noqa: E402


# --- the tool ------------------------------------------------------------- #
WEATHER = {
    "paris": "12°C and rainy",
    "cairo": "35°C and sunny",
    "oslo": "-3°C and snowy",
}


def get_weather(args: dict) -> str:
    city = args["city"].strip().lower()
    if city not in WEATHER:
        # actionable error: tells the model exactly what's valid
        from harness import ToolError
        raise ToolError(f"no data for '{city}'. Known cities: {', '.join(sorted(WEATHER))}.")
    return f"Current weather in {args['city'].title()}: {WEATHER[city]}."


weather_tool = Tool(
    name="get_weather",
    description="Get current weather for a city. Use before giving packing advice.",
    handler=get_weather,
    parameters={
        "type": "object",
        "properties": {"city": {"type": "string", "description": "City name, e.g. 'Paris'"}},
        "required": ["city"],
        "additionalProperties": False,
    },
    side_effect=SideEffect.READ,
)


# --- the model behavior (mock) -------------------------------------------- #
def policy(messages, meta):
    """gather (call weather) -> act -> then answer using the result."""
    has_weather = any(m.role == "tool" and not m.content.startswith("ERROR") for m in messages)
    if not has_weather:
        text = " ".join(m.content for m in messages if m.role == "user").lower()
        city = next((c for c in WEATHER if c in text), "paris")
        return LLMResponse(tool_calls=[ToolCall(id="wc1", name="get_weather",
                                                arguments={"city": city.title()})])
    weather = next(m.content for m in messages if m.role == "tool")
    answer = (f"{weather} You should pack: "
              + ("an umbrella and a light jacket." if "rain" in weather.lower()
                 else "sunscreen, sunglasses and light clothes." if "sun" in weather.lower()
                 else "a heavy coat, gloves and warm boots."))
    return LLMResponse(text=answer)


SYSTEM_PROMPT = """You are a concise travel packing assistant.
Process: call get_weather for the destination, then give specific packing advice
that references the temperature. Keep it to 1-2 sentences."""


def build_loop() -> AgentLoop:
    provider = MockProvider(policy)
    registry = ToolRegistry([weather_tool])
    config = HarnessConfig(max_iterations=6)
    # verification: the answer must reference temperature (°C) and packing
    verifier = RuleVerifier([rule_contains("°C"), rule_contains("pack")])
    return AgentLoop(provider, SYSTEM_PROMPT, registry, config,
                     tier=ModelTier.BALANCED, verifier=verifier)


def main():
    print("--- single run ---")
    result = build_loop().run("What should I pack for a trip to Paris?")
    print("output:", result.output)
    print("success:", result.success, "| iters:", result.iterations,
          "| tokens:", result.usage.total_tokens, "| stop:", result.stop_reason)

    print("\n--- eval (dev split) ---")
    ds = pathlib.Path(__file__).resolve().parents[1] / "evals" / "datasets" / "example_tasks.jsonl"
    cases = load_jsonl(ds)
    report = run_eval(build_loop, cases, contains_all, split="dev")
    print(report.render())

    print("\n--- eval (held-out test split) ---")
    report_test = run_eval(build_loop, cases, contains_all, split="test")
    print(report_test.render())


if __name__ == "__main__":
    main()


# --- swapping in a real provider ------------------------------------------ #
# from harness.providers import AnthropicProvider
# provider = AnthropicProvider()                  # needs ANTHROPIC_API_KEY
# config = HarnessConfig(models={
#     ModelTier.FRONTIER: "<current-frontier-model>",   # ⚠ verify current names
#     ModelTier.BALANCED: "<current-balanced-model>",
#     ModelTier.FAST:     "<current-fast-model>",
# })
# loop = AgentLoop(provider, SYSTEM_PROMPT, ToolRegistry([weather_tool]), config)
