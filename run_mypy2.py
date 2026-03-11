import subprocess

try:
    with open("mypy_dump.txt", "w") as f:
        res = subprocess.run(
            ["python3", "-m", "mypy", "elastro"], capture_output=True, text=True
        )
        f.write(res.stdout)
        f.write("\n")
        f.write(res.stderr)
        f.write(f"\nExit code: {res.returncode}")
except Exception as e:
    with open("mypy_dump.txt", "w") as f:
        f.write(str(e))
