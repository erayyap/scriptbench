import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from .base import BaseEvaluator
from ..task import Task
import logging


class ScriptRunEvaluator(BaseEvaluator):
    """Evaluates script_run results by running checker scripts."""
    
    def __init__(self, timeout: int = 60, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.timeout = timeout
    
    def evaluate(self, task: Task, output: str = "", work_dir: Optional[Path] = None) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate script_run task results."""
        if not work_dir:
            return False, {"error": "work_dir is required for script_run evaluation"}
        
        if not task.script_file:
            return False, {"error": "Missing script_file in task configuration"}
        
        # The script file is copied to root of work_dir without folder structure
        script_file_path = work_dir / Path(task.script_file).name
        
        if not script_file_path.exists():
            return False, {"error": f"Script file not found: {script_file_path}"}
        
        try:
            # Get the python path from the venv in work_dir
            venv_path = work_dir / "venv"
            python_path = self._get_python_path(venv_path)
            
            if not python_path.exists():
                return False, {"error": f"Python interpreter not found: {python_path}"}
            
            # Run the checker script
            cmd = [str(python_path), str(script_file_path)]
            self.logger.info(f"Running checker script: {' '.join(cmd)}")
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=work_dir
                )
                
                stdout = result.stdout.strip() if result.stdout else ""
                stderr = result.stderr.strip() if result.stderr else ""
                
                # Log the output for debugging
                if stdout:
                    self.logger.info(f"Checker script stdout: {stdout}")
                if stderr:
                    self.logger.info(f"Checker script stderr: {stderr}")
                
                # Check if the script printed exactly "TRUE"
                success = stdout == "TRUE"
                
                evaluation_details = {
                    "script_file": str(script_file_path),
                    "return_code": result.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "success_condition": "stdout == 'TRUE'",
                    "condition_met": success
                }
                
                if success:
                    self.logger.info(f"Script run evaluation PASSED: checker script printed 'TRUE'")
                else:
                    self.logger.warning(f"Script run evaluation FAILED: checker script output was '{stdout}', expected 'TRUE'")
                
                return success, evaluation_details
                
            except subprocess.TimeoutExpired:
                self.logger.error(f"Checker script timed out after {self.timeout}s")
                return False, {"error": f"Checker script timed out after {self.timeout}s"}
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Checker script failed with return code {e.returncode}")
                return False, {"error": f"Checker script failed with return code {e.returncode}", "stderr": e.stderr}
            
        except Exception as e:
            return False, {"error": f"Error during script_run evaluation: {str(e)}"}
    
    def _get_python_path(self, venv_path: Path) -> Path:
        """Get the path to the Python interpreter in the virtual environment."""
        if os.name == "nt":
            return venv_path / "Scripts" / "python.exe"
        return venv_path / "bin" / "python"