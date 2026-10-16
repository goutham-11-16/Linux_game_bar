.PHONY: all install uninstall test run diagnostics clean

all: test

install:
	./install.sh

uninstall:
	./uninstall.sh

test:
	PYTHONPATH=src .venv/bin/pytest tests/

run:
	./run.sh

diagnostics:
	./scripts/diagnostics.sh

clean:
	rm -rf .pytest_cache/ htmlcov/ .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
