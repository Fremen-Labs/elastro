---
description: Elastro CLI E2E Testing Workflow
---
# Elastro CLI E2E Testing Workflow

This workflow automates the validation of the `elastro-client` command line interface. It runs a comprehensive test script against a local containerized Elasticsearch cluster and logs all results.

## Requirements
- A local Elasticsearch node running on `http://localhost:9200`.
- Python 3.9+ and `pipx` installed.
- Elastro basic auth configured using standard local cluster credentials.

## Steps

1. Configure authentication targeting the local daemon.
// turbo
```bash
cat << 'EOF' > ~/.elastic/config.yaml
elasticsearch:
  auth:
    password: changeme
    type: basic
    username: elastic
  hosts:
  - http://localhost:9200
  max_retries: 3
  retry_on_timeout: true
  timeout: 30
EOF
```

2. Force-install the local repository version to test structural modifications.
// turbo
```bash
cd elastro
pipx install . --force
```

3. Execute the E2E CLI Test suite.
// turbo
```bash
cd elastro
chmod +x test_cli_commands.sh
./test_cli_commands.sh
```

4. If any tests fail (Output reads `FAILED:`), use standard `mypy` and log review heuristics to resolve the error inside `elastro/cli/commands/*` or `elastro/core/*`.
