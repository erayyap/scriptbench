import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from scriptbench.benchmark import ScriptBenchmark

load_dotenv()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Run ScriptBench evaluation")
    parser.add_argument("--tasks-dir", default="tasks", help="Directory containing task JSON files")
    parser.add_argument("--files-dir", default="files", help="Directory containing task files")
    parser.add_argument("--logs-dir", help="Directory for detailed logs (default: from .env or 'logs')")
    parser.add_argument("--task", help="Run specific task by name")
    parser.add_argument("--output", help="Output file for results (JSON)")
    parser.add_argument(
        "--inference-backend",
        choices=["openai", "mini-swe", "mini-swe-iter"],
        help="Inference backend to use (default: env SCRIPTBENCH_INFERENCE_BACKEND or 'openai')",
    )
    
    args = parser.parse_args()
    
    tasks_dir = Path(args.tasks_dir).resolve()
    files_dir = Path(args.files_dir).resolve()
    logs_dir = Path(args.logs_dir) if args.logs_dir else None
    
    if not tasks_dir.exists():
        print(f"Tasks directory not found: {tasks_dir}")
        return
    
    if not files_dir.exists():
        print(f"Files directory not found: {files_dir}")
        return
    
    benchmark = ScriptBenchmark(
        tasks_dir,
        files_dir,
        logs_dir,
        inference_backend=args.inference_backend,
    )
    
    try:
        results = benchmark.run_benchmark(args.task)
        
        # Generate enhanced JSON output with model name and statistics
        enhanced_results = _generate_enhanced_results(results, benchmark)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            benchmark.logger.info(f"Results saved to {args.output}")
        
        # Always save enhanced results with model name
        _save_enhanced_results(enhanced_results, benchmark)
        
        _print_results_summary(results, benchmark.logs_dir)
                
    except KeyboardInterrupt:
        benchmark.logger.info("Benchmark interrupted by user")
        print("\nBenchmark interrupted by user")
    except Exception as e:
        benchmark.logger.error(f"Benchmark failed: {str(e)}")
        print(f"Benchmark failed: {str(e)}")


def _print_results_summary(results, logs_dir):
    passed = sum(1 for r in results if r['success'])
    print(f"\n=== Benchmark Results ===")
    print(f"Tasks completed: {len(results)}")
    print(f"Tasks passed: {passed}")
    print(f"Tasks failed: {len(results) - passed}")
    print(f"Success rate: {passed/len(results)*100:.1f}%")
    print(f"Detailed logs saved to: {logs_dir}")
    
    print(f"\nTask Results:")
    for result in results:
        status = 'PASSED' if result['success'] else 'FAILED'
        print(f"  {result['task_name']}: {status}")
        if not result['success'] and 'error' in result:
            print(f"    Error: {result['error']}")


def _generate_enhanced_results(results, benchmark):
    """Generate enhanced results with pass/fail statistics and additional metrics."""
    total_tasks = len(results)
    passed_tasks = sum(1 for r in results if r['success'])
    failed_tasks = total_tasks - passed_tasks
    
    pass_percentage = (passed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    fail_percentage = (failed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Get model name from LLM manager
    model_name = os.getenv("OPENAI_MODEL", "gpt-4")
    
    # Calculate additional metrics
    task_durations = []
    for result in results:
        if hasattr(result, 'get') and result.get('execution_time'):
            task_durations.append(result['execution_time'])
    
    avg_duration = sum(task_durations) / len(task_durations) if task_durations else 0
    
    # Group results by difficulty and task type if available
    difficulty_stats = {}
    task_type_stats = {}
    
    for result in results:
        # Difficulty stats
        difficulty = result.get('difficulty', 'unknown')
        if difficulty not in difficulty_stats:
            difficulty_stats[difficulty] = {'total': 0, 'passed': 0}
        difficulty_stats[difficulty]['total'] += 1
        if result['success']:
            difficulty_stats[difficulty]['passed'] += 1
            
        # Task type stats
        result_type = result.get('result_type', 'unknown')
        if result_type not in task_type_stats:
            task_type_stats[result_type] = {'total': 0, 'passed': 0}
        task_type_stats[result_type]['total'] += 1
        if result['success']:
            task_type_stats[result_type]['passed'] += 1
    
    # Calculate percentages for each category
    for category in difficulty_stats:
        total = difficulty_stats[category]['total']
        passed = difficulty_stats[category]['passed']
        difficulty_stats[category]['pass_rate'] = (passed / total * 100) if total > 0 else 0
        
    for category in task_type_stats:
        total = task_type_stats[category]['total']
        passed = task_type_stats[category]['passed']
        task_type_stats[category]['pass_rate'] = (passed / total * 100) if total > 0 else 0
    
    enhanced_results = {
        "metadata": {
            "model": model_name,
            "timestamp": datetime.now().isoformat(),
            "total_tasks": total_tasks,
            "total_duration": sum(task_durations) if task_durations else 0,
            "average_duration_per_task": avg_duration
        },
        "summary": {
            "passed": passed_tasks,
            "failed": failed_tasks,
            "pass_percentage": round(pass_percentage, 2),
            "fail_percentage": round(fail_percentage, 2)
        },
        "breakdown": {
            "by_difficulty": difficulty_stats,
            "by_task_type": task_type_stats
        },
        "detailed_results": results
    }
    
    return enhanced_results


def _save_enhanced_results(enhanced_results, benchmark):
    """Save enhanced results to a JSON file named after the model."""
    model_name = enhanced_results["metadata"]["model"]
    # Sanitize model name for filename
    safe_model_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in model_name)
    
    results_filename = f"{safe_model_name}_results.json"
    results_path = benchmark.logs_dir / results_filename
    
    with open(results_path, 'w') as f:
        json.dump(enhanced_results, f, indent=2)
    
    benchmark.logger.info(f"Enhanced results saved to {results_path}")
    print(f"Enhanced results saved to: {results_path}")


if __name__ == "__main__":
    main()
