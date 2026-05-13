import http.server
import os
import socketserver
import urllib.parse
import urllib.request

ROOT = r"F:\Whiteout Survival Bot\frontend-dashboard"
BACKEND = "http://140.245.241.54:8080"
PORT = 4173


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = urllib.parse.urlparse(path).path
        path = os.path.normpath(urllib.parse.unquote(path).lstrip("/"))
        return os.path.join(ROOT, path)

    def do_GET(self):
        if self.path.startswith("/api/"):
            try:
                request = urllib.request.Request(
                    BACKEND + self.path,
                    headers={"Accept": self.headers.get("Accept", "application/json")},
                )
                with urllib.request.urlopen(request, timeout=15) as response:
                    body = response.read()
                    self.send_response(response.status)
                    self.send_header(
                        "Content-Type",
                        response.headers.get("Content-Type", "application/json"),
                    )
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
            except Exception as exc:
                body = (
                    '{"error":"proxy_unavailable","detail":"'
                    + str(exc).replace('"', '\\"')
                    + '"}'
                ).encode()
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            return
        super().do_GET()


with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as server:
    server.serve_forever()
