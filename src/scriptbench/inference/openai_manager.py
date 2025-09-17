from __future__ import annotations

import logging
import os
import random
import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from scriptbench.code_extraction import CodeExtractor
from scriptbench.inference.base import Submission
from scriptbench.task import Task


class OpenAIInferenceManager:
    """LangChain/OpenAI-backed inference manager."""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        *,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.code_extractor = CodeExtractor()

        model = os.getenv("OPENAI_MODEL", "gpt-4")
        temperature = os.getenv("OPENAI_TEMPERATURE")
        base_url = os.getenv("OPENAI_BASE_URL_RUNNER", "https://api.openai.com/v1")

        llm_kwargs: Dict[str, Any] = {"model": model, "base_url": base_url}
        if temperature is not None:
            llm_kwargs["temperature"] = float(temperature)

        self.llm = ChatOpenAI(**llm_kwargs)
        self.logger.info("LLM initialized: model=%s, temperature=%s, base_url=%s", model, temperature, base_url)

    def produce_submission(self, task: Task, task_log_dir) -> Submission:  # task_log_dir unused but kept for parity
        response, metadata = self._prompt_for_solution(task)

        pip_packages = self.code_extractor.extract_pip_packages(response)
        apt_packages = self.code_extractor.extract_apt_packages(response)
        script_content = self.code_extractor.extract_python_script(response)

        if not script_content:
            raise ValueError("No Python script found in LLM response")

        metadata.update(
            {
                "pip_packages_found": pip_packages,
                "apt_packages_found": apt_packages,
                "script_length": len(script_content),
            }
        )

        return Submission(
            apt_packages=apt_packages,
            pip_packages=pip_packages,
            script_content=script_content,
            metadata={"llm_interaction": metadata},
            raw_response=response,
        )

    def _prompt_for_solution(self, task: Task) -> Tuple[str, Dict[str, Any]]:
        prompt = self._build_prompt(task)

        self.logger.info("Prompting LLM for task: %s", task.task_path.stem)
        self.logger.debug("Prompt: %s", prompt)

        messages = [HumanMessage(content=prompt)]

        for attempt in range(self.max_retries + 1):
            try:
                start_time = datetime.now()
                response = self.llm.invoke(messages)
                end_time = datetime.now()

                llm_metadata = {
                    "prompt": prompt,
                    "response": response.content,
                    "model": self.llm.model_name,
                    "temperature": getattr(self.llm, "temperature", None),
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration_seconds": (end_time - start_time).total_seconds(),
                    "response_usage": getattr(response, "response_metadata", {}).get("token_usage", {}),
                    "retry_attempt": attempt,
                }

                self.logger.info(
                    "LLM response received in %.2fs (attempt %s)",
                    llm_metadata["duration_seconds"],
                    attempt + 1,
                )

                return response.content, llm_metadata

            except Exception as exc:  # broad catch to preserve existing behaviour
                self.logger.warning(
                    "LLM call failed on attempt %s/%s: %s",
                    attempt + 1,
                    self.max_retries + 1,
                    exc,
                )

                if attempt < self.max_retries:
                    delay = self.base_delay * (2**attempt) + random.uniform(0, 1)
                    self.logger.info("Retrying in %.2f seconds...", delay)
                    time.sleep(delay)
                else:
                    self.logger.error("LLM call failed after %s attempts", self.max_retries + 1)
                    raise

        raise RuntimeError("LLM call failed")  # Should not reach here

    @staticmethod
    def _build_prompt(task: Task) -> str:
        return f"""You are tasked with solving a programming problem. Please provide:

1. System package installation commands if needed (in a ```bash code block with apt-get)
2. A pip install command with required Python packages (in a ```bash code block with pip install)
3. A complete Python script to solve the problem (in a ```python code block)

Problem Description:
{task.description}

Please ensure your script can be run with \"python script.py\" and produces the exact output format specified.

Your response should contain (as needed):
```bash
# System packages (if needed)
sudo apt-get update && sudo apt-get install -y package1 package2
```

```bash
# Python packages
pip install package1 package2 package3
```

```python
# Your complete Python script here
```
"""
