from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import logging

from ..task import Task


class BaseEvaluator(ABC):
    """Abstract base class for task evaluators."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
    
    @abstractmethod
    def evaluate(self, task: Task, output: str = "", work_dir: Optional[Path] = None) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate the task results and return (success, details)."""
        pass