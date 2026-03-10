from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess


class MyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Let's run mypy locally and check the errors
            res = subprocess.run(
                ["python3", "-m", "mypy", "elastro"], capture_output=True, text=True
            )
            output = (
                f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}\nEXIT:{res.returncode}"
            )

            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(output.encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))


if __name__ == "__main__":
    server_address = ("", 8009)
    try:
        httpd = HTTPServer(server_address, MyServer)
        print("Server running on port 8009")
        # Run exactly one request and then terminate
        httpd.handle_request()
    except Exception as e:
        print(f"Server error: {e}")
