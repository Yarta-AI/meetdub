.PHONY: install install-py dev doctor run lint clean

install:
	./install.sh

install-py:
	python3 scripts/bootstrap.py

dev:
	python3 -m pip install -e ".[dev]"

doctor:
	meetdub doctor

run:
	meetdub run --to ja

lint:
	ruff check meetdub
	ruff format --check meetdub

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
