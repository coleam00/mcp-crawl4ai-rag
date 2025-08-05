.PHONY: install install-dev start test test-unit test-e2e lint format clean help

# Default target
help:
	@echo "Available commands:"
	@echo "  install     - Install production dependencies"
	@echo "  install-dev - Install development dependencies"
	@echo "  start       - Run the MCP server"
	@echo "  test        - Run unit tests (default)"
	@echo "  test-unit   - Run unit tests"
	@echo "  test-e2e    - Run E2E tests (requires MCP server)"
	@echo "  lint        - Run linting with fix enabled"
	@echo "  format      - Run formatting"
	@echo "  clean       - Remove temporary files like __pycache__"

# Install production dependencies
install:
	uv sync

# Install development dependencies (includes test dependencies and dev tools)
install-dev:
	uv sync --all-extras --group dev

# Run the MCP server
start:
	uv run src/crawl4ai_mcp.py

# Run all tests (default)
test:
	uv run pytest tests/ -v

# Run unit tests
test-unit:
	uv run pytest tests/unit/ -v

# Run E2E tests (requires MCP server running)
test-e2e:
	uv run pytest tests/e2e/ -v

# Run linting with fix enabled
lint:
	@echo "Installing and running ruff for linting..."
	uv add --dev ruff
	uv run ruff check --fix .

# Run formatting
format:
	@echo "Installing and running ruff for formatting..."
	uv add --dev ruff
	uv run ruff format .

# Remove temporary files and caches
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -rf .pytest_cache/ 2>/dev/null || true
	rm -rf .ruff_cache/ 2>/dev/null || true
	rm -rf htmlcov/ 2>/dev/null || true
	rm -rf .coverage 2>/dev/null || true
	rm -rf build/ 2>/dev/null || true
	rm -rf dist/ 2>/dev/null || true