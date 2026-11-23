# Makefile - Common project operations. Run `make help` to list them.

# Dependencies are declared in pyproject.toml and pinned in uv.lock; uv builds .venv from the lock
VENV   := .venv
BIN    := $(VENV)/bin

# C4 diagrams: Structurizr DSL -> PlantUML -> SVG. Tools are plain Java jars (no brew needed);
# `make diagram-tools` downloads pinned versions once into TOOLS.
ARCH  := docs/C4_Architecture
DATA  := docs/Data_architecture
PUML  := build/diagrams
TOOLS ?= $(HOME)/.local/share/fbs-diagram-tools
JAVA  ?= $(firstword $(wildcard /opt/homebrew/opt/openjdk/bin/java) java)
# Graphviz gives much better layouts; without it PlantUML falls back to its built-in Smetana engine
# (macOS 14 has no brew bottle: conda create -n diagrams -c conda-forge graphviz)
DOT   ?= $(firstword $(wildcard /opt/anaconda3/envs/diagrams/bin/dot $(shell command -v dot 2>/dev/null)))
LAYOUT := $(if $(DOT),-graphvizdot $(DOT),-Playout=smetana)
STRUCTURIZR_VERSION := 2025.11.09
PLANTUML_VERSION    := 1.2025.10

.PHONY: help install lock upgrade env clean clean-bronze diagram-tools diagrams diagrams-preview data-diagrams

help:  ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-13s %s\n", $$1, $$2}'

install:  ## Build .venv with the exact versions in uv.lock (incl. live extras)
	uv sync --locked --extra live

lock:  ## Re-resolve uv.lock after editing pyproject.toml by hand
	uv lock

upgrade:  ## Upgrade every package to the newest allowed version and rewrite uv.lock
	uv lock --upgrade
	uv sync --locked --extra live

env:  ## Create .env with an empty NASDAQ_DATA_LINK_API_KEY if it does not exist yet
	@if [ -f .env ]; then echo ".env already exists, left unchanged"; \
	else printf 'NASDAQ_DATA_LINK_API_KEY=\n' > .env && echo "Created .env, fill in NASDAQ_DATA_LINK_API_KEY"; fi

clean:  ## Remove the virtual environment and build artifacts
	rm -rf $(VENV) build dist src/*.egg-info
	find . -name __pycache__ -type d -prune -not -path "./$(VENV)/*" -exec rm -rf {} +

diagram-tools:  ## Download Structurizr CLI and PlantUML (pinned versions) into TOOLS, once per machine
	mkdir -p $(TOOLS)
	curl -fsSL -o $(TOOLS)/structurizr-cli.zip https://github.com/structurizr/cli/releases/download/v$(STRUCTURIZR_VERSION)/structurizr-cli.zip
	unzip -qo $(TOOLS)/structurizr-cli.zip -d $(TOOLS)/structurizr-cli
	curl -fsSL -o $(TOOLS)/plantuml.jar https://github.com/plantuml/plantuml/releases/download/v$(PLANTUML_VERSION)/plantuml-$(PLANTUML_VERSION).jar

diagrams:  ## Render docs/C4_Architecture/workspace.dsl to the SVGs in docs/C4_Architecture/
	mkdir -p $(PUML)
	rm -f $(PUML)/structurizr-*.puml $(PUML)/structurizr-*.svg
	PATH="$(dir $(JAVA)):$$PATH" bash $(TOOLS)/structurizr-cli/structurizr.sh export \
		-workspace $(ARCH)/workspace.dsl -format plantuml/structurizr -output $(PUML)
	$(JAVA) -Djava.awt.headless=true -jar $(TOOLS)/plantuml.jar -tsvg -charset UTF-8 $(LAYOUT) \
		$$(ls $(PUML)/structurizr-*.puml | grep -v -- '-key.puml')
	for f in $(PUML)/structurizr-*.svg; do \
		n=$$(basename $$f .svg); case $$n in *-key) continue;; esac; \
		cp $$f $(ARCH)/$${n#structurizr-}.svg; \
	done

diagrams-preview: diagrams  ## Also render PNGs into build/diagrams/ for reviewing layouts
	$(JAVA) -Djava.awt.headless=true -jar $(TOOLS)/plantuml.jar -tpng -charset UTF-8 $(LAYOUT) \
		$$(ls $(PUML)/structurizr-*.puml | grep -v -- '-key.puml')

data-diagrams:  ## Render the PlantUML data diagrams in docs/Data_architecture/ to SVG
	$(JAVA) -Djava.awt.headless=true -jar $(TOOLS)/plantuml.jar -tsvg -charset UTF-8 $(LAYOUT) \
		$(DATA)/*.puml

clean-bronze:  ## Delete all downloaded data in data/bronze
	@read -p "Delete everything in data/bronze? [y/N] " ans && [ "$$ans" = y ]
	find data/bronze -mindepth 1 -maxdepth 1 -exec rm -rf {} +
