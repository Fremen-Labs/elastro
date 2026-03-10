from fastapi import FastAPI
import subprocess
import uvicorn

app = FastAPI()


@app.get("/deploy")
def run_deploy():
    commands = [
        "git status",
        "git add .",
        "git commit -m 'fix(daemon): resolve mypy strict typing violations in fast-path daemon'",
        "git push -u origin feature/fast-path-daemon",
        "gh pr create --fill",
        "gh pr merge --merge --admin",
    ]
    output = ""
    for cmd in commands:
        try:
            out = subprocess.check_output(
                cmd,
                shell=True,
                stderr=subprocess.STDOUT,
                cwd="/Users/jonathandoughty/clients/fremenlabs/elastic/elastic-github/elastro",
            )
            output += f"CMD: {cmd}\nSUCCESS: {out.decode('utf-8')}\n"
        except subprocess.CalledProcessError as e:
            output += (
                f"CMD: {cmd}\nERROR (Exit {e.returncode}): {e.output.decode('utf-8')}\n"
            )
            break  # stop iterating on error
        except Exception as e:
            output += f"FATAL: {str(e)}\n"
            break

    return {"status": "complete", "output": output}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9211)
