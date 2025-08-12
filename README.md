# ScriptBench

ScriptBench is a benchmarking framework for evaluating Large Language Models (LLMs) on automated Python script generation and execution tasks. It tests an LLM's ability to understand task descriptions, generate working Python code with proper dependencies, and produce correct outputs across various domains.

## Overview

The framework prompts LLMs to generate complete Python solutions for diverse programming challenges, then automatically executes and evaluates the generated scripts. It measures both code generation capabilities and practical problem-solving effectiveness.

## Features

- **Automated LLM Integration**: Uses LangChain to interact with OpenAI models (configurable)
- **Environment Management**: Creates isolated environments with virtual environments and dependency installation
- **Multi-Platform Support**: Works on both Unix and Windows systems
- **Comprehensive Logging**: Detailed execution logs with timestamps and metadata
- **Multiple Evaluation Types**: 
  - Numerical output verification
  - Classification accuracy measurement
  - Script execution validation
- **Task Variety**: Supports different difficulty levels and problem domains

## Task Types

The framework includes several types of programming challenges:

### 1. Data Processing & Analysis
- **IMDB Sentiment Classification** (Difficulty: 2): Process movie reviews using OpenAI API for sentiment analysis
- **Pokemon Type Effectiveness** (Difficulty: 8): Complex type effectiveness calculations with custom game mechanics

### 2. Document Processing  
- **Table Counting** (Easy: Difficulty 3, Medium: varies): Extract and count cells from .docx files with table structures

### 3. Web & Media
- **YouTube Video Downloading**: Handle video downloading with validation scripts

## Project Structure

```
scriptbench/
├── src/scriptbench/           # Main package
│   ├── benchmark.py           # Core benchmarking logic
│   ├── main.py               # CLI entry point
│   ├── task.py               # Task definition and loading
│   ├── llm_manager.py        # LLM interaction management
│   ├── evaluator.py          # Result evaluation system
│   ├── environment.py        # Environment setup and management
│   ├── code_extraction.py    # Extract code/packages from LLM responses
│   ├── logger.py            # Detailed logging system
│   ├── execution/           # Script execution modules
│   └── evaluation/          # Evaluation strategies
├── tasks/                   # Task definitions (YAML)
├── files/                   # Task-specific data files
└── logs/                    # Execution logs and results
```

## Installation

1. Install the package:
```bash
make install
# or
pip install -e .
```

2. Set up environment variables by copying `.env.example` to `.env` and configuring:
```bash
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4
OPENAI_TEMPERATURE=0
```

## Usage

### Run All Tasks
```bash
make local-run
# or
python -m scriptbench.main
```

### Run Specific Task
```bash
make local-run-task TASK=pokemon_type_effectiveness
# or  
python -m scriptbench.main --task pokemon_type_effectiveness
```

### Save Results
```bash
make local-run-output OUTPUT=results.json
# or
python -m scriptbench.main --output results.json
```

### Other Commands
```bash
make clean      # Clean logs and temporary files
make test       # Run test suite
make help       # Show all available commands
```

## Configuration

Key environment variables:

- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_MODEL`: Model to use (default: gpt-4)  
- `OPENAI_TEMPERATURE`: Model temperature (default: 0)
- `SCRIPT_TIMEOUT`: Script execution timeout in seconds (default: 600)
- `LOG_LEVEL`: Logging level (default: INFO)

## Task Definition Format

Tasks are defined in YAML files with this structure:

```yaml
difficulty: 3                    # Difficulty rating (1-10)
task_folder: /path/to/files     # Data files location
task_specification:
  description: >                 # Task description for LLM
    Write a Python script that...
result:
  type: numerical               # evaluation type
  amount: 42                    # expected result
```

Supported result types:
- `numerical`: Compare numeric output
- `classification_match`: Compare against ground truth file
- `script_run`: Validate script execution with checker

## Evaluation System

The framework evaluates generated scripts through:

1. **Code Extraction**: Parse LLM response for Python code and dependencies
2. **Environment Setup**: Create isolated virtual environment
3. **Dependency Installation**: Install required apt and pip packages  
4. **Script Execution**: Run the generated Python script
5. **Result Validation**: Compare output against expected results using appropriate evaluator

## Logging & Output

Each run creates detailed logs in the `logs/` directory containing:
- Benchmark execution logs
- Individual task results and metadata
- Generated Python scripts
- LLM interaction details
- Execution timing and resource usage

## Dependencies

Core dependencies:
- `langchain-core` & `langchain-openai`: LLM integration
- `pandas`: Data processing
- `python-dotenv`: Environment configuration
- `pyyaml`: Task definition parsing

Additional packages installed per task as needed by generated scripts.