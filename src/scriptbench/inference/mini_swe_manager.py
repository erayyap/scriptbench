from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import tempfile
import venv
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


BASE_PIP_PACKAGE_NAMES = {"pip", "setuptools", "wheel"}


class CommandTracker:
    """Lightweight tracker for commands issued by the agent."""

    def __init__(self) -> None:
        self._history: list[tuple[str, int | None]] = []

    def record(self, command: str, result: dict[str, Any]) -> None:
        self._history.append((command, result.get("returncode")))

    def apt_packages(self) -> list[str]:
        packages: set[str] = set()
        for command, returncode in self._history:
            if returncode not in (0, None):
                continue
            packages |= self._extract_apt_packages_from_command(command)
        return sorted(packages)

    def _extract_apt_packages_from_command(self, command: str) -> set[str]:
        packages: set[str] = set()
        for subcommand in re.split(r"\s*(?:&&|;|\|\|)\s*", command):
            subcommand = subcommand.strip()
            if not subcommand:
                continue
            try:
                tokens = shlex.split(subcommand)
            except ValueError:
                continue
            parsed = self._parse_apt_tokens(tokens)
            if parsed:
                packages |= parsed
        return packages

    def _parse_apt_tokens(self, tokens: list[str]) -> set[str]:
        if not tokens:
            return set()

        idx = 0
        while idx < len(tokens) and tokens[idx] not in {"apt", "apt-get"}:
            idx += 1

        if idx >= len(tokens):
            return set()

        idx += 1
        if idx >= len(tokens) or tokens[idx] != "install":
            return set()

        idx += 1
        packages: set[str] = set()
        while idx < len(tokens):
            token = tokens[idx]
            if token.startswith("-"):
                idx += 1
                continue
            packages.add(token)
            idx += 1
        return packages


class TrackingEnvironment(LocalEnvironment):
    """Local environment wrapper that records executed commands."""

    def __init__(self, *, tracker: CommandTracker, **kwargs):
        super().__init__(**kwargs)
        self._tracker = tracker

    def execute(self, command: str, cwd: str = "", *, timeout: int | None = None) -> dict[str, Any]:
        result = super().execute(command, cwd, timeout=timeout)
        try:
            self._tracker.record(command, result)
        finally:
            return result


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

        venv_path = self._create_workspace_venv(workspace)
        pip_baseline = self._pip_freeze(venv_path)
        command_tracker = CommandTracker()

        config = yaml.safe_load(self.config_path.read_text())
        model = self._initialise_model(config)
        environment = self._initialise_environment(config, workspace, venv_path, command_tracker)
        agent = DefaultAgent(model, environment, **config.get("agent", {}))

        extra_template_vars = self._build_template_vars(task, workspace, venv_path)

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
        blocks = self._extract_submission_blocks(submission_content)
        script_block = blocks.get("script") or blocks.get("python") or ""

        detected_pip_packages = self._compute_new_pip_packages(venv_path, pip_baseline)
        detected_apt_packages = command_tracker.apt_packages()

        pip_packages = self._merge_unique(
            detected_pip_packages,
            self._parse_pip_packages(blocks.get("pip", "")),
        )
        apt_packages = self._merge_unique(
            detected_apt_packages,
            self._parse_apt_packages(blocks.get("apt", "")),
        )

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
                "pip_packages_detected": detected_pip_packages,
                "apt_packages_detected": detected_apt_packages,
                "venv_path": str(venv_path),
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

    def _initialise_environment(
        self,
        config: Dict[str, Any],
        workspace: Path,
        venv_path: Path,
        tracker: CommandTracker,
    ) -> TrackingEnvironment:
        env_config = dict(config.get("env", config.get("environment", {})) or {})
        env_vars = dict(env_config.get("env", {}))
        env_vars = self._apply_venv_to_env(venv_path, env_vars)
        env_config["env"] = env_vars
        env_config["cwd"] = str(workspace)
        return TrackingEnvironment(tracker=tracker, **env_config)

    def _build_template_vars(self, task: Task, workspace: Path, venv_path: Path) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "expected_result": task.expected_result,
            "expected_string": task.expected_string,
            "result_type": task.result_type,
            "difficulty": task.difficulty,
            "ground_truth_file": task.ground_truth_file,
            "task_folder": task.task_folder,
            "task_file": task.task_file,
            "script_file": task.script_file,
            "mini_swe_workspace": str(workspace),
            "mini_swe_workspace_venv": str(venv_path),
            "mini_swe_workspace_python": str(self._venv_python_path(venv_path)),
            "mini_swe_workspace_pip": str(self._venv_pip_path(venv_path)),
        }
        return data

    def _extract_submission_blocks(self, submission_content: str) -> Dict[str, str]:
        pattern = re.compile(r"```(\w+)\s*\n(.*?)```", re.DOTALL)
        blocks: Dict[str, str] = {}
        for language, body in pattern.findall(submission_content):
            language_normalised = language.strip().lower()
            blocks[language_normalised] = body.strip()

        if not (blocks.get("script") or blocks.get("python")):
            raise ValueError("Mini SWE submission is missing a 'script' code block")

        return blocks

    def _create_workspace_venv(self, workspace: Path) -> Path:
        venv_path = workspace / "venv"
        self.logger.info("Creating virtual environment for Mini SWE workspace at %s", venv_path)
        try:
            # `symlinks=True` is required on POSIX when the Python distribution lives
            # outside the workspace (as with uv toolchains); copying the launcher
            # without its shared library causes the embedded ensurepip step to fail.
            builder = venv.EnvBuilder(
                with_pip=True,
                clear=False,
                symlinks=(os.name != "nt"),
            )
            builder.create(venv_path)
        except Exception:
            # Surface the error but include context in the log first
            self.logger.exception("Failed to create virtual environment in %s", venv_path)
            raise
        return venv_path

    def _apply_venv_to_env(self, venv_path: Path, base_env: dict[str, str]) -> dict[str, str]:
        env = dict(base_env)
        bin_path = self._venv_bin_path(venv_path)
        existing_path = env.get("PATH") or os.getenv("PATH", "")
        path_parts = [str(bin_path)]
        if existing_path:
            path_parts.append(existing_path)
        env["PATH"] = os.pathsep.join(path_parts)
        env["VIRTUAL_ENV"] = str(venv_path)
        env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
        return env

    def _venv_bin_path(self, venv_path: Path) -> Path:
        return venv_path / ("Scripts" if os.name == "nt" else "bin")

    def _venv_python_path(self, venv_path: Path) -> Path:
        return self._venv_bin_path(venv_path) / ("python.exe" if os.name == "nt" else "python")

    def _venv_pip_path(self, venv_path: Path) -> Path:
        return self._venv_bin_path(venv_path) / ("pip.exe" if os.name == "nt" else "pip")

    def _pip_freeze(self, venv_path: Path) -> list[str]:
        python_executable = self._venv_python_path(venv_path)
        env = os.environ | self._apply_venv_to_env(venv_path, {})
        try:
            result = subprocess.run(
                [str(python_executable), "-m", "pip", "freeze", "--local"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            self.logger.warning("pip freeze failed in Mini SWE workspace: %s", exc)
            if exc.stdout:
                self.logger.debug("pip freeze stdout: %s", exc.stdout)
            if exc.stderr:
                self.logger.debug("pip freeze stderr: %s", exc.stderr)
            return []

        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _compute_new_pip_packages(self, venv_path: Path, baseline: list[str]) -> list[str]:
        baseline_set = set(baseline)
        final_state = self._pip_freeze(venv_path)
        detected: list[str] = []
        seen: set[str] = set()

        for entry in final_state:
            if entry in baseline_set or entry in seen:
                continue
            normalised = self._normalise_pip_name(entry)
            if normalised in BASE_PIP_PACKAGE_NAMES:
                continue
            detected.append(entry)
            seen.add(entry)

        return detected

    @staticmethod
    def _merge_unique(primary: list[str], secondary: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for item in list(primary) + list(secondary):
            if not item or item in seen:
                continue
            merged.append(item)
            seen.add(item)
        return merged

    @staticmethod
    def _normalise_pip_name(entry: str) -> str:
        if "==" in entry:
            return entry.split("==", 1)[0].strip().lower()
        if " @ " in entry:
            return entry.split(" @ ", 1)[0].strip().lower()
        return entry.strip().lower()

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
