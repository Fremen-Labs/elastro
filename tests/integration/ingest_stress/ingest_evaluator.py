import os
import json
import time
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent.parent.parent
SCRATCH = WORKSPACE / "tests" / "integration" / "ingest_stress" / "data"
ARTIFACTS = Path(
    "/Users/jonathandoughty/.gemini/antigravity/brain/e8ee424a-0e30-4543-a356-0ca3e27add02/artifacts"
)
BIN = WORKSPACE / ".venv" / "bin" / "elastro"


# 1. Generate Data
def generate_data():
    SCRATCH.mkdir(exist_ok=True, parents=True)
    ARTIFACTS.mkdir(exist_ok=True, parents=True)

    # Simple CSV
    with open(SCRATCH / "simple_clean.csv", "w") as f:
        f.write("id,name,age,active\n")
        for i in range(1, 101):
            f.write(f"{i},User {i},{20 + i},true\n")

    # Complex/Dirty CSV
    with open(SCRATCH / "complex_dirty.csv", "w") as f:
        f.write("id,name,tags,metadata,score,active\n")
        f.write('1,Alice,"admin,user","{""login"": ""2023""}",99.5,true\n')
        f.write('2,Bob,,,"invalid_score",false\n')  # Sparse, invalid type
        f.write('3,"Charlie, Jr.",, ,,\n')  # Commas in quotes, lots of empty
        f.write('4,Dave,"guest",,0,\n')

    # Simple JSON
    simple_json = [{"id": i, "name": f"User {i}", "age": 20 + i} for i in range(1, 101)]
    with open(SCRATCH / "simple_clean.json", "w") as f:
        json.dump(simple_json, f)

    # Complex/Dirty JSON
    complex_json = [
        {
            "id": 1,
            "name": "Alice",
            "settings": {"theme": "dark", "notifications": True},
            "roles": ["admin", "user"],
        },
        {"id": 2, "name": "Bob", "settings": None, "roles": []},  # Sparse
        {"id": "3_str", "name": 12345},  # Type mismatches relative to 1 and 2
        {"id": 4, "deep": {"nested": {"array": [1, 2, {"three": 3}]}}},  # Deeply nested
    ]
    with open(SCRATCH / "complex_dirty.json", "w") as f:
        json.dump(complex_json, f)

    # Simple NDJSON
    with open(SCRATCH / "simple_clean.ndjson", "w") as f:
        for i in range(1, 101):
            f.write(json.dumps({"id": i, "name": f"User {i}", "age": 20 + i}) + "\n")

    # Complex/Dirty NDJSON
    with open(SCRATCH / "complex_dirty.ndjson", "w") as f:
        f.write(json.dumps({"id": 1, "name": "Alice", "tags": ["a", "b"]}) + "\n")
        f.write(json.dumps({"id": 2}) + "\n")  # Sparse
        f.write(
            json.dumps({"id": 3, "name": "Charlie", "tags": "not_an_array_anymore"})
            + "\n"
        )
        f.write('{"id": 4, "broken_json": unquoted_value}\n')  # Malformed line

    # Simple SQL
    with open(SCRATCH / "simple_clean.sql", "w") as f:
        f.write("INSERT INTO users (id, name, age) VALUES ('1', 'Alice', '30');\n")
        f.write("INSERT INTO users (id, name, age) VALUES ('2', 'Bob', '25');\n")

    # Complex/Dirty SQL
    with open(SCRATCH / "complex_dirty.sql", "w") as f:
        # Multi-row insert, sparse values (NULL)
        f.write(
            "INSERT INTO users (id, name, role, score) VALUES ('1', 'Alice', 'admin', '100'), ('2', 'Bob', NULL, '50');\n"
        )
        f.write(
            "INSERT INTO users (id, name, role, score) VALUES ('3', 'Charlie', 'user', NULL);\n"
        )
        # SQL with extra spaces and quotes in strings
        f.write("INSERT  INTO  users   (id, name)  VALUES  ('4', 'Dave O''Connor');\n")


# 2. Run Tests
def run_tests():
    report = ["# Elastro Ingest Edge-Case Evaluation Report\n"]
    report.append(
        "This report documents the behavior of Elastro's data ingestion engine across various formats, evaluating its resilience against sparse, dirty, and deeply nested data structures.\n\n"
    )

    files_to_test = [
        "simple_clean.csv",
        "complex_dirty.csv",
        "simple_clean.json",
        "complex_dirty.json",
        "simple_clean.ndjson",
        "complex_dirty.ndjson",
        "simple_clean.sql",
        "complex_dirty.sql",
    ]

    for filename in files_to_test:
        filepath = SCRATCH / filename
        fmt = filename.split(".")[-1]

        # We will use auto-map validation to see how it handles mapping inference on dirty data,
        # then we will do a real import with --dlq to see how it drops bad rows.

        report.append(f"## Testing: `{filename}`\n")

        # 1. Profile
        cmd_profile = [BIN, "ingest", "profile", str(filepath)]
        proc_profile = subprocess.run(cmd_profile, capture_output=True, text=True)
        report.append(
            "### Data Profiling\n```text\n" + proc_profile.stdout.strip() + "\n```\n"
        )

        # 2. Validate (Schema Inference)
        # Skip validation inference for malformed NDJSON because python json.loads will hard crash the generator
        cmd_validate = [BIN, "ingest", "validate", str(filepath)]
        proc_validate = subprocess.run(cmd_validate, capture_output=True, text=True)
        report.append(
            "### Schema Inference (Validate without index)\n```text\n"
            + proc_validate.stdout.strip()
            + "\n```\n"
        )
        if proc_validate.stderr:
            report.append(
                "#### Errors:\n```text\n" + proc_validate.stderr.strip() + "\n```\n"
            )

        # 3. Import with DLQ
        idx_name = f"test-eval-{filename.replace('.', '-')}-{int(time.time())}"
        dlq_path = SCRATCH / f"dlq_{filename}.json"

        # We will turn on --validate so it strictly tries to coerce and drops rows if they fail
        cmd_import = [
            BIN,
            "ingest",
            "import",
            str(filepath),
            "--index",
            idx_name,
            "--dlq",
            str(dlq_path),
        ]
        if fmt == "sql":
            cmd_import.extend(["--format", "sql"])

        start = time.time()
        proc_import = subprocess.run(cmd_import, capture_output=True, text=True)
        elapsed = time.time() - start

        report.append(
            f"### Import Execution\n- **Time**: {elapsed:.2f}s\n- **Exit Code**: {proc_import.returncode}\n"
        )
        report.append("```text\n" + proc_import.stdout.strip() + "\n```\n")
        if proc_import.stderr:
            report.append(
                "#### Errors:\n```text\n" + proc_import.stderr.strip() + "\n```\n"
            )

        if dlq_path.exists() and os.path.getsize(dlq_path) > 0:
            with open(dlq_path, "r") as f:
                dlq_contents = f.read()
            report.append(
                f"#### Dead Letter Queue (DLQ)\n```json\n{dlq_contents.strip()}\n```\n"
            )

        report.append("---\n")

    report_path = ARTIFACTS / "elastro_edge_case_report.md"
    with open(report_path, "w") as f:
        f.write("\n".join(report))

    print(f"Tests complete. Report written to {report_path}")


if __name__ == "__main__":
    generate_data()
    run_tests()
