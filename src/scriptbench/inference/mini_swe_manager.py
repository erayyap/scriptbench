from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from scriptbench.mini_swe_agent.agents.default import DefaultAgent
from scriptbench.mini_swe_agent.environments.local import LocalEnvironment
from scriptbench.mini_swe_agent.models.openai_model import OpenAIChatModel
from scriptbench.mini_swe_agent.utils.save import save_traj

from scriptbench.code_extraction import CodeExtractor
from scriptbench.inference.base import Submission
from scriptbench.task import Task


class MiniSWEInferenceManager:
    """Inference backend that runs the Mini SWE agent inside a scratch workspace."""

    SUBMISSION_FILENAME = "submission.md"

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        *,
        config_path: Optional[Path] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.code_extractor = CodeExtractor()
        default_config = Path(__file__).resolve().parent.parent / "config" / "mini_swe.yaml"
        self.config_path = config_path or default_config
        if not self.config_path.exists():
            raise FileNotFoundError(f"Mini SWE config not found at {self.config_path}")

    def produce_submission(self, task: Task, task_log_dir: Path) -> Submission:
        workspace = Path(tempfile.mkdtemp(prefix="scriptbench_miniswe_"))
        self.logger.info("Starting Mini SWE agent for task %s (workspace=%s)", task.task_path.stem, workspace)

        config = yaml.safe_load(self.config_path.read_text())
        model = self._initialise_model(config)
        environment = self._initialise_environment(config, workspace)
        agent = DefaultAgent(model, environment, **config.get("agent", {}))

        extra_template_vars = self._build_template_vars(task)

        exit_status: str
        result_text: str
        try:
            self.logger.info(f"Starting agent.run for task: {task.task_path.stem}")
            exit_status, result_text = agent.run(task.description, **extra_template_vars)
        except Exception:
            # Save trajectory even on failure for debugging
            self._persist_trajectory(agent, task_log_dir / "mini_swe_failed.traj.json")
            raise

        submission_path = workspace / self.SUBMISSION_FILENAME
        if not submission_path.exists():
            self._persist_trajectory(agent, task_log_dir / "mini_swe_missing_submission.traj.json")
            raise FileNotFoundError(
                f"Mini SWE agent completed without writing {self.SUBMISSION_FILENAME} in {workspace}"
            )

        submission_content = submission_path.read_text()
        apt_block, pip_block, script_block = self._extract_blocks(submission_content)

        pip_packages = self._parse_pip_packages(pip_block)
        apt_packages = self._parse_apt_packages(apt_block)
        try:
            script_content, script_path_rel = self._load_script_content(script_block, workspace)
        except Exception:
            self._persist_trajectory(agent, task_log_dir / "mini_swe_invalid_script_path.traj.json")
            raise

        trajectory_path = task_log_dir / "mini_swe.traj.json"
        self._persist_trajectory(agent, trajectory_path, exit_status=exit_status, result=result_text)

        metadata: Dict[str, Any] = {
            "mini_swe": {
                "exit_status": exit_status,
                "submission_result": result_text,
                "workspace": str(workspace),
                "trajectory_path": str(trajectory_path),
                "model_calls": agent.model.n_calls,
                "model_cost": agent.model.cost,
                "script_path": script_path_rel,
            },
            "submission_md": submission_content,
        }

        return Submission(
            apt_packages=apt_packages,
            pip_packages=pip_packages,
            script_content=script_content,
            metadata=metadata,
            raw_response=result_text,
            workspace_path=workspace,
        )

    def _initialise_model(self, config: Dict[str, Any]):
        model_config = dict(config.get("model", {}))

        model_name = model_config.pop("model_name", None)
        if not model_name:
            model_name = os.getenv("MINI_SWE_MODEL_NAME") or os.getenv("OPENAI_MODEL")
        if not model_name:
            raise RuntimeError("Mini SWE backend requires MINI_SWE_MODEL_NAME or OPENAI_MODEL to be set")

        if "temperature" not in model_config and (temp := os.getenv("OPENAI_TEMPERATURE")):
            try:
                model_config["temperature"] = float(temp)
            except ValueError:
                self.logger.warning("Ignoring invalid OPENAI_TEMPERATURE value: %s", temp)
        if "base_url" not in model_config:
            if base_url := os.getenv("OPENAI_BASE_URL_RUNNER") or os.getenv("OPENAI_BASE_URL"):
                model_config["base_url"] = base_url

        self.logger.info("Initializing OpenAIChatModel: %s with config: %s", model_name, model_config)
        return OpenAIChatModel(model_name=model_name, **model_config)

    def _initialise_environment(self, config: Dict[str, Any], workspace: Path):
        env_config = dict(config.get("env", config.get("environment", {})) or {})
        # Ensure commands execute inside the dedicated workspace
        env_config["cwd"] = str(workspace)
        return LocalEnvironment(**env_config)

    @staticmethod
    def _build_template_vars(task: Task) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "expected_result": task.expected_result,
            "expected_string": task.expected_string,
            "result_type": task.result_type,
            "difficulty": task.difficulty,
            "ground_truth_file": task.ground_truth_file,
            "task_folder": task.task_folder,
            "task_file": task.task_file,
            "script_file": task.script_file,
        }
        return data

    def _extract_blocks(self, submission_content: str) -> tuple[str, str, str]:
        pattern = re.compile(r"```(\w+)\s*\n(.*?)```", re.DOTALL)
        blocks: Dict[str, str] = {}
        for language, body in pattern.findall(submission_content):
            language_normalised = language.strip().lower()
            blocks[language_normalised] = body.strip()

        script_block = blocks.get("script") or blocks.get("python") or ""
        apt_block = blocks.get("apt", "")
        pip_block = blocks.get("pip", "")

        required_blocks = (("apt", apt_block), ("pip", pip_block), ("script", script_block))
        missing = [name for name, block in required_blocks if not block]
        if missing:
            raise ValueError(
                f"Mini SWE submission is missing code block(s): {', '.join(missing)}"
            )

        return apt_block, pip_block, script_block

    def _load_script_content(self, script_block: str, workspace: Path) -> tuple[str, str]:
        """Load script content from the path declared in the script block."""

        lines = [line.strip() for line in script_block.splitlines() if line.strip()]
        if not lines:
            raise ValueError("Mini SWE submission did not include a script path in the 'script' code block")

        script_path_value = lines[0]
        script_path = Path(script_path_value)
        if script_path.is_absolute():
            raise ValueError("Mini SWE script path must be relative to the workspace")

        resolved_path = (workspace / script_path).resolve()
        try:
            resolved_path.relative_to(workspace)
        except ValueError:
            raise ValueError("Mini SWE script path must resolve within the workspace directory")

        if not resolved_path.exists():
            raise FileNotFoundError(f"Mini SWE script path does not exist: {script_path_value}")
        if not resolved_path.is_file():
            raise ValueError(f"Mini SWE script path must point to a file: {script_path_value}")

        return resolved_path.read_text(), script_path_value

    def _parse_pip_packages(self, pip_block: str) -> list[str]:
        if not pip_block.strip() or pip_block.strip().lower() in {"none", "n/a"}:
            return []
        synthetic = f"```bash\n{pip_block}\n```"
        return self.code_extractor.extract_pip_packages(synthetic)

    def _parse_apt_packages(self, apt_block: str) -> list[str]:
        if not apt_block.strip() or apt_block.strip().lower() in {"none", "n/a"}:
            return []
        synthetic = f"```bash\n{apt_block}\n```"
        return self.code_extractor.extract_apt_packages(synthetic)

    def _persist_trajectory(
        self,
        agent: DefaultAgent,
        path: Path,
        *,
        exit_status: Optional[str] = None,
        result: Optional[str] = None,
    ) -> None:
        try:
            save_traj(agent, path, exit_status=exit_status, result=result)
            self.logger.info("Mini SWE trajectory saved to %s", path)
        except Exception as exc:  # pragma: no cover - best-effort telemetry
            self.logger.warning("Failed to save Mini SWE trajectory to %s: %s", path, exc)
