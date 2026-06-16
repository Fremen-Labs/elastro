# Contributing to Elastro

We follow industry-standard engineering practices to ensure `elastro` remains secure, reliable, and maintainable. This guide mirrors practices found in high-velocity engineering teams at Netflix, Google, and Microsoft.

## 1. Development Environment

We use `venv` for isolation and `pip-tools` for deterministic dependencies.

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dev dependencies
pip install -r requirements.txt
pip install -e ".[dev]"
```

## 2. Code Quality Standards

We enforce strict quality gates. All checks must pass before merging.

### Formatting & Linting
We use **Ruff** for formatting and linting.
```bash
ruff format .
ruff check --fix .
```

### Static Type Checking
We use **Mypy** in strict mode (Python 3.9+).
```bash
# Run type checks regarding core logic
mypy .
```
*Note: We currently exclude `tests/` and `examples/` from strict checks, but all core library code must be typed.*

### Security Scanning
We use **pip-audit**, **npm audit**, and **Trivy** (via ReleaseFlow) for dependency scanning.
```bash
# Full security gate (matches CI)
bash scripts/security-audit.sh
```
See `security/remediation-2026-06.md` for the audit record and documented suppressions.

## 3. Testing
We use **Pytest** for unit and integration testing.
```bash
pytest
```

## 4. Release Process
Releases are automated via GitHub Actions when a tag is pushed.

1.  **Bump Version**: Use `bumpversion` (do not edit files manually).
    ```bash
    bumpversion patch  # or minor/major
    ```
2.  **Push**:
    ```bash
    git push --tags
    ```
3.  **CI/CD**: The `pypi-publish.yml` workflow will:
    -   Run strict type checks (Mypy).
    -   Run security audits (Pip-Audit).
    -   Build the package.
    -   Publish to PyPI.

## 5. Project Structure
-   `elastro/`: Core package source.
-   `tests/`: Test suite.
-   `examples/`: User-facing examples (typed loosely).
-   `manifests/`: Kubernetes/Release manifests.
