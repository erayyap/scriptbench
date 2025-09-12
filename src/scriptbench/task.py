import json
import yaml
from pathlib import Path
from typing import Dict, Any, List


class Task:
    def __init__(self, task_data: Dict[str, Any], task_path: Path):
        self.difficulty = task_data["difficulty"]
        # Support both task_folder and task_file, but not both at the same time
        self.task_folder = task_data.get("task_folder")
        self.task_file = task_data.get("task_file")
        self.task_script = task_data.get("task_script")
        
        if self.task_folder and self.task_file:
            raise ValueError("Cannot specify both task_folder and task_file in the same task")
            
        self.description = task_data["task_specification"]["description"]
        self.result_type = task_data["result"]["type"]
        self.expected_result = task_data["result"].get("amount")
        self.expected_string = task_data["result"].get("expected_string")
        self.case_sensitive = task_data["result"].get("case_sensitive", True)
        self.threshold = task_data["result"].get("threshold")
        self.ground_truth_file = task_data["result"].get("ground_truth_file")
        self.script_file = task_data["result"].get("script_file")
        self.task_path = task_path
        
    @classmethod
    def load_from_file(cls, task_file: Path) -> "Task":
        with open(task_file, 'r') as f:
            if task_file.suffix.lower() in ('.yaml', '.yml'):
                task_data = yaml.safe_load(f)
            else:
                task_data = json.load(f)
        return cls(task_data, task_file)


class TaskLoader:
    @staticmethod
    def load_tasks(tasks_dir: Path) -> List[Task]:
        tasks = []
        for pattern in ["*.yaml", "*.yml", "*.json"]:
            for task_file in tasks_dir.glob(pattern):
                task = Task.load_from_file(task_file)
                tasks.append(task)
        return tasks