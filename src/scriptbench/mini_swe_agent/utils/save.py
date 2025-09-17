"""Utility helpers for persisting Mini-SWE agent trajectories."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scriptbench.mini_swe_agent import Agent, __version__


def _get_class_name_with_module(obj: Any) -> str:
    return f"{obj.__class__.__module__}.{obj.__class__.__name__}"


def _asdict(obj: Any) -> dict:
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)  # type: ignore[arg-type]
    return obj


def save_traj(
    agent: Agent | None,
    path: Path,
    *,
    print_path: bool = True,
    exit_status: str | None = None,
    result: str | None = None,
    extra_info: dict | None = None,
    print_fct: Callable = print,
    **kwargs,
):
    """Persist the agent trajectory for later inspection."""

    data = {
        "info": {
            "exit_status": exit_status,
            "submission": result,
            "model_stats": {
                "instance_cost": 0.0,
                "api_calls": 0,
            },
            "mini_version": __version__,
        },
        "messages": [],
        "trajectory_format": "mini-swe-agent-1",
    } | kwargs
    if agent is not None:
        data["info"]["model_stats"]["instance_cost"] = getattr(agent.model, "cost", 0.0)
        data["info"]["model_stats"]["api_calls"] = getattr(agent.model, "n_calls", 0)
        data["messages"] = agent.messages
        data["info"]["config"] = {
            "agent": _asdict(agent.config),
            "model": _asdict(agent.model.config),
            "environment": _asdict(agent.env.config),
            "agent_type": _get_class_name_with_module(agent),
            "model_type": _get_class_name_with_module(agent.model),
            "environment_type": _get_class_name_with_module(agent.env),
        }
    if extra_info:
        data["info"].update(extra_info)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    if print_path:
        print_fct(f"Saved trajectory to '{path}'")

