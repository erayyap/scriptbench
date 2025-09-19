from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import venv
from pathlib import Path
from typing import Any, Dict, Optional, Type

import yaml

from scriptbench.mini_swe_agent.agents.default import DefaultAgent
from scriptbench.mini_swe_agent.environments.local import LocalEnvironment
from scriptbench.mini_swe_agent.models.openai_model import OpenAIChatModel
from scriptbench.mini_swe_agent.utils.save import save_traj

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

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        *,
        config_path: Optional[Path] = None,
        agent_class: Type[DefaultAgent] = DefaultAgent,
        backend_metadata_key: str = "mini_swe",
        task_files_dir: Optional[Path] = None,
        agent_files_dir: Optional[Path] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        default_config = Path(__file__).resolve().parent.parent / "config" / "mini_swe.yaml"
        self.config_path = config_path or default_config
        if not self.config_path.exists():
            raise FileNotFoundError(f"Mini SWE config not found at {self.config_path}")
        self.agent_class = agent_class
        self.backend_metadata_key = backend_metadata_key
        self._minimum_iterations: Optional[int] = None
        self.task_files_dir = self._resolve_directory(task_files_dir, "SCRIPTBENCH_FILES_DIR", "files")
        self.agent_files_dir = self._resolve_directory(agent_files_dir, "SCRIPTBENCH_AGENT_FILES_DIR", "files_agent")

    def produce_submission(self, task: Task, task_log_dir: Path) -> Submission:
        workspace = Path(tempfile.mkdtemp(prefix="scriptbench_miniswe_"))
        self.logger.info(
            "Starting %s agent for task %s (workspace=%s)",
            self.backend_metadata_key,
            task.task_path.stem,
            workspace,
        )

        preloaded_assets = self._prepare_agent_environment(task, workspace)

        venv_path = self._create_workspace_venv(workspace)
        pip_baseline = self._pip_freeze(venv_path)
        command_tracker = CommandTracker()

        config = yaml.safe_load(self.config_path.read_text())
        config = self._apply_env_overrides(config)
        model = self._initialise_model(config)
        environment = self._initialise_environment(config, workspace, venv_path, command_tracker)
        agent = self.agent_class(model, environment, **config.get("agent", {}))

        extra_template_vars = self._build_template_vars(task, workspace, venv_path, preloaded_assets)

        exit_status: str
        result_text: str
        try:
            self.logger.info(f"Starting agent.run for task: {task.task_path.stem}")
            exit_status, result_text = agent.run(task.description, **extra_template_vars)
        except Exception:
            # Save trajectory even on failure for debugging
            self._persist_trajectory(agent, task_log_dir / f"{self.backend_metadata_key}_failed.traj.json")
            raise

        detected_pip_packages = self._compute_new_pip_packages(venv_path, pip_baseline)
        detected_apt_packages = command_tracker.apt_packages()

        try:
            script_content, script_path_rel = self._load_script_content(result_text, workspace)
        except Exception:
            self._persist_trajectory(
                agent,
                task_log_dir / f"{self.backend_metadata_key}_invalid_script_path.traj.json",
            )
            raise

        trajectory_path = task_log_dir / f"{self.backend_metadata_key}.traj.json"
        self._persist_trajectory(agent, trajectory_path, exit_status=exit_status, result=result_text)

        pip_packages = detected_pip_packages
        apt_packages = detected_apt_packages

        metadata: Dict[str, Any] = {
            self.backend_metadata_key: {
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
            "mini_swe_variant": self.backend_metadata_key,
            "submission_message": result_text,
        }

        if preloaded_assets.get("files") or preloaded_assets.get("folders"):
            variant_metadata = metadata[self.backend_metadata_key]
            if preloaded_assets.get("files"):
                variant_metadata["preloaded_files"] = preloaded_assets["files"]
            if preloaded_assets.get("folders"):
                variant_metadata["preloaded_folders"] = preloaded_assets["folders"]

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
        if self._minimum_iterations is not None:
            env_vars.setdefault("MINI_SWE_MINIMUM_ITERATIONS", str(self._minimum_iterations))
            env_vars.setdefault("SCRIPTBENCH_MINI_SWE_MIN_ITERATIONS", str(self._minimum_iterations))
        env_config["env"] = env_vars
        env_config["cwd"] = str(workspace)
        return TrackingEnvironment(tracker=tracker, **env_config)

    def _prepare_agent_environment(self, task: Task, workspace: Path) -> Dict[str, list[str]]:
        assets: Dict[str, list[str]] = {"files": [], "folders": []}

        if task.task_file:
            copied = self._copy_resource_file(self.task_files_dir, task.task_file, workspace)
            if copied and copied not in assets["files"]:
                assets["files"].append(copied)

        if task.agent_env.has_assets():
            if not self.agent_files_dir:
                self.logger.warning(
                    "Agent environment assets requested, but no agent files directory configured."
                )
            else:
                for relative_file in task.agent_env.files:
                    copied = self._copy_resource_file(self.agent_files_dir, relative_file, workspace)
                    if copied and copied not in assets["files"]:
                        assets["files"].append(copied)
                for relative_folder in task.agent_env.folders:
                    copied = self._copy_resource_folder(self.agent_files_dir, relative_folder, workspace)
                    if copied and copied not in assets["folders"]:
                        assets["folders"].append(copied)

        return assets

    def _copy_resource_file(
        self,
        base_dir: Optional[Path],
        relative_path: str,
        workspace: Path,
    ) -> Optional[str]:
        if base_dir is None:
            return None

        source = self._safe_join(base_dir, relative_path)
        if source is None:
            return None
        if not source.exists():
            self.logger.warning("Agent resource file does not exist: %s", source)
            return None
        if not source.is_file():
            self.logger.warning("Expected file but found non-file resource: %s", source)
            return None

        destination = workspace / source.name
        if destination.exists():
            self.logger.warning(
                "Overwriting existing agent file in workspace: %s (source=%s)",
                destination,
                source,
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        self.logger.info("Loaded agent file into workspace: %s -> %s", source, destination)
        return str(destination.relative_to(workspace))

    def _copy_resource_folder(
        self,
        base_dir: Optional[Path],
        relative_path: str,
        workspace: Path,
    ) -> Optional[str]:
        if base_dir is None:
            return None

        source = self._safe_join(base_dir, relative_path)
        if source is None:
            return None
        if not source.exists():
            self.logger.warning("Agent resource folder does not exist: %s", source)
            return None
        if not source.is_dir():
            self.logger.warning("Expected folder but found non-directory resource: %s", source)
            return None

        destination = workspace / source.relative_to(base_dir)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, dirs_exist_ok=True)
        self.logger.info("Loaded agent folder into workspace: %s -> %s", source, destination)
        return str(destination.relative_to(workspace))

    def _safe_join(self, base_dir: Optional[Path], relative_path: str) -> Optional[Path]:
        if base_dir is None:
            return None
        cleaned = self._normalise_relative_path(relative_path)
        if not cleaned:
            return None

        candidate = (base_dir / cleaned).resolve()
        try:
            candidate.relative_to(base_dir)
        except ValueError:
            self.logger.warning("Ignoring agent asset outside base directory: %s", candidate)
            return None
        return candidate

    @staticmethod
    def _normalise_relative_path(relative_path: str) -> Path:
        return Path(relative_path.lstrip("/"))

    def _resolve_directory(
        self,
        configured: Optional[Path],
        env_var: str,
        default_value: str,
    ) -> Optional[Path]:
        if configured:
            return Path(configured).resolve()
        env_value = os.getenv(env_var)
        if env_value:
            return Path(env_value).resolve()
        return Path(default_value).resolve()

    def _build_template_vars(
        self,
        task: Task,
        workspace: Path,
        venv_path: Path,
        assets: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        assets = assets or {}
        loaded_files = list(assets.get("files", []))
        loaded_folders = list(assets.get("folders", []))
        data: Dict[str, Any] = {
            "expected_result": task.expected_result,
            "expected_string": task.expected_string,
            "result_type": task.result_type,
            "difficulty": task.difficulty,
            "ground_truth_file": task.ground_truth_file,
            "task_folder": task.task_folder,
            "task_file": task.task_file,
            "script_file": task.script_file,
            "mini_swe_variant": self.backend_metadata_key,
            "mini_swe_workspace": str(workspace),
            "mini_swe_workspace_venv": str(venv_path),
            "mini_swe_workspace_python": str(self._venv_python_path(venv_path)),
            "mini_swe_workspace_pip": str(self._venv_pip_path(venv_path)),
            "mini_swe_loaded_files": loaded_files,
            "mini_swe_loaded_folders": loaded_folders,
            "mini_swe_has_loaded_assets": bool(loaded_files or loaded_folders),
        }
        return data

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        self._minimum_iterations = None
        agent_config = dict(config.get("agent", {}))

        env_value = os.getenv("SCRIPTBENCH_MINI_SWE_MIN_ITERATIONS") or os.getenv(
            "MINI_SWE_MINIMUM_ITERATIONS"
        )
        if env_value is not None:
            try:
                minimum = max(0, int(env_value))
            except ValueError:
                self.logger.warning(
                    "Ignoring invalid MINI_SWE_MINIMUM_ITERATIONS value: %s", env_value
                )
            else:
                agent_config["minimum_iterations"] = minimum
                self.logger.info(
                    "Overriding agent minimum_iterations via environment to %s", minimum
                )
                self._minimum_iterations = minimum

        if self._minimum_iterations is None:
            value = agent_config.get("minimum_iterations")
            if isinstance(value, int):
                self._minimum_iterations = value
            else:
                try:
                    self._minimum_iterations = int(value)
                except (TypeError, ValueError):
                    self._minimum_iterations = None

        if agent_config:
            config["agent"] = agent_config

        return config

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
    def _normalise_pip_name(entry: str) -> str:
        if "==" in entry:
            return entry.split("==", 1)[0].strip().lower()
        if " @ " in entry:
            return entry.split(" @ ", 1)[0].strip().lower()
        return entry.strip().lower()

    def _load_script_content(self, script_block: str, workspace: Path) -> tuple[str, str]:
        """Load script content from the path declared in the final message."""

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
