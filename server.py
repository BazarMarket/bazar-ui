#!/usr/bin/env python3
import http.server
import socketserver

PORT = 5000

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.path = '/coming-soon.html'
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        pass

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

with ReusableTCPServer(("0.0.0.0", PORT), NoCacheHandler) as httpd:
    print(f"Serving on port {PORT}")
    httpd.serve_forever()
