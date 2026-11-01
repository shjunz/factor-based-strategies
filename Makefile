# Makefile - Common project operations. Run `make help` to list them.

PYTHON ?= python3.12
VENV   := .venv
BIN    := $(VENV)/bin

# Backend API
HOST ?= 127.0.0.1
PORT ?= 8000
APP  := fbs.api.main:app

.PHONY: help venv install env clean clean-bronze api api-prod

help:  ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-13s %s\n", $$1, $$2}'

venv: $(BIN)/python  ## Create the virtual environment in .venv

# Created only once, re-running venv over an existing .venv can break pip
$(BIN)/python:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install -U pip

install: venv  ## Install the fbs package in editable mode
	$(BIN)/pip install -e .

env:  ## Create .env from .env.example if it does not exist yet
	@if [ -f .env ]; then echo ".env already exists, left unchanged"; \
	else cp .env.example .env && echo "Created .env, fill in NASDAQ_DATA_LINK_API_KEY"; fi

api:  ## Run the backend API with auto-reload (docs at http://HOST:PORT/docs)
	$(BIN)/uvicorn $(APP) --app-dir src --env-file .env --host $(HOST) --port $(PORT) --reload

api-prod:  ## Run the backend API without reload, listening on all interfaces
	$(BIN)/uvicorn $(APP) --app-dir src --env-file .env --host 0.0.0.0 --port $(PORT)

clean:  ## Remove the virtual environment and build artifacts
	rm -rf $(VENV) build dist src/*.egg-info
	find . -name __pycache__ -type d -prune -not -path "./$(VENV)/*" -exec rm -rf {} +

clean-bronze:  ## Delete downloaded data in data/bronze, keeping data/bronze/sample
	@read -p "Delete everything in data/bronze except sample/? [y/N] " ans && [ "$$ans" = y ]
	find data/bronze -mindepth 1 -maxdepth 1 ! -name sample -exec rm -rf {} +
