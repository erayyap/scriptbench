import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

from .base import ScriptExecutor


class WindowsScriptExecutor(ScriptExecutor):
    """Windows-specific script executor."""
    
    def execute(self, cmd: List[str], work_dir: Path, start_time: datetime) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Execute a script on Windows platform."""
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=work_dir,
                env=os.environ.copy()
            )
            
            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    stdout, stderr = "", "Process killed after timeout"
                
                metadata = self.create_timeout_metadata(cmd, work_dir, start_time)
                self.logger.error(f"Script execution timed out after {self.timeout}s")
                return False, "", "Script execution timed out", metadata
            
            stdout_lines = stdout.splitlines() if stdout else []
            stderr_lines = stderr.splitlines() if stderr else []
            
            self.log_output(stdout_lines, stderr_lines)
            
            metadata = self.create_execution_metadata(process, cmd, work_dir, start_time)
            success = process.returncode == 0
            
            self.logger.info(f"Script execution {'succeeded' if success else 'failed'} in {metadata['duration_seconds']:.2f}s")
            
            return success, stdout, stderr, metadata
            
        except Exception as e:
            self.logger.error(f"Error in Windows script execution: {e}")
            metadata = self.create_error_metadata(cmd, work_dir, start_time, e)
            return False, "", f"Script execution failed: {str(e)}", metadata