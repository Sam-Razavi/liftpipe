.DEFAULT_GOAL := help
UV ?= uv

.PHONY: help setup lint format test synthetic ingest

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

setup: ## Install Python dependencies
	$(UV) sync

lint: ## Run ruff lint and format checks
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## Auto-format and fix lint issues
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

test: ## Run the Python test suite
	$(UV) run pytest

synthetic: ## Generate synthetic Hevy and Apple Health exports into data/synthetic
	$(UV) run python -m liftpipe.synthetic --out data

ingest: ## Load exports for LIFTPIPE_SOURCE (default synthetic) into DuckDB raw tables
	$(UV) run python -m liftpipe.ingest
