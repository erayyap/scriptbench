import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import logging

from .task import Task
from .execution import ScriptExecutor, WindowsScriptExecutor, UnixScriptExecutor
from .evaluation import NumericalEvaluator, ClassificationEvaluator, ScriptRunEvaluator


class Evaluator:
    """Main evaluator class that coordinates script execution and result evaluation."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.timeout = int(os.getenv("SCRIPT_TIMEOUT", "60"))
        self._executor = self._create_executor()
        self._evaluators = {
            "numerical": NumericalEvaluator(self.logger),
            "classification_match": ClassificationEvaluator(self.logger),
            "script_run": ScriptRunEvaluator(self.timeout, self.logger)
        }
    
    def _create_executor(self) -> ScriptExecutor:
        """Create platform-specific script executor."""
        if sys.platform == "win32":
            return WindowsScriptExecutor(self.timeout, self.logger)
        else:
            return UnixScriptExecutor(self.timeout, self.logger)
    
    def run_script(self, script_path: Path, venv_path: Path, work_dir: Path) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Run a script using the platform-specific executor."""
        python_path = self._executor.get_python_path(venv_path)
        
        # Validate paths exist before execution
        if not python_path.exists():
            error = FileNotFoundError(f"Python interpreter not found: {python_path}")
            self.logger.error(str(error))
            return self._handle_validation_error([], work_dir, error)
        
        if not script_path.exists():
            error = FileNotFoundError(f"Script file not found: {script_path}")
            self.logger.error(str(error))
            return self._handle_validation_error([], work_dir, error)
        
        cmd = [str(python_path), str(script_path)]
        self.logger.info(f"Running script command: {' '.join(cmd)}")
        
        start_time = datetime.now()
        
        try:
            return self._executor.execute(cmd, work_dir, start_time)
        except Exception as e:
            self.logger.error(f"Unexpected error during script execution: {e}")
            return self._handle_execution_error(cmd, work_dir, start_time, e)
    
    def _handle_validation_error(self, cmd, work_dir: Path, error: Exception) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Handle validation errors that occur before execution."""
        return self._handle_execution_error(cmd, work_dir, datetime.now(), error)
    
    def _handle_execution_error(self, cmd, work_dir: Path, start_time: datetime, error: Exception) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Handle execution errors consistently."""
        end_time = datetime.now()
        execution_metadata = {
            "command": cmd,
            "working_directory": str(work_dir),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "return_code": None,
            "timeout": self.timeout,
            "success": False,
            "error": str(error)
        }
        return False, "", f"Script execution failed: {str(error)}", execution_metadata
    
    @staticmethod
    def evaluate_numerical_result(output: str, expected: int, logger: Optional[logging.Logger] = None) -> Tuple[bool, Dict[str, Any]]:
        """Legacy method for backward compatibility."""
        evaluator = NumericalEvaluator(logger)
        # Create a mock task object with the expected result
        class MockTask:
            def __init__(self, expected_result):
                self.expected_result = expected_result
        
        task = MockTask(expected)
        return evaluator.evaluate(task, output)
    
    @staticmethod
    def evaluate_classification_match(task: Task, work_dir: Path) -> Tuple[bool, Dict[str, Any]]:
        """Legacy method for backward compatibility."""
        evaluator = ClassificationEvaluator()
        return evaluator.evaluate(task, work_dir=work_dir)
    
    
    @staticmethod
    def evaluate_result(task: Task, output: str, work_dir: Path = None, logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
        """Evaluate task results using appropriate evaluator based on result type."""
        eval_logger = logger or logging.getLogger(__name__)
        evaluation = {
            "task_name": task.task_path.stem,
            "difficulty": task.difficulty,
            "result_type": task.result_type,
            "success": False,
            "output": output
        }
        
        # Create evaluator instance for accessing specialized evaluators
        evaluator_instance = Evaluator(eval_logger)
        
        if task.result_type == "numerical" and task.expected_result is not None:
            success, numerical_details = evaluator_instance._evaluators["numerical"].evaluate(task, output)
            evaluation["success"] = success
            evaluation["expected"] = task.expected_result
            evaluation["numerical_details"] = numerical_details
            
        elif task.result_type == "classification_match" and work_dir is not None:
            success, classification_details = evaluator_instance._evaluators["classification_match"].evaluate(task, work_dir=work_dir)
            evaluation["success"] = success
            evaluation["classification_details"] = classification_details
            
            # Add detailed logging for classification evaluation
            if success:
                eval_logger.info(f"Classification evaluation PASSED for task '{task.task_path.stem}'")
            else:
                error_msg = classification_details.get("error", "Unknown classification error")
                eval_logger.warning(f"Classification evaluation FAILED for task '{task.task_path.stem}': {error_msg}")
                
        elif task.result_type == "script_run" and work_dir is not None:
            success, script_run_details = evaluator_instance._evaluators["script_run"].evaluate(task, work_dir=work_dir)
            evaluation["success"] = success
            evaluation["script_run_details"] = script_run_details
            
            # Add detailed logging for script_run evaluation
            if success:
                eval_logger.info(f"Script run evaluation PASSED for task '{task.task_path.stem}'")
            else:
                error_msg = script_run_details.get("error", "Unknown script_run error")
                eval_logger.warning(f"Script run evaluation FAILED for task '{task.task_path.stem}': {error_msg}")
        
        return evaluation