.PHONY: local-run install clean test help

# Default Python command
PYTHON := python3

# Install dependencies
install:
	pip install -e .

# Run the framework locally
local-run:
	$(PYTHON) -m scriptbench.main

# Run with specific task
local-run-task:
	$(PYTHON) -m scriptbench.main --task $(TASK)

# Run with output file
local-run-output:
	$(PYTHON) -m scriptbench.main --output $(OUTPUT)

# Clean temporary files and logs
clean:
	rm -rf logs/
	rm -rf __pycache__/
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Run tests
test:
	$(PYTHON) -m pytest tests/ -v

# Show help
help:
	@echo "ScriptBench Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install       - Install the package in development mode"
	@echo "  local-run     - Run the framework with default settings"
	@echo "  local-run-task TASK=<name> - Run a specific task"
	@echo "  local-run-output OUTPUT=<file> - Run and save results to file"
	@echo "  clean         - Clean temporary files and logs"
	@echo "  test          - Run the test suite"
	@echo "  help          - Show this help message"
	@echo ""
	@echo "Examples:"
	@echo "  make local-run"
	@echo "  make local-run-task TASK=table_counting"
	@echo "  make local-run-output OUTPUT=results.json"