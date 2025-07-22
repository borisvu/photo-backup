# Photo Backup System

Automated photo backup system to S3-compatible storage with comprehensive configuration management.

## Development Setup

### Prerequisites

- Python 3.8+
- Docker (for test infrastructure)
- Make (optional, for convenience commands)

### Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd photo-backup
   ```

2. **Install development dependencies**

   ```bash
   make install-dev
   # or manually:
   pip install -r requirements-dev.txt
   ```

3. **Set up pre-commit hooks (optional)**
   ```bash
   pre-commit install
   ```

## Code Quality Tools

This project uses several tools to maintain code quality:

### Linting and Formatting

- **Ruff**: Fast Python linter and formatter (replaces flake8 + isort + black)
- **MyPy**: Static type checker

### Available Commands

```bash
# Install dependencies
make install-dev

# Run linting
make lint

# Auto-fix linting issues
make lint-fix

# Format code
make format

# Check formatting (for CI)
make check

# Run tests
make test

# Clean up cache files
make clean

# Show all available commands
make help
```

### Manual Commands

```bash
# Linting
ruff check photo_backup/ tests/
ruff check --fix photo_backup/ tests/  # Auto-fix

# Formatting
ruff format photo_backup/ tests/

# Type checking
mypy photo_backup/

# Testing
pytest tests/ -v
```

## Configuration

- **Ruff**: Configured in `pyproject.toml`
- **MyPy**: Configured in `pyproject.toml`
- **Pre-commit**: Configured in `.pre-commit-config.yaml`

## Project Structure

```
photo-backup/
├── photo_backup/          # Main package
│   ├── config/           # Configuration management
│   ├── main.py           # CLI entry point
│   └── ...
├── tests/                # Test suite
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── functional/      # Functional tests
├── requirements.txt      # Production dependencies
├── requirements-dev.txt  # Development dependencies
├── pyproject.toml       # Tool configurations
├── Makefile            # Convenience commands
└── README.md           # This file
```

## Testing

The project includes comprehensive testing:

- **Unit Tests**: Test individual components
- **Integration Tests**: Test component interactions
- **Functional Tests**: Test end-to-end workflows

Run tests with:

```bash
make test              # All tests
make test-unit         # Unit tests only
make test-integration  # Integration tests only
make test-functional   # Functional tests only
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the quality checks:
   ```bash
   make pre-commit
   ```
5. Commit your changes
6. Submit a pull request

## License

MIT License - see LICENSE file for details.
