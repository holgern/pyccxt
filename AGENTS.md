# AGENTS.md - pyccxt Project Guidelines

## Build & Testing Commands

- Run all tests: `pytest`
- Run single test: `pytest -k "test_name"`
- Run with coverage: `pytest --cov=pyccxt`
- Linting: `ruff .` or `pre-commit run --all-files`
- Do not use `git`, Never commit pull or push

## Code Style Guidelines

- Use [ruff](https://github.com/astral-sh/ruff) for formatting and linting
- Line length: 88 characters (E501)
- Import order: future, standard library, third-party, first-party, local-folder
- Class and function names: snake_case
- Constants: UPPER_CASE
- Type hints: Use for function parameters and return values
- Docstrings: Use for public functions and classes
- Error handling: Use explicit exception types with meaningful messages

## Pre-commit Hooks

This project uses pre-commit hooks for:

- Code formatting (ruff-format)
- Linting (ruff)
- File formatting (prettier, trailing whitespace, end-of-file fixing)
- Best practices (check-toml, check-yaml, debug-statements)

## Project goal

Usage of the public part of ccxt for reading ticker prices and market volumes. Find
overall price by market volume across different exchanges
