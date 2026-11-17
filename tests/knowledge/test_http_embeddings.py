"""Optional explicit HTTP provider configuration uses bounded real HTTP I/O."""

import asyncio
import importlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def test_configured_provider_executes_model_bound_embedding_over_http():
    # covers: KM-400c-2
    # covers: KM-400e-1
    # angle: seam
    module = importlib.import_module("knowledge.adapters.http_embeddings")
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = json.dumps({"vectors": [[1.0, 0.0]], "model": "synthetic-v1"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider = module.HttpEmbeddingProvider(
            f"http://127.0.0.1:{server.server_port}", "synthetic-v1", 2
        )
        assert asyncio.run(provider.embed(["approved summary"])) == [[1.0, 0.0]]
        assert received == [{"model": "synthetic-v1", "texts": ["approved summary"]}]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
