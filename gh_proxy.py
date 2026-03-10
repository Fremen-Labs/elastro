from fastapi import FastAPI
import subprocess
import uvicorn

app = FastAPI()


@app.get("/run_gh")
def run_gh():
    try:
        out = subprocess.check_output(
            "gh pr create --fill && gh pr merge --merge --admin",
            shell=True,
            stderr=subprocess.STDOUT,
            cwd="/Users/jonathandoughty/clients/fremenlabs/elastic/elastic-github/elastro",
        )
        return {"status": "success", "output": out.decode("utf-8")}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "output": e.output.decode("utf-8")}
    except Exception as e:
        return {"status": "fatal", "output": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9205)
