# Contributing to Elastro

We welcome contributions to Elastro! If you'd like to contribute, please follow these guidelines:

## Development Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/elastro.git`
3. Install development dependencies: `pip install -e ".[dev]"`
4. Create a branch for your changes: `git checkout -b feature/your-feature-name`

## Code Standards

- Follow **PEP 8** style guidelines
- Use **type hints** for all method signatures and return values
- Write comprehensive **docstrings (PEP 257)** for all public classes and methods
- Keep files under **300 lines of code** maximum
- Implement custom exception classes for different error categories
- Validate inputs using **Pydantic** before processing

## Architecture Guidelines

- Maintain separation of concerns between core functionality and interfaces
- Design modular components with single responsibilities
- Follow **SOLID** principles
- Implement dependency injection for better testability
- Structure code by functionality rather than technology type

## Testing

- Write unit tests with **pytest** for all new functionality
- Maintain test coverage of at least **80%** for core functionality
- Run tests using `./run_tests.sh` before submitting a PR

## Submitting Changes

1. Ensure your code follows the project's standards
2. Write meaningful commit messages
3. Push your changes to your fork
4. Submit a pull request to the main repository
5. Describe your changes and the problem they solve

## Documentation

- Update documentation for any changed functionality
- Add examples for new features
- Write clear, concise docstrings for all public APIs
