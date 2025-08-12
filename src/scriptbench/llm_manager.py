import os
import logging
import time
import random
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

from .task import Task


class LLMManager:
    def __init__(self, logger: Optional[logging.Logger] = None, max_retries: int = 3, base_delay: float = 1.0):
        from langchain_core.messages import HumanMessage
        from langchain_openai import ChatOpenAI
        
        self.logger = logger or logging.getLogger(__name__)
        self.max_retries = max_retries
        self.base_delay = base_delay
        
        model = os.getenv("OPENAI_MODEL", "gpt-4")
        temperature = os.getenv("OPENAI_TEMPERATURE")
        base_url = os.getenv("OPENAI_BASE_URL_RUNNER", "https://api.openai.com/v1")
        
        llm_kwargs = {"model": model, "base_url": base_url}
        if temperature is not None:
            llm_kwargs["temperature"] = float(temperature)
        
        self.llm = ChatOpenAI(**llm_kwargs)
        self.HumanMessage = HumanMessage
        
        self.logger.info(f"LLM initialized: model={model}, temperature={temperature}, base_url={base_url}")
    
    def prompt_for_solution(self, task: Task) -> Tuple[str, Dict[str, Any]]:
        prompt = self._build_prompt(task)
        
        self.logger.info(f"Prompting LLM for task: {task.task_path.stem}")
        self.logger.debug(f"Prompt: {prompt}")
        
        messages = [self.HumanMessage(content=prompt)]
        
        for attempt in range(self.max_retries + 1):
            try:
                start_time = datetime.now()
                response = self.llm.invoke(messages)
                end_time = datetime.now()
                
                llm_metadata = {
                    "prompt": prompt,
                    "response": response.content,
                    "model": self.llm.model_name,
                    "temperature": getattr(self.llm, 'temperature', None),
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration_seconds": (end_time - start_time).total_seconds(),
                    "response_usage": getattr(response, 'response_metadata', {}).get('token_usage', {}),
                    "retry_attempt": attempt
                }
                
                self.logger.info(f"LLM response received in {llm_metadata['duration_seconds']:.2f}s (attempt {attempt + 1})")
                
                return response.content, llm_metadata
                
            except Exception as e:
                self.logger.warning(f"LLM call failed on attempt {attempt + 1}/{self.max_retries + 1}: {str(e)}")
                
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
                    self.logger.info(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    self.logger.error(f"LLM call failed after {self.max_retries + 1} attempts")
                    raise e
    
    def _build_prompt(self, task: Task) -> str:
        return f"""You are tasked with solving a programming problem. Please provide:

1. System package installation commands if needed (in a ```bash code block with apt-get)
2. A pip install command with required Python packages (in a ```bash code block with pip install)
3. A complete Python script to solve the problem (in a ```python code block)

Problem Description:
{task.description}

Please ensure your script can be run with "python script.py" and produces the exact output format specified.

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