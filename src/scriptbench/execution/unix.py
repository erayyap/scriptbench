import os
import select
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

from .base import ScriptExecutor


class UnixScriptExecutor(ScriptExecutor):
    """Unix-specific script executor with real-time output streaming."""
    
    def execute(self, cmd: List[str], work_dir: Path, start_time: datetime) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Execute a script on Unix platform with output streaming."""
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
                stdout_lines, stderr_lines = self._stream_output(process)
                
                # Get any remaining output
                try:
                    remaining_stdout, remaining_stderr = process.communicate(timeout=5)
                    if remaining_stdout:
                        stdout_lines.extend(remaining_stdout.splitlines())
                    if remaining_stderr:
                        stderr_lines.extend(remaining_stderr.splitlines())
                except subprocess.TimeoutExpired:
                    self.logger.warning("Timeout while collecting remaining output")
                    process.kill()
                    try:
                        process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass
                
            except subprocess.TimeoutExpired:
                metadata = self.create_timeout_metadata(cmd, work_dir, start_time)
                self.logger.error(f"Script execution timed out after {self.timeout}s")
                return False, "", "Script execution timed out", metadata
            except Exception as stream_error:
                self.logger.error(f"Error during output streaming: {stream_error}")
                # Fallback to basic communicate
                try:
                    stdout, stderr = process.communicate(timeout=self.timeout)
                    stdout_lines = stdout.splitlines() if stdout else []
                    stderr_lines = stderr.splitlines() if stderr else []
                    self.log_output(stdout_lines, stderr_lines)
                except subprocess.TimeoutExpired:
                    process.kill()
                    metadata = self.create_timeout_metadata(cmd, work_dir, start_time)
                    self.logger.error(f"Script execution timed out after {self.timeout}s")
                    return False, "", "Script execution timed out", metadata
            
            stdout_str = '\n'.join(stdout_lines)
            stderr_str = '\n'.join(stderr_lines)
            
            metadata = self.create_execution_metadata(process, cmd, work_dir, start_time)
            success = process.returncode == 0
            
            self.logger.info(f"Script execution {'succeeded' if success else 'failed'} in {metadata['duration_seconds']:.2f}s")
            
            return success, stdout_str, stderr_str, metadata
            
        except Exception as e:
            self.logger.error(f"Error in Unix script execution: {e}")
            metadata = self.create_error_metadata(cmd, work_dir, start_time, e)
            return False, "", f"Script execution failed: {str(e)}", metadata
    
    def _stream_output(self, process: subprocess.Popen) -> Tuple[List[str], List[str]]:
        """Stream output from process in real-time."""
        stdout_lines = []
        stderr_lines = []
        
        try:
            poller = select.poll()
            poller.register(process.stdout, select.POLLIN)
            poller.register(process.stderr, select.POLLIN)
            
            timeout_counter = 0
            max_timeouts = self.timeout * 10  # 100ms polls, so timeout * 10 = timeout in seconds
            
            while process.poll() is None and timeout_counter < max_timeouts:
                ready = poller.poll(100)  # 100ms timeout
                
                if not ready:
                    timeout_counter += 1
                    continue
                
                timeout_counter = 0  # Reset counter if we got output
                
                for fd, event in ready:
                    try:
                        if fd == process.stdout.fileno():
                            line = process.stdout.readline()
                            if line:
                                line = line.rstrip()
                                if line:
                                    self.logger.info(f"script stdout: {line}")
                                    stdout_lines.append(line)
                        elif fd == process.stderr.fileno():
                            line = process.stderr.readline()
                            if line:
                                line = line.rstrip()
                                if line:
                                    self.logger.error(f"script stderr: {line}")
                                    stderr_lines.append(line)
                    except Exception as read_error:
                        self.logger.warning(f"Error reading output line: {read_error}")
                        continue
            
            # Check if we timed out
            if timeout_counter >= max_timeouts and process.poll() is None:
                self.logger.error("Script execution timed out during streaming")
                process.kill()
                raise subprocess.TimeoutExpired([], self.timeout)
        
        except Exception as polling_error:
            self.logger.error(f"Error during output polling: {polling_error}")
            # Try to kill process if it's still running
            if process.poll() is None:
                try:
                    process.kill()
                except Exception:
                    pass
            raise
        
        return stdout_lines, stderr_lines