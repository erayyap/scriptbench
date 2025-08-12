import re
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from .base import BaseEvaluator
from ..task import Task


class NumericalEvaluator(BaseEvaluator):
    """Evaluates numerical results by extracting and comparing answers."""
    
    def evaluate(self, task: Task, output: str = "", work_dir: Optional[Path] = None) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate numerical task results."""
        if task.expected_result is None:
            return False, {"error": "No expected result specified for numerical evaluation"}
        
        answer_pattern = r'ANSWER=(\d+(?:\.\d+)?)'
        match = re.search(answer_pattern, output)
        
        evaluation_details = {
            "expected_answer": task.expected_result,
            "pattern_used": answer_pattern,
            "extraction_successful": False,
            "extracted_answer": None,
            "comparison_result": False
        }
        
        if match:
            try:
                actual = float(match.group(1))
                evaluation_details["extraction_successful"] = True
                evaluation_details["extracted_answer"] = actual
                evaluation_details["comparison_result"] = abs(actual - float(task.expected_result)) < 1e-9
                
                if abs(actual - float(task.expected_result)) < 1e-9:
                    self.logger.info(f"Numerical evaluation PASSED: extracted answer {actual} matches expected {task.expected_result}")
                    return True, evaluation_details
                else:
                    self.logger.warning(f"Numerical evaluation FAILED: extracted answer {actual} does not match expected {task.expected_result}")
                    return False, evaluation_details
            except ValueError as e:
                self.logger.error(f"Numerical evaluation FAILED: could not convert extracted value '{match.group(1)}' to number: {e}")
                evaluation_details["error"] = f"Value conversion error: {str(e)}"
                return False, evaluation_details
        else:
            self.logger.error(f"Numerical evaluation FAILED: no answer found matching pattern '{answer_pattern}' in output. Output content: {repr(output[:200])}{'...' if len(output) > 200 else ''}")
            evaluation_details["error"] = "No answer pattern found in output"
            return False, evaluation_details