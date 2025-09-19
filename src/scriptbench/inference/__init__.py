from __future__ import annotations

from pathlib import Path
from typing import Optional

from scriptbench.inference.base import InferenceManager, Submission
from scriptbench.inference.openai_manager import OpenAIInferenceManager

try:
    from scriptbench.inference.mini_swe_manager import MiniSWEInferenceManager
    from scriptbench.mini_swe_agent.agents.iterative import IterativeAgent
except Exception:  # pragma: no cover - optional dependency during partial installs
    MiniSWEInferenceManager = None  # type: ignore


def create_inference_manager(
    backend: str,
    *,
    logger=None,
    task_files_dir: Optional[Path] = None,
    agent_files_dir: Optional[Path] = None,
) -> InferenceManager:
    backend_normalized = backend.strip().lower()
    match backend_normalized:
        case "openai" | "default":
            return OpenAIInferenceManager(logger=logger)
        case "mini-swe":
            if MiniSWEInferenceManager is None:
                raise RuntimeError("Mini SWE backend not available; ensure dependencies are installed.")
            return MiniSWEInferenceManager(
                logger=logger,
                task_files_dir=task_files_dir,
                agent_files_dir=agent_files_dir,
            )
        case "mini-swe-iter":
            if MiniSWEInferenceManager is None:
                raise RuntimeError("Mini SWE backend not available; ensure dependencies are installed.")
            config_path = Path(__file__).resolve().parent.parent / "config" / "mini_swe_iter.yaml"
            return MiniSWEInferenceManager(
                logger=logger,
                config_path=config_path,
                agent_class=IterativeAgent,
                backend_metadata_key="mini_swe_iter",
                task_files_dir=task_files_dir,
                agent_files_dir=agent_files_dir,
            )
        case other:
            raise ValueError(
                f"Unknown inference backend '{other}'. Supported backends: openai, mini-swe, mini-swe-iter"
            )


__all__ = ["InferenceManager", "Submission", "create_inference_manager"]
