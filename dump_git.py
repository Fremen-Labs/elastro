import subprocess


def run_cmd(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, stderr=subprocess.STDOUT
        ).decode("utf-8")
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e.output.decode('utf-8')}"


with open("git_dump.txt", "w") as f:
    f.write("--- GIT STATUS ---\n")
    f.write(run_cmd("git status"))
    f.write("\n--- GIT BRANCH ---\n")
    f.write(run_cmd("git branch -a"))
    f.write("\n--- GIT LOG ---\n")
    f.write(run_cmd("git log -n 5"))
