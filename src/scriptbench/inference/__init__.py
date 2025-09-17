from __future__ import annotations

from typing import Optional

from scriptbench.inference.base import InferenceManager, Submission
from scriptbench.inference.openai_manager import OpenAIInferenceManager

try:
    from scriptbench.inference.mini_swe_manager import MiniSWEInferenceManager
except Exception:  # pragma: no cover - optional dependency during partial installs
    MiniSWEInferenceManager = None  # type: ignore


def create_inference_manager(
    backend: str,
    *,
    logger=None,
) -> InferenceManager:
    backend_normalized = backend.strip().lower()
    match backend_normalized:
        case "openai" | "default":
            return OpenAIInferenceManager(logger=logger)
        case "mini-swe":
            if MiniSWEInferenceManager is None:
                raise RuntimeError("Mini SWE backend not available; ensure dependencies are installed.")
            return MiniSWEInferenceManager(logger=logger)
        case other:
            raise ValueError(f"Unknown inference backend '{other}'. Supported backends: openai, mini-swe")


__all__ = ["InferenceManager", "Submission", "create_inference_manager"]
