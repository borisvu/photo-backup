.PHONY: help install install-dev lint format check clean test test-unit test-functional test-integration

# Default target
help:
	@echo "Available commands:"
	@echo "  install      - Install production dependencies"
	@echo "  install-dev  - Install development dependencies"
	@echo "  lint         - Run all linting tools (ruff, mypy)"
	@echo "  lint-fix     - Auto-fix linting issues with ruff"
	@echo "  format       - Format code with ruff"
	@echo "  check        - Run linting and formatting checks"
	@echo "  clean        - Clean up cache and build files"
	@echo "  test         - Run all tests"
	@echo "  test-unit    - Run unit tests only"
	@echo "  test-functional - Run functional tests only"
	@echo "  test-integration - Run integration tests only"

# Install production dependencies
install:
	pip install -r requirements.txt

# Install development dependencies
install-dev:
	pip install -r requirements-dev.txt

# Run all linting tools
lint:
	@echo "Running ruff..."
	ruff check photo_backup/ tests/
	@echo "Running mypy..."
	mypy photo_backup/
	@echo "✅ Linting completed successfully!"

# Auto-fix linting issues with ruff
lint-fix:
	@echo "Auto-fixing linting issues with ruff..."
	ruff check --fix photo_backup/ tests/
	@echo "✅ Linting auto-fix completed!"

# Format code with ruff
format:
	@echo "Running ruff format..."
	ruff format photo_backup/ tests/
	@echo "✅ Code formatting completed successfully!"

# Check if code needs formatting (for CI)
check:
	@echo "Checking code formatting..."
	ruff format --check photo_backup/ tests/
	@echo "✅ Code formatting check passed!"

# Clean up cache and build files
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .coverage htmlcov/ 2>/dev/null || true
	@echo "✅ Cleanup completed!"

# Run all tests
test:
	python -m pytest tests/ -v

# Run unit tests only
test-unit:
	python -m pytest tests/unit/ -v

# Run functional tests only
test-functional:
	python -m pytest tests/functional/ -v

# Run integration tests only
test-integration:
	python -m pytest tests/integration/ -v

# Pre-commit hook: run all checks
pre-commit: format lint test
	@echo "✅ All pre-commit checks passed!" 