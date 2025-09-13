import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .logger import DetailedLogger
from .task import TaskLoader, Task
from .environment import EnvironmentManager
from .llm_manager import LLMManager
from .code_extraction import CodeExtractor
from .evaluator import Evaluator


class ScriptBenchmark:
    def __init__(self, tasks_dir: Path, files_dir: Path, logs_dir: Optional[Path] = None):
        self.tasks_dir = tasks_dir
        self.files_dir = files_dir
        self.logs_dir = logs_dir or Path(os.getenv("DETAILED_LOGS_DIR", "logs"))
        
        self.detailed_logger = DetailedLogger(self.logs_dir)
        self.logger = self.detailed_logger.logger
        
        self.task_loader = TaskLoader()
        self.env_manager = EnvironmentManager(files_dir, self.logger)
        self.llm_manager = LLMManager(self.logger)
        self.code_extractor = CodeExtractor()
    
    def run_benchmark(self, task_name: Optional[str] = None) -> List[Dict[str, Any]]:
        tasks = self.task_loader.load_tasks(self.tasks_dir)
        
        self.logger.info(f"Loaded {len(tasks)} tasks from {self.tasks_dir}")
        
        if task_name:
            tasks = [task for task in tasks if task.task_path.stem == task_name]
            if not tasks:
                raise ValueError(f"Task '{task_name}' not found")
            self.logger.info(f"Running specific task: {task_name}")
        else:
            self.logger.info("Running all tasks")
        
        results = []
        
        for i, task in enumerate(tasks, 1):
            self.logger.info(f"[{i}/{len(tasks)}] Starting task: {task.task_path.stem}")
            
            try:
                result = self.run_single_task(task)
                results.append(result)
                
                status = 'PASSED' if result['success'] else 'FAILED'
                self.logger.info(f"[{i}/{len(tasks)}] Task {task.task_path.stem}: {status}")
            except Exception as e:
                self.logger.error(f"[{i}/{len(tasks)}] Critical error in task {task.task_path.stem}: {str(e)}")
                # Create a failure result even for critical errors
                critical_error_result = {
                    "task_name": task.task_path.stem,
                    "success": False,
                    "error": f"Critical error: {str(e)}",
                    "difficulty": task.difficulty,
                    "result_type": task.result_type,
                    "output": ""
                }
                results.append(critical_error_result)
                self.logger.info(f"[{i}/{len(tasks)}] Task {task.task_path.stem}: FAILED (Critical Error)")
                # Continue with next task instead of stopping the entire benchmark
        
        passed = sum(1 for r in results if r['success'])
        self.logger.info(f"Benchmark complete: {passed}/{len(results)} tasks passed")
        
        return results
    
    def run_single_task(self, task: Task) -> Dict[str, Any]:
        task_start_time = datetime.now()
        temp_dir = None
        detailed_log = self._initialize_task_log(task, task_start_time)
        
        try:
            temp_dir, venv_path = self._setup_environment(task, detailed_log)
            
            llm_response, llm_metadata = self.llm_manager.prompt_for_solution(task)
            detailed_log["llm_interaction"] = llm_metadata
            
            # Add checkpoint after LLM interaction
            llm_end_time = datetime.now()
            detailed_log["benchmark_metadata"]["llm_end_time"] = llm_end_time.isoformat()
            
            pip_packages, apt_packages, script_content = self._extract_code(llm_response, detailed_log)
            
            if not script_content:
                return self._handle_no_script_error(task, detailed_log)
            
            # Install packages but continue execution even if some fail
            self._install_apt_packages(apt_packages, detailed_log)
            self._install_packages(venv_path, pip_packages, detailed_log)
            
            # Handle script wait time before execution
            self._handle_script_wait_time(task, task_start_time, detailed_log)
            
            success, output, stderr = self._execute_script(script_content, temp_dir, venv_path, detailed_log)
            
            if not success:
                return self._handle_execution_error(task, detailed_log, stderr)
            
            return self._evaluate_and_finalize(task, output, detailed_log, task_start_time, pip_packages, apt_packages, script_content, temp_dir)
            
        except Exception as e:
            self.logger.error(f"Unexpected error in task {task.task_path.stem}: {str(e)}", exc_info=True)
            return self._handle_unexpected_error(task, detailed_log, task_start_time, e)
        finally:
            if temp_dir:
                try:
                    self.env_manager.cleanup(temp_dir)
                except Exception as cleanup_error:
                    self.logger.warning(f"Failed to cleanup temp directory {temp_dir}: {cleanup_error}")
    
    def _initialize_task_log(self, task: Task, start_time: datetime) -> Dict[str, Any]:
        return {
            "task_name": task.task_path.stem,
            "task_metadata": {
                "difficulty": task.difficulty,
                "task_folder": task.task_folder,
                "task_file": task.task_file,
                "description": task.description,
                "result_type": task.result_type,
                "expected_result": task.expected_result,
                "task_file_path": str(task.task_path)
            },
            "benchmark_metadata": {
                "start_time": start_time.isoformat(),
                "temp_directory": None,
                "venv_path": None
            }
        }
    
    def _setup_environment(self, task: Task, detailed_log: Dict[str, Any]):
        self.logger.info(f"Setting up environment for task: {task.task_path.stem}")
        temp_dir = self.env_manager.setup_task_environment(task)
        venv_path = self.env_manager.create_venv(temp_dir)
        
        detailed_log["benchmark_metadata"]["temp_directory"] = str(temp_dir)
        detailed_log["benchmark_metadata"]["venv_path"] = str(venv_path)
        
        return temp_dir, venv_path
    
    def _extract_code(self, llm_response: str, detailed_log: Dict[str, Any]):
        pip_packages = self.code_extractor.extract_pip_packages(llm_response)
        apt_packages = self.code_extractor.extract_apt_packages(llm_response)
        script_content = self.code_extractor.extract_python_script(llm_response)
        
        detailed_log["code_extraction"] = {
            "pip_packages_found": pip_packages,
            "apt_packages_found": apt_packages,
            "script_extracted": script_content is not None,
            "script_length": len(script_content) if script_content else 0
        }
        
        return pip_packages, apt_packages, script_content
    
    def _install_apt_packages(self, packages: List[str], detailed_log: Dict[str, Any]) -> bool:
        self.logger.info(f"Installing apt packages: {packages}")
        success = self.env_manager.install_apt_packages(packages)
        detailed_log["apt_package_installation"] = {
            "packages": packages,
            "success": success
        }
        return success
    
    def _install_packages(self, venv_path: Path, packages: List[str], detailed_log: Dict[str, Any]) -> bool:
        self.logger.info(f"Installing pip packages: {packages}")
        success = self.env_manager.install_packages(venv_path, packages)
        detailed_log["pip_package_installation"] = {
            "packages": packages,
            "success": success
        }
        return success
    
    def _execute_script(self, script_content: str, temp_dir: Path, venv_path: Path, detailed_log: Dict[str, Any]):
        script_path = temp_dir / "script.py"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Save script separately in the logs directory
        task_name = detailed_log["task_name"]
        saved_script_path = self.detailed_logger.save_script(task_name, script_content, "python")
        
        detailed_log["generated_script"] = {
            "temp_path": str(script_path),
            "saved_path": str(saved_script_path),
            "content": script_content
        }
        
        # Create task-specific evaluator with task's timeout
        evaluator = Evaluator(self.logger, task.script_timeout)
        success, output, stderr, execution_metadata = evaluator.run_script(script_path, venv_path, temp_dir)
        detailed_log["script_execution"] = execution_metadata
        detailed_log["script_execution"]["stdout"] = output
        detailed_log["script_execution"]["stderr"] = stderr
        
        return success, output, stderr
    
    def _handle_script_wait_time(self, task: Task, task_start_time: datetime, detailed_log: Dict[str, Any]):
        """Handle script wait time using time checkpoints."""
        if task.script_wait_time <= 0:
            return
        
        current_time = datetime.now()
        elapsed_seconds = (current_time - task_start_time).total_seconds()
        
        if elapsed_seconds < task.script_wait_time:
            remaining_wait = task.script_wait_time - elapsed_seconds
            self.logger.info(f"Script wait time: {task.script_wait_time}s configured, {elapsed_seconds:.2f}s elapsed, waiting additional {remaining_wait:.2f}s")
            time.sleep(remaining_wait)
            
            # Log final checkpoint after wait
            final_time = datetime.now()
            detailed_log["benchmark_metadata"]["script_execution_start_time"] = final_time.isoformat()
            detailed_log["benchmark_metadata"]["total_wait_applied"] = remaining_wait
        else:
            self.logger.info(f"Script wait time: {task.script_wait_time}s configured, {elapsed_seconds:.2f}s already elapsed, no additional wait needed")
            detailed_log["benchmark_metadata"]["script_execution_start_time"] = current_time.isoformat()
            detailed_log["benchmark_metadata"]["total_wait_applied"] = 0
        
        detailed_log["benchmark_metadata"]["script_wait_time_configured"] = task.script_wait_time
        detailed_log["benchmark_metadata"]["elapsed_time_before_script"] = elapsed_seconds
    
    def _evaluate_and_finalize(self, task: Task, output: str, detailed_log: Dict[str, Any],
                              start_time: datetime, pip_packages: List[str], apt_packages: List[str], script_content: str, work_dir: Path) -> Dict[str, Any]:
        # Use task-specific evaluator for result evaluation as well
        evaluator = Evaluator(self.logger, task.script_timeout)
        evaluation = evaluator.evaluate_result(task, output, work_dir, self.logger)
        detailed_log["evaluation"] = {
            "success": evaluation["success"],
            "output_analysis": evaluation
        }
        
        end_time = datetime.now()
        detailed_log["benchmark_metadata"]["end_time"] = end_time.isoformat()
        detailed_log["benchmark_metadata"]["total_duration_seconds"] = (end_time - start_time).total_seconds()
        detailed_log["success"] = evaluation["success"]
        
        # Save main task details
        self.detailed_logger.save_task_details(task.task_path.stem, detailed_log)
        
        # Save separate execution log for easy access
        execution_details = {
            "task_name": task.task_path.stem,
            "success": evaluation["success"],
            "pip_packages_installed": pip_packages,
            "apt_packages_installed": apt_packages,
            "execution_time": detailed_log["benchmark_metadata"]["total_duration_seconds"],
            "output": output,
            "evaluation": evaluation,
            "script_execution": detailed_log.get("script_execution", {}),
            "timestamp": end_time.isoformat()
        }
        self.detailed_logger.save_execution_log(task.task_path.stem, execution_details)
        
        evaluation.update({
            "pip_packages_installed": pip_packages,
            "apt_packages_installed": apt_packages,
            "script_content": script_content
        })
        
        return evaluation
    
    def _handle_no_script_error(self, task: Task, detailed_log: Dict[str, Any]) -> Dict[str, Any]:
        detailed_log["error"] = "No Python script found in LLM response"
        detailed_log["success"] = False
        self.detailed_logger.save_task_details(task.task_path.stem, detailed_log)
        return {
            "task_name": task.task_path.stem,
            "success": False,
            "error": "No Python script found in LLM response",
            "difficulty": task.difficulty,
            "result_type": task.result_type
        }
    
    def _handle_package_error(self, task: Task, detailed_log: Dict[str, Any]) -> Dict[str, Any]:
        detailed_log["error"] = "Failed to install packages"
        detailed_log["success"] = False
        self.detailed_logger.save_task_details(task.task_path.stem, detailed_log)
        return {
            "task_name": task.task_path.stem,
            "success": False,
            "error": "Failed to install packages",
            "difficulty": task.difficulty,
            "result_type": task.result_type
        }
    
    def _handle_execution_error(self, task: Task, detailed_log: Dict[str, Any], stderr: str) -> Dict[str, Any]:
        detailed_log["error"] = f"Script execution failed: {stderr}"
        detailed_log["success"] = False
        self.detailed_logger.save_task_details(task.task_path.stem, detailed_log)
        return {
            "task_name": task.task_path.stem,
            "success": False,
            "error": f"Script execution failed: {stderr}",
            "difficulty": task.difficulty,
            "result_type": task.result_type
        }
    
    def _handle_unexpected_error(self, task: Task, detailed_log: Dict[str, Any], 
                                start_time: datetime, error: Exception) -> Dict[str, Any]:
        self.logger.error(f"Unexpected error in task {task.task_path.stem}: {str(error)}")
        
        end_time = datetime.now()
        detailed_log["benchmark_metadata"]["end_time"] = end_time.isoformat()
        detailed_log["benchmark_metadata"]["total_duration_seconds"] = (end_time - start_time).total_seconds()
        detailed_log["error"] = f"Unexpected error: {str(error)}"
        detailed_log["success"] = False
        
        self.detailed_logger.save_task_details(task.task_path.stem, detailed_log)
        
        return {
            "task_name": task.task_path.stem,
            "success": False,
            "error": f"Unexpected error: {str(error)}",
            "difficulty": task.difficulty,
            "result_type": task.result_type
        }