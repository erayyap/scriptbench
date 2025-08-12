import os
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple
import logging


class ScriptExecutor(ABC):
    """Abstract base class for platform-specific script executors."""
    
    def __init__(self, timeout: int, logger: logging.Logger):
        self.timeout = timeout
        self.logger = logger
    
    @abstractmethod
    def execute(self, cmd: List[str], work_dir: Path, start_time: datetime) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Execute a script command and return results."""
        pass
    
    def get_python_path(self, venv_path: Path) -> Path:
        """Get the path to the Python interpreter in the virtual environment."""
        if os.name == "nt":
            return venv_path / "Scripts" / "python.exe"
        return venv_path / "bin" / "python"
    
    def log_output(self, stdout_lines: List[str], stderr_lines: List[str]) -> None:
        """Log script output lines."""
        for line in stdout_lines:
            if line.strip():
                self.logger.info(f"script stdout: {line}")
        for line in stderr_lines:
            if line.strip():
                self.logger.error(f"script stderr: {line}")
    
    def create_execution_metadata(self, process: subprocess.Popen, cmd: List[str], 
                                work_dir: Path, start_time: datetime) -> Dict[str, Any]:
        """Create execution metadata dictionary."""
        end_time = datetime.now()
        success = process.returncode == 0
        
        return {
            "command": cmd,
            "working_directory": str(work_dir),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "return_code": process.returncode,
            "timeout": self.timeout,
            "success": success
        }
    
    def create_error_metadata(self, cmd: List[str], work_dir: Path, start_time: datetime, 
                            error: Exception) -> Dict[str, Any]:
        """Create metadata for error cases."""
        end_time = datetime.now()
        
        return {
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
    
    def create_timeout_metadata(self, cmd: List[str], work_dir: Path, start_time: datetime) -> Dict[str, Any]:
        """Create metadata for timeout cases."""
        end_time = datetime.now()
        
        return {
            "command": cmd,
            "working_directory": str(work_dir),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "return_code": None,
            "timeout": self.timeout,
            "success": False,
            "error": "timeout"
        }