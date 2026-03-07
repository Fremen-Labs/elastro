#!/bin/bash
LOG_FILE="test_results.log"
echo "Starting E2E test of elastro CLI 1.3.13" > "$LOG_FILE"

run_test() {
    CMD=$1
    echo "======================================" >> "$LOG_FILE"
    echo "Running: $CMD" | tee -a "$LOG_FILE"
    eval "$CMD" >> "$LOG_FILE" 2>&1
    if [ $? -eq 0 ]; then
        echo "SUCCESS: $CMD" | tee -a "$LOG_FILE"
    else
        echo "FAILED: $CMD" | tee -a "$LOG_FILE"
        # Print tail of log to console so we can see why it failed
        tail -n 15 "$LOG_FILE"
    fi
}

echo "Testing Utilities..."
run_test "elastro utils health"
run_test "elastro utils aliases list"

echo "Testing Indices..."
# Idempotent cleanup for local test re-runs
yes | elastro index delete test-auto-index || true
run_test "elastro index create test-auto-index"
run_test "elastro index exists test-auto-index"
run_test "elastro index get test-auto-index"
echo '{"index.number_of_replicas": 0}' > test_settings.json
run_test "elastro index update test-auto-index --settings test_settings.json"
run_test "elastro index close test-auto-index"
run_test "elastro index open test-auto-index"
run_test "elastro index list"
run_test "elastro index find test-auto-*"

echo "Testing Documents..."
echo '{"title": "Test doc", "content": "Hello World"}' > test_doc.json
run_test "elastro doc index test-auto-index --id doc-1 --file test_doc.json"
run_test "elastro doc get test-auto-index doc-1"
run_test "elastro doc search test-auto-index '*'"
echo '{"doc": {"title": "Updated doc"}}' > update_doc.json
run_test "elastro doc update test-auto-index doc-1 --file update_doc.json"
run_test "elastro doc delete test-auto-index doc-1"

echo "Testing Scripts..."
echo "ctx._source.new_field = 1" > test_script.painless
run_test "elastro script create test-file-script -f test_script.painless"
run_test "elastro script get test-file-script"
run_test "elastro script execute --id test-file-script --context '{\"visits\": 0}'"
run_test "elastro script list"
run_test "yes | elastro script delete test-file-script"

echo "Testing DataStreams..."
run_test "elastro datastream list"

echo "Cleaning up..."
run_test "yes | elastro index delete test-auto-index"

echo "Finished. Look at $LOG_FILE for full output."
