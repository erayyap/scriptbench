import csv
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from .base import BaseEvaluator
from ..task import Task


class ClassificationEvaluator(BaseEvaluator):
    """Evaluates classification results by comparing generated files with ground truth."""
    
    def evaluate(self, task: Task, output: str = "", work_dir: Optional[Path] = None) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate classification task results."""
        if not work_dir:
            return False, {"error": "work_dir is required for classification evaluation"}
        
        if not task.threshold or not task.ground_truth_file:
            return False, {"error": "Missing threshold or ground_truth_file in task configuration"}
        
        # Determine result file path based on task configuration
        if task.task_file:
            # Files are copied to root of work_dir without folder structure
            result_file_path = work_dir / Path(task.task_file).name
        else:
            return False, {"error": "task_file not specified for classification_match"}
        
        # Ground truth file is also copied to root of work_dir without folder structure
        ground_truth_path = work_dir / Path(task.ground_truth_file).name
        
        if not result_file_path.exists():
            return False, {"error": f"Result file not found: {result_file_path}"}
        
        if not ground_truth_path.exists():
            return False, {"error": f"Ground truth file not found: {ground_truth_path}"}
        
        try:
            # Read result file with proper encoding detection
            result_rows = self._read_csv_with_encoding(result_file_path)
            
            # Read ground truth file with proper encoding detection
            truth_rows = self._read_csv_with_encoding(ground_truth_path)
            
            if len(result_rows) != len(truth_rows):
                return False, {
                    "error": f"Row count mismatch: result={len(result_rows)}, ground_truth={len(truth_rows)}"
                }
            
            if len(result_rows) == 0:
                return False, {"error": "No data rows found in files"}
            
            # Find the target column (prefer 'target', fall back to 'result')
            result_target_col = self._find_target_column(result_rows[0])
            truth_target_col = self._find_target_column(truth_rows[0])
            
            if not result_target_col or not truth_target_col:
                return False, {
                    "error": f"Target column not found. Result columns: {list(result_rows[0].keys())}, Truth columns: {list(truth_rows[0].keys())}"
                }
            
            # Compare classifications
            matches = 0
            total = len(result_rows)
            
            for i, (result_row, truth_row) in enumerate(zip(result_rows, truth_rows)):
                result_value = result_row.get(result_target_col, "").strip()
                truth_value = truth_row.get(truth_target_col, "").strip()
                
                if result_value == truth_value:
                    matches += 1
            
            score = matches / total if total > 0 else 0
            success = score >= task.threshold
            
            evaluation_details = {
                "matches": matches,
                "total": total,
                "score": score,
                "threshold": task.threshold,
                "result_file": str(result_file_path),
                "ground_truth_file": str(ground_truth_path),
                "result_target_column": result_target_col,
                "truth_target_column": truth_target_col
            }
            
            return success, evaluation_details
            
        except Exception as e:
            return False, {"error": f"Error during classification evaluation: {str(e)}"}
    
    def _read_csv_with_encoding(self, file_path: Path) -> list:
        """Read CSV file with proper encoding detection (UTF-16 or UTF-8)."""
        encodings_to_try = ['utf-16', 'utf-8']
        
        for encoding in encodings_to_try:
            try:
                with open(file_path, 'r', newline='', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    return list(reader)
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        # If all encodings fail, raise an error
        raise ValueError(f"Could not read {file_path} with UTF-16 or UTF-8 encoding")
    
    def _find_target_column(self, row_data: Dict[str, Any]) -> Optional[str]:
        """Find the target column in the data, checking multiple possible column names."""
        # Check for common target column names
        target_columns = ['target', 'result', 'Durum', 'label', 'class', 'classification']
        
        for col in target_columns:
            if col in row_data:
                return col
        
        # If no standard target column found, return the last column (common convention)
        columns = list(row_data.keys())
        if columns:
            return columns[-1]
        
        return None