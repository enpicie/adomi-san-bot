.PHONY: test venv

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
