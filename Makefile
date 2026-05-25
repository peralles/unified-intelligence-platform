# Atalhos para desenvolvedores — a lógica fica na CLI (integrator).
.PHONY: help setup status validate test

help:
	@./setup.sh help

setup:
	@./setup.sh

status:
	@./setup.sh status

validate:
	@./scripts/validate.sh

test:
	@uv run pytest -q --tb=short
