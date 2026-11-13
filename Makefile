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

# Install production dependencies only (no dev group)
install:
	uv sync --no-dev

# Install all dependencies including the dev group
install-dev:
	uv sync

# Run all linting tools
lint:
	@echo "Running ruff..."
	uv run ruff check photo_backup/ tests/
	@echo "Running mypy..."
	uv run mypy photo_backup/
	@echo "✅ Linting completed successfully!"

# Auto-fix linting issues with ruff
lint-fix:
	@echo "Auto-fixing linting issues with ruff..."
	uv run ruff check --fix photo_backup/ tests/
	@echo "✅ Linting auto-fix completed!"

# Format code with ruff
format:
	@echo "Running ruff format..."
	uv run ruff format photo_backup/ tests/
	@echo "✅ Code formatting completed successfully!"

# Check if code needs formatting (for CI)
check:
	@echo "Checking code formatting..."
	uv run ruff format --check photo_backup/ tests/
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
	uv run pytest tests/ -v

# Run unit tests only
test-unit:
	uv run pytest tests/unit/ -v

# Run functional tests only
test-functional:
	uv run pytest tests/functional/ -v

# Run integration tests only
test-integration:
	uv run pytest tests/integration/ -v

# Pre-commit hook: run all checks
pre-commit: format lint test
	@echo "✅ All pre-commit checks passed!" 