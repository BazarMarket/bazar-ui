#!/usr/bin/env python3
import http.server
import socketserver
import os
import json

PORT = 5000
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')
STRIPE_SECRET_KEY   = os.environ.get('STRIPE_SECRET_KEY', '')

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/boost-checkout':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                data = {}

            return_url  = data.get('return_url', 'http://localhost:5000')
            listing_id  = data.get('listing_id', '')
            firebase_uid = data.get('firebase_uid', '')

            sep = '&' if '?' in return_url else '?'
            success_url = return_url + sep + 'boosted=1&session_id={CHECKOUT_SESSION_ID}'
            cancel_url  = return_url

            try:
                import stripe
                stripe.api_key = STRIPE_SECRET_KEY
                session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'gbp',
                            'unit_amount': 100,
                            'product_data': {'name': 'Boost to Top'},
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata={
                        'firebase_uid': firebase_uid,
                        'listing_id': listing_id,
                        'source': 'boost_to_top',
                    },
                )
                resp = json.dumps({'success': True, 'url': session.url}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(resp)
            except Exception as e:
                resp = json.dumps({'success': False, 'error': str(e)}).encode()
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(resp)
            return

        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        host = self.headers.get('Host', '')
        is_production = 'bazar.uk' in host

        if self.path == '/api/config':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'googleMapsApiKey': GOOGLE_MAPS_API_KEY}).encode())
            return

        if self.path.startswith('/api/products/'):
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
