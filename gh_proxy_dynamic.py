import subprocess
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/run":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode("utf-8"))
            command = payload.get("command")
            cwd = payload.get(
                "cwd",
                "/Users/jonathandoughty/clients/fremenlabs/elastic/elastic-github/elastro",
            )

            try:
                out = subprocess.check_output(
                    command, shell=True, stderr=subprocess.STDOUT, cwd=cwd
                )
                response = {"status": "success", "output": out.decode("utf-8")}
            except subprocess.CalledProcessError as e:
                response = {
                    "status": "error",
                    "output": e.output.decode("utf-8"),
                    "code": e.returncode,
                }
            except Exception as e:
                response = {"status": "fatal", "output": str(e)}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    print("Starting dynamic command proxy on port 8901...")
    server = HTTPServer(("127.0.0.1", 8901), RequestHandler)
    server.serve_forever()
