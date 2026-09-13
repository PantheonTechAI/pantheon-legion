"""Declared-capability tool broker used by the first Fabrica slice."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Protocol


class FabricaError(RuntimeError):
    """Base error for a rejected or failed tool invocation."""


class UnknownTool(FabricaError):
    """Raised when no declared tool owns the requested capability."""


@dataclass(frozen=True)
class ToolDefinition:
    """A declared tool capability and its execution-policy metadata."""

    capability: str
    side_effect_class: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    filesystem_policy: str = "none"
    network_policy: str = "none"
    credential_policy: str = "none"


@dataclass(frozen=True)
class ToolInvocation:
    """A correlated call presented to Fabrica after Aquila authorization."""

    invocation_id: str
    mission_id: str
    capability: str
    arguments: dict[str, Any]
    authorization_id: str
    correlation_id: str


@dataclass(frozen=True)
class ToolResult:
    """A correlated, structured result from a declared tool."""

    invocation_id: str
    capability: str
    output: dict[str, Any]


class ToolExecutionAdapter(Protocol):
    """Replaceable tool-broker contract; MCP and sandboxes sit behind it."""

    def resolve(self, capability: str) -> ToolDefinition: ...

    def invoke(self, invocation: ToolInvocation) -> ToolResult: ...


class InMemoryFabrica:
    """Reference broker that only invokes registered, declared capabilities."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if not definition.capability:
            raise FabricaError("TOOL_CAPABILITY_REQUIRED")
        if definition.side_effect_class not in {
            "READ", "MUTATION", "EXTERNAL_SIDE_EFFECT", "CREDENTIAL_USE", "PRODUCTION_ACCESS"
        }:
            raise FabricaError("TOOL_SIDE_EFFECT_CLASS_INVALID")
        if definition.capability in self._tools:
            raise FabricaError("TOOL_CAPABILITY_DUPLICATE")
        self._tools[definition.capability] = definition

    def resolve(self, capability: str) -> ToolDefinition:
        try:
            return self._tools[capability]
        except KeyError as exc:
            raise UnknownTool("TOOL_CAPABILITY_UNDECLARED") from exc

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        if not invocation.authorization_id or not invocation.correlation_id:
            raise FabricaError("TOOL_AUTHORIZATION_REQUIRED")
        definition = self.resolve(invocation.capability)
        output = definition.handler(deepcopy(invocation.arguments))
        if not isinstance(output, dict):
            raise FabricaError("TOOL_RESULT_INVALID")
        return ToolResult(
            invocation_id=invocation.invocation_id,
            capability=invocation.capability,
            output=deepcopy(output),
        )
