# Testing Strategy for Elastro

This directory contains all the tests for the Elastro module. The testing framework is built using pytest and follows these principles:

## Test Organization

- **Unit Tests**: Located in `tests/unit/` - Tests individual components in isolation with mocked dependencies
  - `tests/unit/core/` - Tests for core components (client, index, document, datastream, validation, errors)
  - `tests/unit/advanced/` - Tests for advanced features (scroll, query builder, aggregations)
  - `tests/unit/config/` - Tests for configuration management (loader, defaults)
  - `tests/unit/utils/` - Tests for utility functions (templates, snapshots, health, aliases)
- **Integration Tests**: Located in `tests/integration/` - Tests components interacting with a real Elasticsearch instance
  - Tests client, index, document, datastream operations
  - Tests workflow scenarios
  - Tests advanced features (scroll, query builder, aggregations)
- **Fixtures**: Located in `tests/fixtures/` - Contains reusable test data and mocks
  - Index fixtures
  - Document fixtures
  - Datastream fixtures

## Component Coverage

Our test suite covers:

- **Core Components**: 
  - ElasticsearchClient - Connection management, authentication, request handling
  - IndexManager - Index CRUD operations, settings, mappings
  - DocumentManager - Document operations, bulk processing
  - DatastreamManager - Datastream lifecycle management
  - Validation - Input validation using Pydantic
  - Error Handling - Custom exceptions and error scenarios

- **Advanced Features**:
  - Query Builder - Complex query construction
  - Scroll API - Efficient large dataset retrieval
  - Aggregations - Data analysis capabilities

- **Configuration**:
  - Config loading from files and environment
  - Default configurations

- **Utilities**:
  - Index templates management
  - Snapshot operations
  - Cluster health monitoring
  - Alias management

## Running Tests

The `run_tests.sh` script provides a convenient way to run tests with the proper environment setup.

### Command Line Options

```bash
./run_tests.sh [--unit] [--integration] [--all] [--keep-es-up]
```

- `--unit`: Run unit tests only (default if no options specified)
- `--integration`: Run integration tests only
- `--all`: Run both unit and integration tests
- `--keep-es-up`: Keep Elasticsearch container running after integration tests

### Unit Tests

To run unit tests with coverage reporting:

```bash
./run_tests.sh --unit
```

or simply:

```bash
./run_tests.sh
```

This will:
1. Create a virtual environment if one doesn't exist
2. Install necessary dependencies
3. Run all unit tests with coverage reporting
4. Generate an HTML coverage report in the `htmlcov/` directory

### Integration Tests

To run integration tests (requires Docker):

```bash
./run_tests.sh --integration
```

This will:
1. Check if Docker is running
2. Start an Elasticsearch container using Docker Compose
3. Wait for Elasticsearch to be ready
4. Set up test credentials and generate an API key
5. Run the integration tests with the `-m integration` marker
6. Stop the Elasticsearch container (unless `--keep-es-up` is specified)

If you want to keep the Elasticsearch container running after tests:

```bash
./run_tests.sh --integration --keep-es-up
```

### Running All Tests

To run both unit and integration tests:

```bash
./run_tests.sh --all
```

### Ingest Stress Tests

The `tests/integration/ingest_stress/` directory contains standalone python scripts used to profile, evaluate, and stress-test the `elastro ingest` CLI capabilities using various edge-case datasets (clean/dirty CSV, JSON, NDJSON, and SQL files).

To run the ingest evaluation script (which also regenerates the test data):
```bash
python3 tests/integration/ingest_stress/ingest_evaluator.py
```

To run the full ingest stress tester pipeline:
```bash
python3 tests/integration/ingest_stress/stress_tester.py
```

### Running Specific Tests

To run specific test files or directories manually:

```bash
# Run all tests in a specific directory
pytest tests/unit/core/ -v

# Run a specific test file
pytest tests/unit/core/test_client.py -v

# Run tests with a specific name pattern
pytest -k "test_index or test_document" -v
```

## Environment Variables

For integration tests, the following environment variables are used:

- `INTEGRATION_TESTS`: When set to any value, enables integration tests that require a running Elasticsearch instance.
- `TEST_ES_USERNAME`: Username for Elasticsearch authentication (default: "elastic")
- `TEST_ES_PASSWORD`: Password for Elasticsearch authentication (default: "elastic_password")
- `TEST_ES_API_KEY`: Base64-encoded API key generated for testing

## Test Coverage

The goal is to maintain at least 80% test coverage for core functionality. Current coverage report shows:
- Core components: >90% coverage
- Advanced features: >85% coverage
- Utilities: >80% coverage

Coverage reports are generated as HTML and can be viewed by opening `htmlcov/index.html` in a browser.

## Docker Setup

The `docker-compose.yml` file in the project root provides an isolated Elasticsearch instance for integration testing. It uses Elasticsearch 8.9.0 with security features disabled for testing purposes.

## Writing New Tests

When adding new functionality:

1. Create unit tests that mock all external dependencies
2. Create integration tests that verify real-world behavior
3. Add any necessary fixtures to the fixtures directory
4. Ensure test coverage meets or exceeds 80%
5. Test error conditions and edge cases thoroughly

### Test Best Practices

- Use descriptive test names that explain what is being tested
- Follow the Arrange-Act-Assert pattern
- Mock external dependencies in unit tests
- Test both successful scenarios and error conditions
- Use parametrized tests for testing multiple similar cases
- Keep test methods focused on testing a single aspect
- Use the `-m integration` marker for integration tests

## Continuous Integration

In a CI environment, unit tests should always be run. Integration tests can be conditionally run based on environment capabilities (Docker access).

The CI pipeline:
1. Sets up the Python environment
2. Installs dependencies
3. Runs linting checks
4. Runs unit tests
5. Conditionally runs integration tests
6. Generates and archives coverage reports 