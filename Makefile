# LLMSearchBench
#
# Two halves: the Python benchmark harness (uv) and the documentation site
# (npm, in docs/). `make check` gates both.
#
# Recipes avoid `.SHELLFLAGS` tricks on purpose — GNU make 3.81, which still
# ships on macOS, ignores it silently, so a pipefail set there buys nothing.

SHELL := /bin/sh

UV ?= uv
NPM ?= npm
DOCS_DIR := docs
SITE_PORT ?= 3000

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "; print "Targets:"} \
		/^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- Python ---------------------------------------------------------------

.PHONY: install
install: ## Install Python and site dependencies
	$(UV) sync
	cd $(DOCS_DIR) && $(NPM) install

.PHONY: sync
sync: ## Resolve and install Python dependencies only
	$(UV) sync

.PHONY: test
test: ## Run the Python test suite
	$(UV) run pytest

.PHONY: test-cov
test-cov: ## Run tests with a coverage report
	$(UV) run pytest --cov --cov-report=term-missing

.PHONY: lint
lint: ## Check formatting and lint rules
	$(UV) run ruff check .
	$(UV) run ruff format --check .

.PHONY: format
format: ## Apply formatting and autofixable lint rules
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

.PHONY: typecheck
typecheck: ## Type-check the harness
	$(UV) run mypy

.PHONY: check
check: lint typecheck test docs-typecheck ## Everything CI runs
	@echo "all checks passed"

# --- Data -----------------------------------------------------------------

.PHONY: data
data: ## Download every source dataset, skipping what already verifies
	$(UV) run llmsearchbench data download

.PHONY: data-one
data-one: ## Download one dataset — make data-one DATASET=retrievalqa
	@test -n "$(DATASET)" || { echo "set DATASET=<key>, see make data-list"; exit 2; }
	$(UV) run llmsearchbench data download --dataset $(DATASET)

.PHONY: data-verify
data-verify: ## Check raw data against the pinned checksums
	$(UV) run llmsearchbench data verify

.PHONY: data-list
data-list: ## Show the dataset registry
	$(UV) run llmsearchbench data list

.PHONY: data-clean
data-clean: ## Delete downloaded and derived data (re-fetchable)
	rm -rf data/raw data/processed

.PHONY: attribution
attribution: ## Regenerate licence, citation, and data-source files
	$(UV) run llmsearchbench attribution

.PHONY: attribution-check
attribution-check: ## Fail if the generated attribution files are stale
	$(UV) run llmsearchbench attribution
	git diff --exit-code -- attribution docs/content/data-sources.md data/datasets.lock.json

# --- Task sets ------------------------------------------------------------

.PHONY: tasks
tasks: ## Rebuild the tool-use-correctness task set from source data
	$(UV) run llmsearchbench tasks build

.PHONY: tasks-discrimination
tasks-discrimination: ## Rebuild the search-result-discrimination task set
	$(UV) run python scripts/extract_judged_passages.py
	$(UV) run llmsearchbench tasks build-discrimination

.PHONY: examples-discrimination
examples-discrimination: ## Write a page per discrimination item for the docs
	$(UV) run llmsearchbench examples-discrimination

.PHONY: tasks-stats
tasks-stats: ## Describe the committed task set
	$(UV) run llmsearchbench tasks stats

# --- Benchmark ------------------------------------------------------------

.PHONY: models
models: ## List the model catalogue
	$(UV) run llmsearchbench models

.PHONY: run
run: ## Run a model against the task set — make run MODEL=qwen/qwen3.5-27b
	@test -n "$(MODEL)" || { echo "set MODEL=<id>, see make models"; exit 2; }
	$(UV) run llmsearchbench run --model $(MODEL) $(ARGS)

.PHONY: score
score: ## Score a finished run — make score MODEL=qwen/qwen3.5-27b
	@test -n "$(MODEL)" || { echo "set MODEL=<id>, see make models"; exit 2; }
	$(UV) run llmsearchbench score --model $(MODEL)

.PHONY: leaderboard
leaderboard: ## Compare every model that has been run
	$(UV) run llmsearchbench leaderboard

.PHONY: publish
publish: ## Regenerate the leaderboard the documentation site renders
	$(UV) run llmsearchbench publish

# --- Documentation site ---------------------------------------------------

.PHONY: docs
docs: ## Start the docs dev server with hot reload
	cd $(DOCS_DIR) && $(NPM) start -- --port $(SITE_PORT)

.PHONY: docs-build
docs-build: ## Production build of the docs site
	cd $(DOCS_DIR) && $(NPM) run build

.PHONY: docs-serve
docs-serve: docs-build ## Serve the production build locally
	cd $(DOCS_DIR) && $(NPM) run serve -- --port $(SITE_PORT)

.PHONY: docs-typecheck
docs-typecheck: ## Type-check the docs site
	cd $(DOCS_DIR) && $(NPM) run typecheck

.PHONY: docs-version
docs-version: ## Freeze the current docs as a version — make docs-version VERSION=v0.1.0
	@test -n "$(VERSION)" || { echo "set VERSION=<version to freeze, e.g. v0.1.0>"; exit 2; }
	cd $(DOCS_DIR) && $(NPM) run version:cut -- $(VERSION)

# --- Housekeeping ---------------------------------------------------------

.PHONY: clean
clean: ## Remove build output and caches
	rm -rf $(DOCS_DIR)/build $(DOCS_DIR)/.docusaurus
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist
	find . -path ./$(DOCS_DIR)/node_modules -prune -o -name __pycache__ -type d -print0 \
		| xargs -0 rm -rf

.PHONY: clean-all
clean-all: clean ## Also remove installed dependencies
	rm -rf .venv $(DOCS_DIR)/node_modules
