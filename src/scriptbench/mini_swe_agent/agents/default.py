"""Vendored implementation of the default Mini-SWE agent."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass

from jinja2 import StrictUndefined, Template

from scriptbench.mini_swe_agent import Environment, Model


@dataclass
class AgentConfig:
    """Configurable prompt templates and limits for the agent."""

    system_template: str = "You are a helpful assistant that can do anything."
    instance_template: str = (
        "Your task: {{task}}. Please reply with a single shell command in triple backticks. "
        "To finish, the first line of the output of the shell command must be 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'."
    )
    timeout_template: str = (
        "The last command <command>{{action['action']}}</command> timed out and has been killed.\n"
        "The output of the command was:\n <output>\n{{output}}\n</output>\n"
        "Please try another command and make sure to avoid those requiring interactive input."
    )
    format_error_template: str = "Please always provide EXACTLY ONE action in triple backticks."
    action_observation_template: str = "Observation: {{output}}"
    step_limit: int = 0
    cost_limit: float = 3.0
    minimum_iterations: int = 0


class NonTerminatingException(Exception):
    """Raised for conditions that the agent can recover from."""


class FormatError(NonTerminatingException):
    """Raised when the model output does not contain a single bash block."""


class ExecutionTimeoutError(NonTerminatingException):
    """Raised when the executed action times out."""


class TerminatingException(Exception):
    """Raised for conditions that stop the agent entirely."""


class Submitted(TerminatingException):
    """Raised when the model signals that the task is complete."""


class LimitsExceeded(TerminatingException):
    """Raised when the configured step or cost limits have been hit."""


class DefaultAgent:
    """Reimplementation of the original ``DefaultAgent`` with minimal dependencies."""

    def __init__(self, model: Model, env: Environment, *, config_class: Callable = AgentConfig, **kwargs):
        self.config = config_class(**kwargs)
        self.messages: list[dict] = []
        self.model = model
        self.env = env
        self.extra_template_vars: dict[str, str] = {}

    # === Core control flow ==================================================

    def render_template(self, template: str, **kwargs) -> str:
        template_vars = asdict(self.config) | self.env.get_template_vars() | self.model.get_template_vars()
        return Template(template, undefined=StrictUndefined).render(
            **kwargs, **template_vars, **self.extra_template_vars
        )

    def add_message(self, role: str, content: str, **kwargs) -> None:
        self.messages.append({"role": role, "content": content, **kwargs})

    def run(self, task: str, **kwargs) -> tuple[str, str]:
        """Run ``step`` repeatedly until the agent terminates."""

        self.extra_template_vars |= {"task": task, **kwargs}
        self.messages = []
        self.add_message("system", self.render_template(self.config.system_template))
        self.add_message("user", self.render_template(self.config.instance_template))
        while True:
            try:
                self.step()
            except NonTerminatingException as exc:
                self.add_message("user", str(exc))
            except TerminatingException as exc:
                self.add_message("user", str(exc))
                return type(exc).__name__, str(exc)

    def step(self) -> dict:
        """Query the model, execute the action, and return the observation."""

        return self.get_observation(self.query())

    def query(self) -> dict:
        """Query the model and record the assistant message."""

        if 0 < self.config.step_limit <= self.model.n_calls or 0 < self.config.cost_limit <= self.model.cost:
            raise LimitsExceeded()
        response = self.model.query(self.messages)
        self.add_message("assistant", **response)
        return response

    def get_observation(self, response: dict) -> dict:
        """Execute the parsed action and store the observation."""

        output = self.execute_action(self.parse_action(response))
        observation = self.render_template(self.config.action_observation_template, output=output)
        self.add_message("user", observation)
        return output

    # === Action parsing & execution ========================================

    def parse_action(self, response: dict) -> dict:
        """Extract a single bash action from the model output."""

        actions = re.findall(r"```bash\s*\n(.*?)\n```", response["content"], re.DOTALL)
        if len(actions) == 1:
            return {"action": actions[0].strip(), **response}
        raise FormatError(self.render_template(self.config.format_error_template, actions=actions))

    def execute_action(self, action: dict) -> dict:
        try:
            output = self.env.execute(action["action"])
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - depends on runtime
            stdout = exc.output.decode("utf-8", errors="replace") if exc.output else ""
            raise ExecutionTimeoutError(self.render_template(self.config.timeout_template, action=action, output=stdout))
        except TimeoutError:  # pragma: no cover - defensive
            raise ExecutionTimeoutError(self.render_template(self.config.timeout_template, action=action, output=""))
        self._check_finished(output)
        return output

    def _check_finished(self, output: dict[str, str]) -> None:
        lines = output.get("output", "").lstrip().splitlines(keepends=True)
        if lines and lines[0].strip().upper() in {
            "MINI_SWE_AGENT_FINAL_OUTPUT",
            "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT",
            "END",
        }:
            raise Submitted("".join(lines[1:]))
