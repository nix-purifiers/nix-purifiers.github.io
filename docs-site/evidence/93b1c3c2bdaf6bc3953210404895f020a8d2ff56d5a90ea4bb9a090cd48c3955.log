# SPDX-License-Identifier: MIT
#
# A stand-in for the upload API of luarocks.org, for the publish tests:
#
#   python3 fake-luarocks-server.py UPLOAD-DIR PORT-FILE
#
# It listens on a free port of 127.0.0.1, writes the port to PORT-FILE, and
# keeps every file `luarocks upload` sends in UPLOAD-DIR, under the file name
# the client gives.

import email.parser
import email.policy
import http.server
import json
import os
import sys

upload_dir, port_file = sys.argv[1], sys.argv[2]
os.makedirs(upload_dir, exist_ok=True)


class Handler(http.server.BaseHTTPRequestHandler):
    def reply(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/api/tool_version":
            params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
            self.reply({"version": params.get("current", "")})
        elif path.endswith("/status"):
            self.reply({"user_id": 1})
        elif path.endswith("/check_rockspec"):
            self.reply({})
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
            b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + body
        )
        for part in message.iter_parts():
            name = part.get_filename()
            if name:
                payload = part.get_payload(decode=True)
                assert isinstance(payload, bytes)
                with open(os.path.join(upload_dir, os.path.basename(name)), "wb") as f:
                    f.write(payload)
        if self.path.endswith("/upload"):
            self.reply({"is_new": False, "manifests": ["root"], "module_url": "http://127.0.0.1/m", "version": {"id": 1}})
        else:
            self.reply({"rock": {"id": 1}})

    def log_message(self, format, *args):
        pass


server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
with open(port_file + ".tmp", "w") as f:
    f.write(str(server.server_address[1]))
os.rename(port_file + ".tmp", port_file)
server.serve_forever()
