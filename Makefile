.DEFAULT_GOAL := help
UV ?= uv
LIFTPIPE_SOURCE ?= synthetic
export LIFTPIPE_SOURCE
export LIFTPIPE_WAREHOUSE := $(CURDIR)/data/warehouse/liftpipe_$(LIFTPIPE_SOURCE).duckdb
export DBT_PROFILES_DIR := $(CURDIR)/dbt/liftpipe
export DBT_PROJECT_DIR := $(CURDIR)/dbt/liftpipe
DBT := $(UV) run dbt
export DAGSTER_HOME := $(CURDIR)/.dagster
DAGSTER_MODULE := liftpipe.orchestration.definitions

.PHONY: help setup lint format test synthetic ingest dbt export dbt-parse dagster pipeline demo real clean

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

dbt: ## Build and test all dbt models (seed, run, test)
	$(DBT) build

export: ## Export marts to dashboard/public/data as Parquet
	$(UV) run python -m liftpipe.export

dbt-parse:
	@$(DBT) parse --quiet

dagster: dbt-parse ## Open the Dagster UI at http://localhost:3000
	@mkdir -p $(DAGSTER_HOME)
	$(UV) run dagster dev -m $(DAGSTER_MODULE)

pipeline: dbt-parse ## Materialise every asset with Dagster (ingest, dbt build, export)
	@mkdir -p $(DAGSTER_HOME)
	$(UV) run dagster job execute -m $(DAGSTER_MODULE) -j refresh_all

demo: synthetic pipeline ## One command: synthetic data end to end

real: ## Run the pipeline on your own exports in data/real (never committed)
	$(MAKE) pipeline LIFTPIPE_SOURCE=real

clean: ## Remove generated data, warehouse and dbt artefacts
	rm -rf data/synthetic data/raw data/warehouse dbt/liftpipe/target dbt/liftpipe/logs .dagster
