"""
Provider-agnostic agent harness — a minimal, dependency-light reference
implementation of the patterns in ../../reference/.

The whole point is portability: nothing here is tied to a specific model
provider or framework. Swap the provider, keep the harness.

Core pieces:
    providers   - LLM interface + Mock/Anthropic/OpenAI adapters
    tools       - Tool registry, schema validation, actionable errors, side-effect classes
    context     - Context manager: token budget, compaction, tool-result clearing
    memory      - File-backed memory (note-taking / progress file)
    verify      - Rule-based + LLM-as-judge verification
    observability - Structured tracing + token/cost accounting
    config      - Tiered model config
    loop        - The single-agent loop: gather -> act -> verify -> repeat
    subagents   - Orchestrator: parallel READ sub-agents + single-threaded synthesis
"""

from .providers import (
    LLMProvider,
    MockProvider,
    Message,
    ToolCall,
    LLMResponse,
    estimate_tokens,
)
from .tools import Tool, ToolRegistry, ToolResult, ToolError, SideEffect
from .context import ContextManager
from .memory import FileMemory
from .verify import (
    Verifier,
    RuleVerifier,
    LLMJudgeVerifier,
    CompositeVerifier,
    VerificationResult,
)
from .observability import Tracer, Usage, estimate_cost
from .config import HarnessConfig, ModelTier
from .loop import AgentLoop, RunResult
from .subagents import Orchestrator, SubAgentSpec

__all__ = [
    "LLMProvider",
    "MockProvider",
    "Message",
    "ToolCall",
    "LLMResponse",
    "estimate_tokens",
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "ToolError",
    "SideEffect",
    "ContextManager",
    "FileMemory",
    "Verifier",
    "RuleVerifier",
    "LLMJudgeVerifier",
    "CompositeVerifier",
    "VerificationResult",
    "Tracer",
    "Usage",
    "estimate_cost",
    "HarnessConfig",
    "ModelTier",
    "AgentLoop",
    "RunResult",
    "Orchestrator",
    "SubAgentSpec",
]
