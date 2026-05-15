.PHONY: help install install-dev install-docs clean test lint format type-check coverage \
        data figures paper docs serve-docs notebook release pre-commit hooks all

help:  ## show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ===== install =====

install:  ## install package in editable mode
	pip install -e .

install-dev:  ## install with dev extras
	pip install -e ".[dev]"
	pre-commit install

install-docs:  ## install with docs extras
	pip install -e ".[docs]"

# ===== quality =====

test:  ## run pytest
	pytest tests/ -v

coverage:  ## run tests with coverage report
	pytest tests/ --cov=robin_fpga --cov-report=term-missing --cov-report=html
	@echo "Coverage HTML report: htmlcov/index.html"

lint:  ## run ruff lint
	ruff check src/ tests/ scripts/

format:  ## run black formatter
	black src/ tests/ scripts/

type-check:  ## run mypy type checker
	mypy src/robin_fpga

pre-commit:  ## run all pre-commit hooks
	pre-commit run --all-files

# ===== data / experiments =====

data:  ## generate simulator data for all 13 paper figures
	python scripts/run_simulator.py --output data/results/ --seed 42

figures:  ## regenerate figures from data
	python scripts/generate_figures.py --data data/results/ --output paper/figures/

# ===== paper =====

paper:  ## build the LaTeX paper
	cd paper && pdflatex robin-fpga.tex && pdflatex robin-fpga.tex

# ===== docs =====

docs:  ## build sphinx documentation
	cd docs && sphinx-build -b html . _build/html

serve-docs:  ## serve docs at http://localhost:8000
	cd docs/_build/html && python -m http.server 8000

# ===== jupyter =====

notebook:  ## launch jupyter
	jupyter notebook notebooks/

# ===== release =====

release:  ## build distribution
	rm -rf dist/
	python -m build
	python -m twine check dist/*

# ===== aliases =====

clean:  ## remove build / cache artefacts
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete

all: install-dev test lint type-check  ## install + test + lint + type-check
