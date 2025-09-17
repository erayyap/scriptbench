import logging
import os
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


class DetailedLogger:
    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create timestamped run directory
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.run_dir = self.logs_dir / f"run_{self.timestamp}"
        self.run_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for organization
        self.scripts_dir = self.run_dir / "scripts"
        self.scripts_dir.mkdir(exist_ok=True)

        self.task_artifacts_dir = self.run_dir / "tasks"
        self.task_artifacts_dir.mkdir(exist_ok=True)
        
        self.logger = logging.getLogger("scriptbench")
        self.logger.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO")))
        
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        log_file = self.run_dir / f"benchmark_{self.timestamp}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(console_formatter)
        self.logger.addHandler(file_handler)
        
        self.logger.info(f"Logging initialized. Run directory: {self.run_dir}")
        self.logger.info(f"Log file: {log_file}")
        self.logger.info(f"Scripts directory: {self.scripts_dir}")
        self.logger.info(f"Task artifacts directory: {self.task_artifacts_dir}")
    
    def save_task_details(self, task_name: str, details: Dict[str, Any]):
        yaml_file = self.run_dir / f"{task_name}.yaml"
        
        with open(yaml_file, 'w') as f:
            yaml.dump(details, f, default_flow_style=False, allow_unicode=True)
        
        self.logger.info(f"Task details saved to: {yaml_file}")
        return yaml_file
    
    def save_script(self, task_name: str, script_content: str, script_type: str = "python"):
        """Save script content to a separate file in the scripts directory"""
        if script_type == "python":
            script_file = self.scripts_dir / f"{task_name}.py"
        else:
            script_file = self.scripts_dir / f"{task_name}.{script_type}"
        
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        self.logger.info(f"Script saved to: {script_file}")
        return script_file
    
    def save_execution_log(self, task_name: str, execution_details: Dict[str, Any]):
        """Save execution details for a specific task"""
        exec_file = self.run_dir / f"{task_name}_execution.yaml"

        with open(exec_file, 'w') as f:
            yaml.dump(execution_details, f, default_flow_style=False, allow_unicode=True)

        self.logger.info(f"Execution details saved to: {exec_file}")
        return exec_file

    def get_task_directory(self, task_name: str) -> Path:
        """Return (and create) the directory for task-specific artifacts."""
        task_dir = self.task_artifacts_dir / task_name
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir
