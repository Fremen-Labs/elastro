import json
import csv
import subprocess
import os
import random
import time
from pathlib import Path

# Paths
WORKSPACE = Path("/Users/jonathandoughty/clients/fremenlabs/elastic/elastro")
SCRATCH = WORKSPACE / "scratch"
ELASTRO_BIN = WORKSPACE / ".venv" / "bin" / "elastro"


# Generate test data
def generate_data():
    print("Generating stress test data...")

    # 1. large.csv
    csv_path = SCRATCH / "large.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "value", "timestamp", "active"])
        for i in range(50000):
            writer.writerow(
                [
                    i,
                    f"User_{i}",
                    random.random() * 100,
                    f"2026-05-12T10:00:{i%60:02d}Z",
                    random.choice(["true", "false"]),
                ]
            )

    # 2. large.ndjson
    ndjson_path = SCRATCH / "large.ndjson"
    with open(ndjson_path, "w") as f:
        for i in range(50000):
            f.write(
                json.dumps(
                    {"id": i, "event": "click", "user_id": random.randint(1, 1000)}
                )
                + "\n"
            )

    # 3. large.json (JSON Array)
    json_path = SCRATCH / "large.json"
    with open(json_path, "w") as f:
        f.write("[\n")
        for i in range(20000):
            f.write(json.dumps({"item_id": i, "price": random.randint(10, 500)}))
            if i < 19999:
                f.write(",\n")
            else:
                f.write("\n")
        f.write("]\n")

    # 4. anomalous.csv
    anom_path = SCRATCH / "anomalous.csv"
    with open(anom_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "email", "ssn", "age"])
        for i in range(100):
            if i % 10 == 0:
                # Bad row
                writer.writerow([i, "bad_email", "not-an-ssn", "invalid_age"])
            else:
                # Good row with PII
                writer.writerow(
                    [
                        i,
                        f"user{i}@example.com",
                        f"123-45-{1000+i}",
                        random.randint(20, 60),
                    ]
                )

    # 5. sample_logs.txt
    logs_path = SCRATCH / "sample_logs.txt"
    with open(logs_path, "w") as f:
        f.write(
            '192.168.1.100 - user1 [12/May/2026:10:00:00 +0000] "GET /api/v1/status HTTP/1.1" 200 1234\n'
        )
        f.write(
            '10.0.0.5 - admin [12/May/2026:10:05:00 +0000] "POST /api/v1/data HTTP/1.1" 201 567\n'
        )

    # 6. pipeline_def.json
    pipe_path = SCRATCH / "pipeline_def.json"
    with open(pipe_path, "w") as f:
        json.dump(
            {
                "description": "Test",
                "processors": [{"set": {"field": "test", "value": "1"}}],
            },
            f,
        )

    print("Data generation complete.")


def run_cmd(cmd, input_str=None):
    print(f"Running: {' '.join(cmd)}")
    start = time.time()
    try:
        proc = subprocess.run(
            cmd, input=input_str, text=True, capture_output=True, check=False
        )
        elapsed = time.time() - start
        return proc.returncode, proc.stdout, proc.stderr, elapsed
    except Exception as e:
        return -1, "", str(e), time.time() - start


def stress_test():
    generate_data()

    issues = []

    # We will use an index name with a timestamp to avoid conflicts if Elastro connects to a real cluster
    idx = f"stress-test-{int(time.time())}"

    tests = [
        (
            "Import large CSV",
            [
                str(ELASTRO_BIN),
                "ingest",
                "import",
                str(SCRATCH / "large.csv"),
                "--index",
                f"{idx}-csv",
            ],
        ),
        (
            "Import large NDJSON",
            [
                str(ELASTRO_BIN),
                "ingest",
                "import",
                str(SCRATCH / "large.ndjson"),
                "--index",
                f"{idx}-ndjson",
            ],
        ),
        (
            "Import large JSON Array",
            [
                str(ELASTRO_BIN),
                "ingest",
                "import",
                str(SCRATCH / "large.json"),
                "--index",
                f"{idx}-json",
            ],
        ),
        (
            "Auto-map anomalous",
            [str(ELASTRO_BIN), "ingest", "auto-map", str(SCRATCH / "anomalous.csv")],
        ),
        (
            "Profile anomalous",
            [str(ELASTRO_BIN), "ingest", "profile", str(SCRATCH / "anomalous.csv")],
        ),
        (
            "Validate anomalous",
            [str(ELASTRO_BIN), "ingest", "validate", str(SCRATCH / "anomalous.csv")],
        ),
        (
            "Import with DLQ",
            [
                str(ELASTRO_BIN),
                "ingest",
                "import",
                str(SCRATCH / "anomalous.csv"),
                "--index",
                f"{idx}-dlq",
                "--validate",
                "--dlq",
                str(SCRATCH / "dlq.json"),
            ],
        ),
        (
            "Grok Builder from file",
            [
                str(ELASTRO_BIN),
                "ingest",
                "grok-builder",
                "--file",
                str(SCRATCH / "sample_logs.txt"),
            ],
        ),
        (
            "Pipeline Create",
            [
                str(ELASTRO_BIN),
                "ingest",
                "pipeline",
                "create",
                f"{idx}-pipe",
                "--file",
                str(SCRATCH / "pipeline_def.json"),
            ],
        ),
        (
            "Pipeline Wizard (non-interactive fallback/cancel)",
            [str(ELASTRO_BIN), "ingest", "pipeline", "wizard"],
        ),
    ]

    for name, cmd in tests:
        # Provide basic input for the wizard to exit immediately
        input_data = "test-pipe\n\n1\n\nN\nN\n\n" if "wizard" in name else None

        ret, out, err, elapsed = run_cmd(cmd, input_data)
        print(f"[{name}] Code: {ret}, Time: {elapsed:.2f}s")
        if ret != 0:
            print(f"ERROR OUTPUT:\n{err}\n{out}\n")
            issues.append(
                f"{name} failed with exit code {ret}. Error snippet: {err[:200]}..."
            )
        else:
            if "WARNING" in out or "ERROR" in out or "Exception" in out:
                issues.append(
                    f"{name} succeeded but contained warnings/errors in stdout."
                )

        # Check specific things
        if name == "Import with DLQ":
            if not (SCRATCH / "dlq.json").exists():
                issues.append("DLQ file was not created during 'Import with DLQ'.")
            else:
                sz = os.path.getsize(SCRATCH / "dlq.json")
                if sz == 0:
                    issues.append("DLQ file was created but is empty.")

    print("\n--- STRESS TEST COMPLETE ---")
    if issues:
        print("Issues found:")
        for i in issues:
            print(f"- {i}")
    else:
        print("No issues detected during execution.")


if __name__ == "__main__":
    stress_test()
