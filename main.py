#!/usr/bin/env python3
"""Development server for the AI Constructor product prototype."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parent


class AppHandler(SimpleHTTPRequestHandler):
    """Serve the frontend and fall back to the app shell for client routes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):  # noqa: N802 - inherited HTTP verb naming
        if self.path not in {"/", "/index.html", "/styles.css", "/app.js"}:
            self.path = "/index.html"
        return super().do_GET()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"AI Constructor running at http://0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), AppHandler).serve_forever()
