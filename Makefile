DB_CONTAINER := "matchmakeo-db"

clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

clean-build: ## Remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-pyc: ## Remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## Remove test and coverage artifacts
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache

.PHONY: lint
lint: ## Check code style
	@echo "+ $@"
	@uv run ruff check

.PHONY: test
test: export DJANGO_SETTINGS_MODULE = polarrouteserver.settings.test
test: ## Run tests quickly with the default Python
	@echo "+ $@"
	@uv run pytest

.PHONY: serve-docs
serve-docs: ## Serve the documentation in a development server
	@echo "+ $@"
	@uv run properdocs serve

.PHONY: start-db
start-db: ## Start a dev PostGIS instance in a docker container
	@echo "+ $@"
	@docker run --name ${DB_CONTAINER} --volume ./data/db:/var/lib/postgresql/data -p 5432:5432 -e POSTGRES_DB=matchmakeo -e POSTGRES_PASSWORD=password -d --rm postgis/postgis

.PHONY: stop-db
stop-db: ## Stop and remove a running database docker container
	@echo "+ $@"
	@docker stop ${DB_CONTAINER}

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

