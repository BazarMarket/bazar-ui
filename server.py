#!/usr/bin/env python3
import http.server
import socketserver
import os

PORT = 5000
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        host = self.headers.get('Host', '')
        is_production = 'bazar.uk' in host

        if self.path == '/api/config':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            import json
            self.wfile.write(json.dumps({'googleMapsApiKey': GOOGLE_MAPS_API_KEY}).encode())
            return

        if self.path.startswith('/api/products/'):
            import json
            product_id = self.path.split('/api/products/')[-1].split('?')[0]
            try:
                with open('products.json', 'r') as f:
                    products = json.load(f)
                product = products.get(product_id)
                if product:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps(product).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'{"error":"not found"}')
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"error":"server error"}')
            return

        if not is_production and (self.path == '/' or self.path == '/index.html'):
            self.path = '/dev-index.html'
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
