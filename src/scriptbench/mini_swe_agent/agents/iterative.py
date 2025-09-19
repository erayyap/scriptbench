"""Iterative variant of the Mini-SWE agent that enforces a minimum step count."""

from __future__ import annotations

from dataclasses import dataclass

from scriptbench.mini_swe_agent.agents.default import (
    AgentConfig,
    DefaultAgent,
    NonTerminatingException,
    Submitted,
)


class MinimumIterationsNotReached(NonTerminatingException):
    """Raised when the agent attempts to finish before the minimum steps."""


@dataclass
class IterativeAgentConfig(AgentConfig):
    """Configuration for the iterative agent variant."""

    minimum_iterations: int = 5
    early_submission_template: str = (
        "You attempted to end on step {{current_step}}, but you must complete at least "
        "{{minimum_steps}} steps. {{steps_remaining}} more step(s) are required before "
        "you may emit the completion signal."
    )


class IterativeAgent(DefaultAgent):
    """Mini-SWE agent that must complete a fixed number of steps before stopping."""

    config: IterativeAgentConfig

    def __init__(self, model, env, *, config_class=IterativeAgentConfig, **kwargs):
        super().__init__(model, env, config_class=config_class, **kwargs)
        self._step_index = 0

    def run(self, task: str, **kwargs):
        self._step_index = 0
        minimum = max(0, getattr(self.config, "minimum_iterations", 0))
        self.extra_template_vars = {
            "minimum_steps": minimum,
            "current_step": 0,
            "steps_remaining": minimum,
            "next_step": 1,
        }
        return super().run(task, **kwargs)

    def step(self):
        self._step_index += 1
        self._update_iteration_vars()
        return super().step()

    def _update_iteration_vars(self) -> None:
        minimum = max(0, getattr(self.config, "minimum_iterations", 0))
        remaining = max(minimum - self._step_index, 0)
        self.extra_template_vars |= {
            "minimum_steps": minimum,
            "current_step": self._step_index,
            "steps_remaining": remaining,
            "next_step": self._step_index + 1,
        }

    def _check_finished(self, output):  # type: ignore[override]
        lines = output.get("output", "").lstrip().splitlines(keepends=True)
        if not lines:
            return

        header = lines[0].strip().upper()
        if header in {"MINI_SWE_AGENT_FINAL_OUTPUT", "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT", "END"}:
            minimum = max(0, getattr(self.config, "minimum_iterations", 0))
            if self._step_index < minimum:
                template = getattr(self.config, "early_submission_template", "") or (
                    "You must complete at least {{minimum_steps}} steps before finishing."
                )
                message = self.render_template(
                    template,
                    submitted_output="".join(lines[1:]),
                )
                raise MinimumIterationsNotReached(message)
            raise Submitted("".join(lines[1:]))
