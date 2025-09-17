import os
import shutil
import subprocess
import sys
import tempfile
import threading
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from .task import Task

# Constants
DEFAULT_TIMEOUT_SECONDS = 300
STREAM_TIMEOUT_SECONDS = 10
UPDATE_TIMEOUT_SECONDS = 300
VENV_DIRNAME = "venv"
LOG_PREFIX_TASK_SCRIPT = "task_script"
LOG_PREFIX_APT_UPDATE = "apt-update"
LOG_PREFIX_APT_PACKAGE = "apt"
LOG_PREFIX_PIP_PACKAGE = "pip"


class EnvironmentManager:
    def __init__(self, base_files_dir: Path, logger: Optional[logging.Logger] = None):
        self.base_files_dir = base_files_dir
        self.logger = logger or logging.getLogger(__name__)
        self.running_processes: List[subprocess.Popen] = []
        
    def setup_task_environment(self, task: Task, *, start_task_script: bool = True) -> Path:
        prefix = self._get_temp_dir_prefix(task)
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
        
        self._setup_task_files(task, temp_dir)
        self._setup_script_file(task, temp_dir)
        if start_task_script:
            self._start_task_script_if_needed(task)

        return temp_dir
    
    def _get_temp_dir_prefix(self, task: Task) -> str:
        """Generate appropriate prefix for temp directory based on task."""
        if task.task_folder:
            return f"scriptbench_{task.task_folder.strip('/').replace('/', '_')}_"
        elif task.task_file:
            file_stem = Path(task.task_file).stem
            return f"scriptbench_{file_stem}_"
        else:
            return "scriptbench_"
    
    def _setup_task_files(self, task: Task, temp_dir: Path) -> None:
        """Set up task environment files based on task configuration."""
        if task.task_folder:
            self._setup_folder_environment(task, temp_dir)
        elif task.task_file:
            self._setup_file_environment(task, temp_dir)
        else:
            self.logger.info("No task_folder or task_file specified, using empty environment")
    
    def _setup_script_file(self, task: Task, temp_dir: Path) -> None:
        """Copy script file for script_run evaluation if needed."""
        if task.script_file:
            self._copy_script_file(task, temp_dir)
    
    def _start_task_script_if_needed(self, task: Task) -> None:
        """Start task script as background process if specified."""
        if task.task_script:
            process = self._start_task_script(task)
            if process:
                self.running_processes.append(process)

    def start_task_script(self, task: Task) -> None:
        """Public helper to start a task script on demand."""
        self._start_task_script_if_needed(task)
    
    def _setup_folder_environment(self, task: Task, temp_dir: Path) -> None:
        """Copy entire folder structure to temp directory"""
        task_files_dir = self.base_files_dir / task.task_folder.strip("/")
        self.logger.info(f"Checking task files directory: {task_files_dir}")
        
        if task_files_dir.exists():
            self.logger.info(f"Task files directory exists, contents: {list(task_files_dir.iterdir())}")
            destination = temp_dir / task.task_folder.strip("/")
            self.logger.info(f"Copying from {task_files_dir} to {destination}")
            shutil.copytree(task_files_dir, destination)
            self.logger.info(f"Copy completed. Destination contents: {list(destination.iterdir()) if destination.exists() else 'Directory not found'}")
        else:
            self.logger.warning(f"Task files directory does not exist: {task_files_dir}")
    
    def _setup_file_environment(self, task: Task, temp_dir: Path) -> None:
        """Copy individual file and ground truth file to temp directory without folder structure"""
        # Copy the main task file
        source_file = self.base_files_dir / task.task_file.strip("/")
        self.logger.info(f"Checking task file: {source_file}")
        
        if source_file.exists():
            # Copy only the filename, not the folder structure
            filename = Path(task.task_file).name
            destination = temp_dir / filename
            
            self.logger.info(f"Copying file from {source_file} to {destination}")
            shutil.copy2(source_file, destination)
            self.logger.info(f"File copy completed. File exists: {destination.exists()}")
        else:
            self.logger.warning(f"Task file does not exist: {source_file}")
        
        # Copy the ground truth file if specified
        if task.ground_truth_file:
            ground_truth_source = self.base_files_dir / task.ground_truth_file.strip("/")
            self.logger.info(f"Checking ground truth file: {ground_truth_source}")
            
            if ground_truth_source.exists():
                # Copy only the filename, not the folder structure
                ground_truth_filename = Path(task.ground_truth_file).name
                ground_truth_destination = temp_dir / ground_truth_filename
                
                self.logger.info(f"Copying ground truth file from {ground_truth_source} to {ground_truth_destination}")
                shutil.copy2(ground_truth_source, ground_truth_destination)
                self.logger.info(f"Ground truth file copy completed. File exists: {ground_truth_destination.exists()}")
            else:
                self.logger.warning(f"Ground truth file does not exist: {ground_truth_source}")
    
    def _copy_script_file(self, task: Task, temp_dir: Path) -> None:
        """Copy the script file for script_run evaluation type (separate from task files)"""
        script_source = self.base_files_dir / task.script_file.strip("/")
        self.logger.info(f"Checking script file: {script_source}")
        
        if script_source.exists():
            # Copy only the filename, not the folder structure
            script_filename = Path(task.script_file).name
            script_destination = temp_dir / script_filename
            
            self.logger.info(f"Copying script file from {script_source} to {script_destination}")
            shutil.copy2(script_source, script_destination)
            self.logger.info(f"Script file copy completed. File exists: {script_destination.exists()}")
        else:
            self.logger.warning(f"Script file does not exist: {script_source}")
    
    def _start_task_script(self, task: Task) -> Optional[subprocess.Popen]:
        """Start the task_script as a subprocess using the main project's venv"""
        script_source = self.base_files_dir / task.task_script.strip("/")
        self.logger.info(f"Checking task script: {script_source}")
        
        if script_source.exists():
            self.logger.info(f"Running task script: {script_source}")
            try:
                python_path = sys.executable
                script_dir = script_source.parent
                
                process = self._create_background_process(python_path, script_source, script_dir)
                self.logger.info(f"Task script started with PID: {process.pid}")
                
                self._start_output_streaming(process)
                return process
            except Exception as e:
                self.logger.error(f"Failed to start task script: {e}")
                raise
        else:
            self.logger.warning(f"Task script does not exist: {script_source}")

    def _create_background_process(self, python_path: str, script_source: Path, script_dir: Path) -> subprocess.Popen:
        """Create a background subprocess for running task scripts."""
        return subprocess.Popen(
            [str(python_path), str(script_source)],
            cwd=script_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
    
    def _start_output_streaming(self, process: subprocess.Popen) -> None:
        """Start streaming output from process in a separate thread."""
        def stream_output():
            try:
                for line in iter(process.stdout.readline, ''):
                    if line:
                        self.logger.info(f"{LOG_PREFIX_TASK_SCRIPT}: {line.rstrip()}")
                process.stdout.close()
            except Exception as e:
                self.logger.error(f"Error streaming task script output: {e}")
        
        output_thread = threading.Thread(target=stream_output, daemon=True)
        output_thread.start()
    
    def create_venv(self, work_dir: Path) -> Path:
        venv_path = work_dir / VENV_DIRNAME
        cmd = ["python", "-m", "venv", str(venv_path)]
        
        self.logger.info(f"Creating virtual environment: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.logger.info("Virtual environment created successfully")
            if result.stdout.strip():
                self.logger.info(f"venv stdout: {result.stdout.strip()}")
            if result.stderr.strip():
                self.logger.info(f"venv stderr: {result.stderr.strip()}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Virtual environment creation failed: {e}")
            if e.stdout:
                self.logger.error(f"venv stdout: {e.stdout}")
            if e.stderr:
                self.logger.error(f"venv stderr: {e.stderr}")
            raise
            
        return venv_path
    
    def install_apt_packages(self, packages: List[str]) -> bool:
        if not packages:
            return True
        
        missing_packages = self._get_missing_apt_packages(packages)
        if not missing_packages:
            self.logger.info("All apt packages are already installed")
            return True
            
        self.logger.info(f"Installing missing apt packages: {missing_packages}")
        
        self._update_apt_package_list()
        successfully_installed, failed_packages = self._install_apt_packages_individually(missing_packages)
        
        self._log_installation_results(successfully_installed, failed_packages, "apt")
        return True

    def install_packages(self, venv_path: Path, packages: List[str]) -> bool:
        if not packages:
            return True
            
        pip_path = self._get_pip_path(venv_path)
        successfully_installed, failed_packages = self._install_pip_packages_individually(pip_path, packages)
        
        self._log_installation_results(successfully_installed, failed_packages, "pip")
        return True
    
    def _get_missing_apt_packages(self, packages: List[str]) -> List[str]:
        """Check which apt packages are not installed."""
        missing_packages = []
        for package in packages:
            try:
                result = subprocess.run(
                    ["dpkg-query", "-W", "-f=${Status}", package],
                    capture_output=True,
                    text=True,
                    timeout=STREAM_TIMEOUT_SECONDS
                )
                if result.returncode != 0 or "install ok installed" not in result.stdout:
                    missing_packages.append(package)
                else:
                    self.logger.info(f"Package {package} is already installed")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                missing_packages.append(package)
        return missing_packages
    
    def _update_apt_package_list(self) -> None:
        """Update the apt package list."""
        self.logger.info("Updating package list...")
        try:
            update_process = subprocess.Popen(
                ["bash", "-c", "sudo apt-get update"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            for line in update_process.stdout:
                line = line.rstrip()
                if line:
                    self.logger.info(f"{LOG_PREFIX_APT_UPDATE}: {line}")
                    
            update_process.wait(timeout=UPDATE_TIMEOUT_SECONDS)
        except Exception as e:
            self.logger.warning(f"Failed to update package list: {str(e)}. Continuing with installations...")
    
    def _install_apt_packages_individually(self, packages: List[str]) -> Tuple[List[str], List[str]]:
        """Install apt packages one by one, returning success and failure lists."""
        successfully_installed = []
        failed_packages = []
        
        for package in packages:
            try:
                self.logger.info(f"Attempting to install package: {package}")
                success = self._install_single_apt_package(package)
                if success:
                    successfully_installed.append(package)
                else:
                    failed_packages.append(package)
            except Exception as e:
                self.logger.warning(f"Package {package} installation failed with exception: {str(e)}. Continuing with next package...")
                failed_packages.append(package)
        
        return successfully_installed, failed_packages
    
    def _install_single_apt_package(self, package: str) -> bool:
        """Install a single apt package."""
        bash_cmd = f"sudo apt-get install -y {package}"
        
        try:
            process = subprocess.Popen(
                ["bash", "-c", bash_cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            output_lines = self._stream_process_output(process, f"{LOG_PREFIX_APT_PACKAGE}({package})")
            
            try:
                return_code = process.wait(timeout=DEFAULT_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Package {package} installation timed out after {DEFAULT_TIMEOUT_SECONDS} seconds. Continuing with next package...")
                self._kill_process_safely(process)
                return False
            
            if return_code == 0:
                self.logger.info(f"Successfully installed package: {package}")
                return True
            else:
                self.logger.warning(f"Failed to install package {package} (return code: {return_code}). Continuing with next package...")
                if output_lines:
                    self.logger.warning(f"Last output for {package}: {output_lines[-3:]}")
                return False
                
        except FileNotFoundError:
            self.logger.warning(f"bash not found - cannot install {package}. Continuing with next package...")
            return False
    
    def _install_pip_packages_individually(self, pip_path: Path, packages: List[str]) -> Tuple[List[str], List[str]]:
        """Install pip packages one by one, returning success and failure lists."""
        successfully_installed = []
        failed_packages = []
        
        for package in packages:
            try:
                self.logger.info(f"Attempting to install pip package: {package}")
                success = self._install_single_pip_package(pip_path, package)
                if success:
                    successfully_installed.append(package)
                else:
                    failed_packages.append(package)
            except Exception as e:
                self.logger.warning(f"Package {package} installation failed with exception: {str(e)}. Continuing with next package...")
                failed_packages.append(package)
        
        return successfully_installed, failed_packages
    
    def _install_single_pip_package(self, pip_path: Path, package: str) -> bool:
        """Install a single pip package."""
        cmd = [str(pip_path), "install", package]
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            output_lines = self._stream_process_output(process, f"{LOG_PREFIX_PIP_PACKAGE}({package})")
            
            try:
                return_code = process.wait(timeout=DEFAULT_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Package {package} installation timed out after {DEFAULT_TIMEOUT_SECONDS} seconds. Continuing with next package...")
                self._kill_process_safely(process)
                return False
            
            if return_code == 0:
                self.logger.info(f"Successfully installed pip package: {package}")
                return True
            else:
                self.logger.warning(f"Failed to install package {package} (return code: {return_code}). Continuing with next package...")
                if output_lines:
                    self.logger.warning(f"Last output for {package}: {output_lines[-3:]}")
                return False
                
        except FileNotFoundError:
            self.logger.warning(f"Pip executable not found at: {pip_path} for package {package}. Continuing with next package...")
            return False
        except PermissionError:
            self.logger.warning(f"Permission denied accessing pip for package {package}. Continuing with next package...")
            return False
    
    def _stream_process_output(self, process: subprocess.Popen, log_prefix: str) -> List[str]:
        """Stream process output and return collected lines."""
        output_lines = []
        try:
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    self.logger.info(f"{log_prefix}: {line}")
                    output_lines.append(line)
        except Exception as stream_error:
            self.logger.warning(f"Error reading output stream: {stream_error}")
        return output_lines
    
    def _kill_process_safely(self, process: subprocess.Popen) -> None:
        """Safely kill a process with timeout handling."""
        try:
            process.kill()
            process.wait(timeout=STREAM_TIMEOUT_SECONDS)
        except Exception:
            pass
    
    def _log_installation_results(self, successfully_installed: List[str], failed_packages: List[str], package_type: str) -> None:
        """Log the results of package installation."""
        if successfully_installed:
            self.logger.info(f"Successfully installed {package_type} packages: {successfully_installed}")
        if failed_packages:
            self.logger.warning(f"Failed to install {package_type} packages: {failed_packages}. Script execution will continue anyway.")
    
    def _get_pip_path(self, venv_path: Path) -> Path:
        if os.name == "nt":
            return venv_path / "Scripts" / "pip.exe"
        return venv_path / "bin" / "pip"
    
    def _get_python_path(self, venv_path: Path) -> Path:
        if os.name == "nt":
            return venv_path / "Scripts" / "python.exe"
        return venv_path / "bin" / "python"
    
    def cleanup_processes(self) -> None:
        """Clean up any running task script processes."""
        for process in self.running_processes:
            if process.poll() is None:  # Process is still running
                self.logger.info(f"Terminating task script process {process.pid}")
                self._terminate_process_safely(process)
        self.running_processes.clear()
    
    def _terminate_process_safely(self, process: subprocess.Popen) -> None:
        """Safely terminate a process with fallback to kill."""
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Force killing task script process {process.pid}")
            try:
                process.kill()
                process.wait()
            except Exception as e:
                self.logger.error(f"Error force killing process {process.pid}: {e}")
        except Exception as e:
            self.logger.error(f"Error cleaning up process {process.pid}: {e}")
    
    def cleanup(self, temp_dir: Path) -> None:
        self.cleanup_processes()
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
