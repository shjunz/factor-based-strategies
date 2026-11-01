# Makefile - Common project operations. Run `make help` to list them.

PYTHON ?= python3.12
VENV   := .venv
BIN    := $(VENV)/bin

.PHONY: help venv install clean

help:  ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

venv:  ## Create the virtual environment in .venv
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install -U pip

install: venv  ## Install the fbs package in editable mode
	$(BIN)/pip install -e .

clean:  ## Remove the virtual environment and build artifacts
	rm -rf $(VENV) build dist src/*.egg-info
	find . -name __pycache__ -type d -prune -not -path "./$(VENV)/*" -exec rm -rf {} +
