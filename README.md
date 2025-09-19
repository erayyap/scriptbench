# ScriptBench

> **⚠️ Pre-release Notice**: This is a pre-release version and everything is bound to change.
> 
> If you have task ideas, please share them! Open a PR or issue with your suggestions.

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
│   ├── inference/            # Inference backends (OpenAI, Mini SWE agent)
│   ├── evaluator.py          # Result evaluation system
│   ├── environment.py        # Environment setup and management
│   ├── code_extraction.py    # Extract code/packages from LLM responses
│   ├── logger.py             # Detailed logging system
│   ├── execution/            # Script execution modules
│   ├── evaluation/           # Evaluation strategies
│   └── config/               # Mini SWE agent configuration
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
# run with the Mini SWE agent
python -m scriptbench.main --inference-backend mini-swe
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
- `SCRIPTBENCH_INFERENCE_BACKEND`: Selects the inference backend (`openai`, `mini-swe`, or `mini-swe-iter`). Defaults to `openai`.
- `MINI_SWE_MINIMUM_ITERATIONS` / `SCRIPTBENCH_MINI_SWE_MIN_ITERATIONS`: Overrides the minimum command steps required by the `mini-swe-iter` backend (default: value from `mini_swe_iter.yaml`).

### Inference Backends

ScriptBench supports multiple inference providers via the `--inference-backend` CLI flag (or the `SCRIPTBENCH_INFERENCE_BACKEND` environment variable):

- `openai` *(default)*: Uses LangChain’s `ChatOpenAI` with the prompt structure described earlier. Behaviour is unchanged from previous releases.
- `mini-swe`: Runs the Mini SWE agent in an isolated scratch workspace. The agent iterates freely, then writes a `submission.md` file that contains three fenced code blocks (`apt`, `pip`, `script`). ScriptBench parses this file to extract dependencies and the final Python solution before executing it in the standard pipeline. The agent trajectory and full workspace are copied into the per-task log directory for inspection.
- `mini-swe-iter`: Uses the bundled "mini SWE iterative" prompt, which instructs the agent to execute at least *N* command steps (configurable via `minimum_iterations` or the `MINI_SWE_MINIMUM_ITERATIONS` environment override) before finishing. Each observation reminds the agent of the current step number and remaining required steps, preventing early termination.

Mini SWE backend configuration:

- `MINI_SWE_MODEL_NAME` *(optional)* – model name passed to Mini SWE. Falls back to `OPENAI_MODEL` if unset.
- `MINI_SWE_MODEL_CLASS` *(optional)* – explicit Mini SWE model class (e.g. `anthropic`).
- `MINI_SWE_MODEL_API_KEY` *(optional)* – API key for the Mini SWE model. Falls back to `OPENAI_API_KEY` if unset.
- `MINI_SWE_MODEL_BASE_URL` *(optional)* – base URL forwarded to LiteLLM. Falls back to the `OPENAI_BASE_URL_RUNNER` value.

The Mini SWE agents use bundled prompt configurations:

- `src/scriptbench/config/mini_swe.yaml` for the default free-iteration variant.
- `src/scriptbench/config/mini_swe_iter.yaml` for the minimum-steps variant described above.

Both prompts enforce the `END` completion signal with the relative path to the submission script (`printf 'END\nrelative/path/to/your_script.py\n'`).
Make sure the [`mini-swe-agent`](https://github.com/openai/mini-swe-agent) package is available in your environment (e.g. `pip install mini-swe-agent`) before selecting this backend.

## Task Definition Format

Tasks are defined in YAML files with this structure:

```yaml
difficulty: 3                    # Difficulty rating (1-10)
task_folder: /path/to/files     # Data files location
agent_env:                     # Optional resources staged for the Mini SWE agent
  agent_file: /path/to/example_input.json
task_specification:
  description: >                 # Task description for LLM
    Write a Python script that...
result:
  type: numerical               # evaluation type
  amount: 42                    # expected result
```

The runner copies `task_folder` / `task_file` paths from the directory configured by `SCRIPTBENCH_FILES_DIR` (defaults to `files/`) into the isolated execution environment that validates submissions. When `agent_env` is provided, any referenced files or folders are copied from `SCRIPTBENCH_AGENT_FILES_DIR` (defaults to `files_agent/`) into the Mini SWE agent workspace before it begins iterating. Both `agent_*` keys and their `task_*` aliases accept either a single string or a list of strings. If a top-level `task_file` is present, the same file is also staged for the agent to inspect.

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
