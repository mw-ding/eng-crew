"""A12 sample service and API: svc.py DIR binds a free loopback port, writes it to DIR/port and logs to DIR/log.

GET /health answers 200 {"status": "ok"}; POST /items with {"name": ...} answers 201 with the new item;
GET / is the web view; any other path answers 404 {"error": "not found"}.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

DIR = sys.argv[1]
ITEMS = []


def log(line):
    with open(os.path.join(DIR, "log"), "a") as fh:
        fh.write(line + "\n")


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body, kind="application/json"):
        data = (body if kind == "text/html" else json.dumps(body)).encode()
        log("%s %s %d" % (self.command, self.path, status))
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self.reply(200, {"status": "ok"})
        elif self.path == "/":
            self.reply(200, "<h1>Items</h1><ul>%s</ul>" % "".join("<li>%s</li>" % i["name"] for i in ITEMS), "text/html")
        else:
            self.reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/items":
            return self.reply(404, {"error": "not found"})
        name = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["name"]
        ITEMS.append({"id": len(ITEMS) + 1, "name": name})
        self.reply(201, ITEMS[-1])

    def log_message(self, *args):
        pass


server = HTTPServer(("127.0.0.1", 0), Handler)
log("ready")
with open(os.path.join(DIR, "port.tmp"), "w") as fh:
    fh.write(str(server.server_address[1]))
os.replace(os.path.join(DIR, "port.tmp"), os.path.join(DIR, "port"))
server.serve_forever()
