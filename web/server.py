"""
Lightweight Web Server for Group Chat Semantic Search.
Provides REST APIs for search and benchmark results and serves the interactive UI.
Runs on standard library http.server without requiring external web frameworks.
"""

import sys
import os
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from search.query_parser import QueryParser
from search.retriever import GroupChatRetriever
from search.synthesizer import AnswerSynthesizer

WEB_DIR = Path(__file__).resolve().parent
EVAL_DIR = PROJECT_ROOT / "eval"

# Global search components
print("[Server] Initializing Search Pipeline...")
PARSER = QueryParser()
RETRIEVER = GroupChatRetriever()
SYNTHESIZER = AnswerSynthesizer()
print("[Server] Pipeline initialized.")


class SearchRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if path == "/" or path == "/index.html":
            self.serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        elif path == "/api/search":
            self.handle_search(query_params)
        elif path == "/api/benchmark":
            self.handle_benchmark()
        else:
            self.send_error(404, "File Not Found")

    def serve_file(self, file_path: Path, content_type: str):
        if not file_path.exists():
            self.send_error(404, "File Not Found")
            return
        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def handle_search(self, query_params):
        q = query_params.get("q", [""])[0].strip()
        if not q:
            self.send_json({"error": "Empty query"}, status=400)
            return

        parsed = PARSER.parse(q)
        hits = RETRIEVER.retrieve(parsed, top_k=5)

        if not hits:
            self.send_json({
                "query": q,
                "parsed": parsed.dict(),
                "hits": [],
                "answer": "No matching conversation was found for this query.",
                "context": []
            })
            return

        top_hit = hits[0]
        context_msgs = SYNTHESIZER.expand_context(top_hit["center_message_id"], above=5, below=4)
        answer = SYNTHESIZER.synthesize_answer(q, top_hit, context_msgs)

        response_data = {
            "query": q,
            "parsed": {
                "semantic_query": parsed.semantic_query,
                "sender_filter": parsed.sender_filter,
                "date_range": parsed.date_range,
                "is_open_ended": parsed.is_open_ended,
                "needs_clarification": parsed.needs_clarification
            },
            "hits": hits,
            "answer": answer,
            "context": context_msgs
        }
        self.send_json(response_data)

    def handle_benchmark(self):
        results_path = EVAL_DIR / "eval_results.json"
        if not results_path.exists():
            # Run eval if not present
            from eval.run_eval import run_evaluation
            run_evaluation()

        with open(results_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.send_json(data)

    def send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Silence routine request logging in terminal
        pass


def run_server(port: int = 8080):
    server_address = ("", port)
    httpd = HTTPServer(server_address, SearchRequestHandler)
    print(f"\n=======================================================")
    print(f"  Group Chat Search Web App Running on http://localhost:{port}")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
