from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from scriptbench.task import Task


@dataclass
class Submission:
    """Artifacts produced by an inference backend."""

    apt_packages: list[str]
    pip_packages: list[str]
    script_content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_response: str | None = None
    workspace_path: Path | None = None


class InferenceManager(Protocol):
    """Protocol for LLM/code-generation backends."""

    def produce_submission(self, task: Task, task_log_dir: Path) -> Submission:
        """Generate solution artifacts for the given task."""
        ...
