"""Local execution environment for the Mini-SWE agent."""

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class LocalEnvironmentConfig:
    cwd: str = ""
    env: dict[str, str] = field(default_factory=dict)
    timeout: int = 30


class LocalEnvironment:
    """Execute commands directly on the host machine using ``subprocess``."""

    def __init__(self, *, config_class: type = LocalEnvironmentConfig, **kwargs):
        self.config = config_class(**kwargs)

    def execute(self, command: str, cwd: str = "", *, timeout: int | None = None) -> dict[str, Any]:
        resolved_cwd = cwd or self.config.cwd or os.getcwd()
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            cwd=resolved_cwd,
            env=os.environ | self.config.env,
            timeout=timeout or self.config.timeout,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return {"output": result.stdout, "returncode": result.returncode}

    def get_template_vars(self) -> dict[str, Any]:
        return asdict(self.config) | platform.uname()._asdict() | os.environ

