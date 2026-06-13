.PHONY: test venv lint build dev

# Ensure venv exists
venv:
	@test -d .venv || python3 -m venv .venv

# Single command to do everything: venv, install, run tests
test: venv
	@bash -c "\
		source .venv/bin/activate && \
		pip install -r requirements.txt && \
		pip install -r requirements-dev.txt && \
		export PYTHONPATH=\"\$$PYTHONPATH:$(PWD)/src\" && \
		pytest tests/ && \
		deactivate \
	"

# Lint all Python source with ruff (installs dev requirements into the venv first)
lint: venv
	@bash -c "\
		source .venv/bin/activate && \
		pip install -r requirements-dev.txt && \
		ruff check src jobs scripts tests && \
		deactivate \
	"

# Zip the main Lambda source into dist/, mirroring CI's upload action (source_directory ./src)
build:
	@mkdir -p dist
	@bash -c "cd src && zip -r ../dist/adomi-san-bot.zip ."
	@echo "Built dist/adomi-san-bot.zip"

# There is no local Discord stack — the bot only runs deployed behind API Gateway.
dev:
	@echo "There is no local development stack for this project."
	@echo "Discord interactions require a deployed endpoint (API Gateway -> Lambda)."
	@echo "Push to any non-main branch to deploy to dev via the 'Dev Pipeline' GitHub Actions workflow,"
	@echo "or trigger it manually with workflow_dispatch. Use 'make test' for local verification."
