import re
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from .base import BaseEvaluator
from ..task import Task


class StringAnswerEvaluator(BaseEvaluator):
    """Evaluates string answer results by extracting and comparing exact string matches."""
    
    def evaluate(self, task: Task, output: str = "", work_dir: Optional[Path] = None) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate string answer task results."""
        if task.expected_string is None:
            return False, {"error": "No expected_string specified for string_answer evaluation"}
        
        # Support both simple strings and quoted strings
        # Pattern matches: ANSWER=word or ANSWER="quoted string" or ANSWER='quoted string'
        answer_pattern = r'ANSWER=(["\']?)([^"\'\n\r]+?)\1(?:\s|$)'
        match = re.search(answer_pattern, output)
        
        evaluation_details = {
            "expected_answer": task.expected_string,
            "pattern_used": answer_pattern,
            "extraction_successful": False,
            "extracted_answer": None,
            "comparison_result": False,
            "case_sensitive": getattr(task, 'case_sensitive', True)
        }
        
        if match:
            extracted_string = match.group(2).strip()
            evaluation_details["extraction_successful"] = True
            evaluation_details["extracted_answer"] = extracted_string
            
            # Perform comparison (case-sensitive by default)
            case_sensitive = getattr(task, 'case_sensitive', True)
            if case_sensitive:
                matches = extracted_string == task.expected_string
            else:
                matches = extracted_string.lower() == task.expected_string.lower()
            
            evaluation_details["comparison_result"] = matches
            
            if matches:
                self.logger.info(f"String answer evaluation PASSED: extracted answer '{extracted_string}' matches expected '{task.expected_string}'")
                return True, evaluation_details
            else:
                self.logger.warning(f"String answer evaluation FAILED: extracted answer '{extracted_string}' does not match expected '{task.expected_string}'")
                return False, evaluation_details
        else:
            # Try a simpler pattern for unquoted strings
            simple_pattern = r'ANSWER=([^\s\n\r]+)'
            simple_match = re.search(simple_pattern, output)
            
            if simple_match:
                extracted_string = simple_match.group(1).strip()
                evaluation_details["extraction_successful"] = True
                evaluation_details["extracted_answer"] = extracted_string
                evaluation_details["pattern_used"] = simple_pattern
                
                case_sensitive = getattr(task, 'case_sensitive', True)
                if case_sensitive:
                    matches = extracted_string == task.expected_string
                else:
                    matches = extracted_string.lower() == task.expected_string.lower()
                
                evaluation_details["comparison_result"] = matches
                
                if matches:
                    self.logger.info(f"String answer evaluation PASSED: extracted answer '{extracted_string}' matches expected '{task.expected_string}'")
                    return True, evaluation_details
                else:
                    self.logger.warning(f"String answer evaluation FAILED: extracted answer '{extracted_string}' does not match expected '{task.expected_string}'")
                    return False, evaluation_details
            else:
                self.logger.error(f"String answer evaluation FAILED: no answer found matching pattern in output. Output content: {repr(output[:200])}{'...' if len(output) > 200 else ''}")
                evaluation_details["error"] = "No answer pattern found in output"
                return False, evaluation_details