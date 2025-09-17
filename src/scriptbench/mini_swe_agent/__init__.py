"""Minimal Mini-SWE agent primitives embedded in Scriptbench.

This module provides lightweight Protocol definitions that mirror the
behaviour of the upstream ``mini-swe-agent`` package.  Only the pieces that
Scriptbench relies on are implemented here so that we can vendor the agent
without depending on the external distribution.
"""

from __future__ import annotations

from typing import Any, Protocol


__all__ = [
    "Agent",
    "Environment",
    "Model",
    "__version__",
]


# Keep a version string for telemetry saved via ``save_traj``.
__version__ = "scriptbench-mini-swe-0.1"


class Model(Protocol):
    """Protocol for language models used by the Mini-SWE agent."""

    config: Any
    cost: float
    n_calls: int

    def query(self, messages: list[dict[str, str]], **kwargs) -> dict: ...

    def get_template_vars(self) -> dict[str, Any]: ...


class Environment(Protocol):
    """Protocol for execution environments used by the agent."""

    config: Any

    def execute(self, command: str, cwd: str = "", *, timeout: int | None = None) -> dict[str, Any]: ...

    def get_template_vars(self) -> dict[str, Any]: ...


class Agent(Protocol):
    """Protocol describing the behaviour of the Mini-SWE agent."""

    model: Model
    env: Environment
    messages: list[dict[str, str]]
    config: Any

    def run(self, task: str, **kwargs) -> tuple[str, str]: ...

