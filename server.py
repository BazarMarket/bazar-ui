#!/usr/bin/env python3
"""
Bazar – production HTTP server with server-side SEO injection.

Architecture (Path B):
  resolve_page_type(path, qs) → (page_type, params)
  fetch_seo_data(page_type, params) → seo_dict
  build_seo_head(seo_dict) → html_string
  inject_seo(html, seo_head) → html

nginx proxies *.html page requests here; static assets bypass Python.
Same HTML is returned to users and crawlers – no bot-only rendering.
"""

import http.server
import socketserver
import os
import json
import re
import urllib.request
import urllib.parse
import time
import threading

# ── Configuration ─────────────────────────────────────────────────────────────
PORT               = 5000
PUBLIC_DOMAIN      = 'https://www.bazar.uk'
LARAVEL_API_HOST   = 'admin.bazar.uk'
LARAVEL_API_BASE   = 'http://localhost/api'
SITE_ROOT          = os.environ.get('BAZAR_SITE_ROOT', os.path.dirname(os.path.abspath(__file__)))
SEO_CACHE_TTL      = 300  # seconds (5 min)
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')
STRIPE_SECRET_KEY   = os.environ.get('STRIPE_SECRET_KEY', '')

# ── In-memory SEO cache ───────────────────────────────────────────────────────
_cache: dict = {}
_cache_lock = threading.Lock()

def _cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and time.time() - entry['ts'] < SEO_CACHE_TTL:
            return entry['data']
    return None

def _cache_set(key, data):
    with _cache_lock:
        _cache[key] = {'ts': time.time(), 'data': data}


# ══════════════════════════════════════════════════════════════════════════════
# Layer 1 – Page type resolver
# ══════════════════════════════════════════════════════════════════════════════
INTERNAL_PAGES = {
    'cabinet.html', 'post-ad.html', 'messages.html', 'favorites.html',
    'withdrawals.html', 'payments-policy.html', 'refund-policy.html',
    'privacy-policy.html', 'cookie-policy.html', 'terms.html',
}

def resolve_page_type(path: str, qs: str = '') -> tuple:
    """
    Returns (page_type, params_dict).
    page_type: homepage | listing | category | category_city |
               category_city_district | search | internal | other
    """
    p = path.lstrip('/')

    if p in ('', 'index.html'):
        return 'homepage', {}

    # card.html?id=123  (current listing URL)
    if p == 'card.html':
        qp = urllib.parse.parse_qs(qs)
        lid = qp.get('id', [None])[0]
        if lid:
            return 'listing', {'id': lid}
        return 'other', {}

    # /listing/{id}  (clean SEO URL – served as card.html content)
    m = re.match(r'^listing/(\d+)$', p)
    if m:
        return 'listing', {'id': m.group(1)}

    # search
    if p == 'search.html' or p.startswith('search'):
        return 'search', {}

    # internal / private pages
    if p in INTERNAL_PAGES:
        return 'internal', {}

    # static assets – let them pass through unchanged
    if '.' in p.split('/')[-1]:
        return 'other', {}

    parts = [x for x in p.split('/') if x]
    if len(parts) == 3:
        return 'category_city_district', {
            'category': parts[0], 'city': parts[1], 'district': parts[2]
        }
    if len(parts) == 2:
        return 'category_city', {'category': parts[0], 'city': parts[1]}
    if len(parts) == 1:
        return 'category', {'category': parts[0]}

    return 'other', {}


# ══════════════════════════════════════════════════════════════════════════════
# Layer 2 – SEO data fetcher
# ══════════════════════════════════════════════════════════════════════════════
CATEGORY_LABELS = {
    'property': 'Property',    'real-estate': 'Property',
    'cars': 'Cars',            'motors': 'Motors',
    'vehicles': 'Vehicles',    'rooms': 'Rooms',
    'jobs': 'Jobs',            'electronics': 'Electronics',
    'furniture': 'Furniture',  'fashion': 'Fashion',
    'services': 'Services',    'pets': 'Pets',
    'sports': 'Sports',        'kids': 'Kids',
    'garden': 'Garden',        'tools': 'Tools',
}

CURRENCY_SYMBOL = {'GBP': '£', 'USD': '$', 'EUR': '€'}

def _api_get(path: str, cache_key: str = None):
    """HTTP GET to the Laravel API with caching."""
    if cache_key:
        cached = _cache_get(cache_key)
        if cached:
            return cached

    # Try internal (same-server) request first
    for url, headers in [
        (f'{LARAVEL_API_BASE}{path}', {'Host': LARAVEL_API_HOST}),
        (f'https://{LARAVEL_API_HOST}/api{path}', {}),
    ]:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if isinstance(data, dict) and data.get('error'):
                    continue
                if cache_key:
                    _cache_set(cache_key, data)
                return data
        except Exception:
            continue
    return None


def _default_seo():
    return {
        'title':       'Free UK Classifieds – Buy & Sell | Bazar',
        'description': 'Post free ads in the UK. Buy and sell property, cars, '
                       'electronics and more on Bazar.',
        'canonical':   PUBLIC_DOMAIN + '/',
        'og_image':    PUBLIC_DOMAIN + '/img/og-bazar.jpg',
        'robots':      'index, follow',
        'json_ld':     None,
    }


def fetch_seo_data(page_type: str, params: dict) -> dict:
    seo = _default_seo()

    # ── Homepage ──────────────────────────────────────────────────────────────
    if page_type == 'homepage':
        seo['canonical'] = PUBLIC_DOMAIN + '/'
        seo['json_ld'] = json.dumps({
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Bazar",
            "url": PUBLIC_DOMAIN,
            "description": seo['description'],
            "potentialAction": {
                "@type": "SearchAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": f"{PUBLIC_DOMAIN}/search.html?q={{search_term_string}}"
                },
                "query-input": "required name=search_term_string"
            }
        })
        return seo

    # ── Listing page ──────────────────────────────────────────────────────────
    elif page_type == 'listing':
        lid = params.get('id', '')
        listing = _api_get(f'/properties/{lid}', f'listing_{lid}')

        if not listing:
            # API returned nothing – noindex, let JS handle it
            seo['canonical'] = f'{PUBLIC_DOMAIN}/listing/{lid}'
            seo['robots'] = 'noindex, follow'
            return seo

        # ── Status check: only active listings are indexable ──────────────────
        status = listing.get('status', 'active')
        if status != 'active':
            seo['canonical'] = f'{PUBLIC_DOMAIN}/listing/{lid}'
            seo['robots'] = 'noindex, follow'
            # Still return partial data so H1/breadcrumbs render server-side
            # (page will still load for logged-in users via JS)

        title        = listing.get('title') or 'Listing'
        city         = listing.get('city') or ''
        district     = listing.get('district') or ''
        price        = listing.get('price') or ''
        currency     = listing.get('currency') or 'GBP'
        prop_type    = listing.get('property_type') or ''
        listing_type = listing.get('listing_type') or 'sale'
        description  = listing.get('description') or ''
        images       = listing.get('images') or []
        bedrooms     = listing.get('bedrooms')

        symbol = CURRENCY_SYMBOL.get(currency, currency)

        # Price string
        try:
            price_str = f'{symbol}{float(price):,.0f}'
        except (ValueError, TypeError):
            price_str = ''

        # ── Title formula ─────────────────────────────────────────────────────
        # With district:    "{title} in {district}, {city} – £{price} | Bazar"
        # Without district: "{title} in {city} – £{price} | Bazar"
        if district and city:
            location_str = f'{district}, {city}'
        elif city:
            location_str = city
        else:
            location_str = 'UK'

        raw_title = f'{title} in {location_str}'
        if price_str:
            raw_title += f' – {price_str}'
        raw_title += ' | Bazar'
        seo_title = raw_title[:65] + '…' if len(raw_title) > 68 else raw_title

        # ── Meta description ──────────────────────────────────────────────────
        if description and len(description) > 20:
            desc = description[:155] + '…' if len(description) > 158 else description
        else:
            loc_phrase = f'in {location_str}' if location_str != 'UK' else 'in the UK'
            price_phrase = f'Price: {price_str}. ' if price_str else ''
            desc = f'{title} {loc_phrase}. {price_phrase}Browse this listing on Bazar UK classifieds.'
            if len(desc) > 160:
                desc = desc[:157] + '…'

        canonical = f'{PUBLIC_DOMAIN}/listing/{lid}'

        # OG image
        og_image = seo['og_image']
        if images:
            img = images[0]
            og_image = img if img.startswith('http') else f'{PUBLIC_DOMAIN}/storage/{img}'

        # ── Breadcrumb labels ─────────────────────────────────────────────────
        action_label = {
            'sale': 'for sale', 'long_rent': 'to rent',
            'short_rent': 'to rent', 'Sale': 'for sale',
            'Long_rent': 'to rent', 'Short_rent': 'to rent',
        }.get(listing_type, 'for sale')
        cat_label  = f'Property {action_label}'
        type_label = prop_type.replace('_', ' ').title() if prop_type else 'Property'

        # ── JSON-LD ───────────────────────────────────────────────────────────
        real_estate_types = {'apartment', 'house', 'flat', 'room', 'villa',
                             'studio', 'bungalow', 'maisonette', 'cottage'}
        is_real_estate = prop_type.lower() in real_estate_types

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": cat_label, "item": f"{PUBLIC_DOMAIN}/property"},
                {"@type": "ListItem", "position": 3,
                 "name": title, "item": canonical},
            ]
        }

        if is_real_estate:
            schema = {
                "@context": "https://schema.org",
                "@type": "WebPage",
                "name": seo_title,
                "description": desc,
                "url": canonical,
                "breadcrumb": breadcrumb_schema,
            }
        else:
            schema = {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": title,
                "description": desc,
                "url": canonical,
                "image": og_image,
                "offers": {
                    "@type": "Offer",
                    "price": str(price) if price else "0",
                    "priceCurrency": currency,
                    "availability": "https://schema.org/InStock",
                    "url": canonical,
                    "seller": {"@type": "Organization", "name": "Bazar"}
                }
            }

        # ── SSR blocks: visible H1 + breadcrumbs injected into body ──────────
        seo['ssr'] = {
            'prop_title':  title,
            'breadcrumbs': [
                ('Home', '/'),
                (cat_label, '/property'),
                (type_label, None),
            ],
        }

        if status == 'active':
            seo.update({
                'title':       seo_title,
                'description': desc,
                'canonical':   canonical,
                'og_image':    og_image,
                'json_ld':     json.dumps(schema),
            })
        return seo

    # ── Category ──────────────────────────────────────────────────────────────
    elif page_type == 'category':
        cat       = params.get('category', '')
        cat_label = CATEGORY_LABELS.get(cat, cat.replace('-', ' ').title())
        canonical = f'{PUBLIC_DOMAIN}/{cat}'
        seo.update({
            'title':       f'{cat_label} for sale UK | Bazar',
            'description': f'Browse {cat_label.lower()} listings across the UK. '
                           f'Find great deals on Bazar UK classifieds.',
            'canonical':   canonical,
            'json_ld':     json.dumps({
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1,
                     "name": "Home", "item": PUBLIC_DOMAIN},
                    {"@type": "ListItem", "position": 2,
                     "name": cat_label, "item": canonical},
                ]
            }),
        })
        return seo

    # ── Category + city ───────────────────────────────────────────────────────
    elif page_type == 'category_city':
        cat       = params.get('category', '')
        city_slug = params.get('city', '')
        city      = city_slug.replace('-', ' ').title()
        cat_label = CATEGORY_LABELS.get(cat, cat.replace('-', ' ').title())
        canonical = f'{PUBLIC_DOMAIN}/{cat}/{city_slug}'
        seo.update({
            'title':       f'{cat_label} for sale in {city} | Bazar',
            'description': f'Browse {cat_label.lower()} listings in {city}. '
                           f'Find great local deals on Bazar UK classifieds.',
            'canonical':   canonical,
            'json_ld':     json.dumps({
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1,
                     "name": "Home", "item": PUBLIC_DOMAIN},
                    {"@type": "ListItem", "position": 2,
                     "name": cat_label, "item": f"{PUBLIC_DOMAIN}/{cat}"},
                    {"@type": "ListItem", "position": 3,
                     "name": city, "item": canonical},
                ]
            }),
        })
        return seo

    # ── Category + city + district (noindex by default) ───────────────────────
    elif page_type == 'category_city_district':
        cat      = params.get('category', '')
        city     = params.get('city', '').replace('-', ' ').title()
        district = params.get('district', '').replace('-', ' ').title()
        cat_label = CATEGORY_LABELS.get(cat, cat.replace('-', ' ').title())
        canonical = (f'{PUBLIC_DOMAIN}/{params["category"]}/'
                     f'{params["city"]}/{params["district"]}')
        seo.update({
            'title':       f'{cat_label} in {district}, {city} | Bazar',
            'description': f'Browse {cat_label.lower()} in {district}, {city}.',
            'canonical':   canonical,
            'robots':      'noindex, follow',   # activate per district later
        })
        return seo

    # ── Search (noindex always) ───────────────────────────────────────────────
    elif page_type == 'search':
        seo.update({
            'title':   'Search | Bazar',
            'robots':  'noindex, follow',
        })
        return seo

    # ── Internal / private pages ──────────────────────────────────────────────
    elif page_type == 'internal':
        seo['robots'] = 'noindex, nofollow'
        return seo

    return seo


# ══════════════════════════════════════════════════════════════════════════════
# Layer 3 – SEO head builder
# ══════════════════════════════════════════════════════════════════════════════
def _esc(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def _attr(s: str) -> str:
    return s.replace('"', '&quot;')

def build_seo_head(seo: dict) -> str:
    title    = _esc(seo['title'])
    desc     = _attr(seo['description'])
    canon    = _attr(seo['canonical'])
    og_image = _attr(seo['og_image'])
    robots   = _attr(seo['robots'])
    og_title = _attr(seo['title'])
    og_desc  = _attr(seo['description'])
    json_ld  = seo.get('json_ld')

    lines = [
        f'<title>{title}</title>',
        f'<meta name="description" content="{desc}">',
        f'<link rel="canonical" href="{canon}">',
        f'<meta name="robots" content="{robots}">',
        f'<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="Bazar">',
        f'<meta property="og:url" content="{canon}">',
        f'<meta property="og:title" content="{og_title}">',
        f'<meta property="og:description" content="{og_desc}">',
        f'<meta property="og:image" content="{og_image}">',
        f'<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{og_title}">',
        f'<meta name="twitter:description" content="{og_desc}">',
        f'<meta name="twitter:image" content="{og_image}">',
    ]
    if json_ld:
        lines.append(f'<script type="application/ld+json">{json_ld}</script>')

    return '\n    '.join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# Layer 4 – HTML injector
# ══════════════════════════════════════════════════════════════════════════════
_RE_TITLE      = re.compile(r'<title[^>]*>.*?</title>', re.I | re.S)
_RE_DESC       = re.compile(r'<meta\s[^>]*name=["\']description["\'][^>]*/?>', re.I)
_RE_ROBOTS     = re.compile(r'<meta\s[^>]*name=["\']robots["\'][^>]*/?>', re.I)
_RE_CANONICAL  = re.compile(r'<link\s[^>]*rel=["\']canonical["\'][^>]*/?>', re.I)
_RE_OG         = re.compile(r'<meta\s[^>]*property=["\']og:[^"\']*["\'][^>]*/?>', re.I)
_RE_TWITTER    = re.compile(r'<meta\s[^>]*name=["\']twitter:[^"\']*["\'][^>]*/?>', re.I)
_RE_JSON_LD    = re.compile(
    r'<script\s[^>]*type=["\']application/ld\+json["\'][^>]*>.*?</script>',
    re.I | re.S
)
_RE_HEAD_OPEN   = re.compile(r'(<head[^>]*>)', re.I)
_RE_PROP_TITLE  = re.compile(r'(id="prop-title"[^>]*>)[^<]*(</)', re.I)
_RE_BREADCRUMB  = re.compile(r'(<ul[^>]+id="breadcrumb"[^>]*>).*?(</ul>)', re.I | re.S)

def inject_seo(html: str, seo_head: str) -> str:
    """Strip old SEO tags, inject fresh ones right after <head>."""
    html = _RE_TITLE.sub('', html)
    html = _RE_DESC.sub('', html)
    html = _RE_ROBOTS.sub('', html)
    html = _RE_CANONICAL.sub('', html)
    html = _RE_OG.sub('', html)
    html = _RE_TWITTER.sub('', html)
    html = _RE_JSON_LD.sub('', html)

    # Use string find/replace to avoid re.sub interpreting seo_head
    # as a replacement pattern (backslashes in JSON-LD break re.sub)
    m = _RE_HEAD_OPEN.search(html)
    if m:
        insert_at = m.end()
        html = html[:insert_at] + '\n    ' + seo_head + html[insert_at:]
    return html


def inject_ssr_body(html: str, ssr: dict) -> str:
    """Inject visible H1 and breadcrumbs into the body so Googlebot
    sees real content without waiting for JavaScript."""

    # ── Replace placeholder title in #prop-title ──────────────────────────────
    prop_title = ssr.get('prop_title', '')
    if prop_title:
        m = _RE_PROP_TITLE.search(html)
        if m:
            html = html[:m.start()] + m.group(1) + _esc(prop_title) + m.group(2) + html[m.end():]

    # ── Replace breadcrumb list in #breadcrumb ────────────────────────────────
    breadcrumbs = ssr.get('breadcrumbs', [])
    if breadcrumbs:
        items = []
        for i, (label, href) in enumerate(breadcrumbs):
            is_last = (i == len(breadcrumbs) - 1)
            safe_label = _esc(label)
            if not is_last:
                link = f'<a href="{href}">{safe_label}</a>'
                items.append(f'<li>{link}<span class="icon-arrow-r"></span></li>')
            else:
                items.append(f'<li><span>{safe_label}</span></li>')
        new_ul = '<ul class="bread-custom" id="breadcrumb">\n' + \
                 '\n'.join(f'                        {li}' for li in items) + \
                 '\n                     </ul>'
        m = _RE_BREADCRUMB.search(html)
        if m:
            html = html[:m.start()] + new_ul + html[m.end():]

    return html


# ══════════════════════════════════════════════════════════════════════════════
# Sitemap (Phase 3 – DB-driven, cached)
# ══════════════════════════════════════════════════════════════════════════════
_sitemap_cache = {'xml': None, 'ts': 0}
SITEMAP_TTL = 3600  # 1 hour

def build_sitemap() -> str:
    now = time.time()
    if _sitemap_cache['xml'] and now - _sitemap_cache['ts'] < SITEMAP_TTL:
        return _sitemap_cache['xml']

    urls = [PUBLIC_DOMAIN + '/']
    for cat in CATEGORY_LABELS:
        urls.append(f'{PUBLIC_DOMAIN}/{cat}')

    # TODO (Phase 3): add listing URLs from DB API
    # listings = _api_get('/properties?status=active&per_page=10000', 'sitemap_listings')
    # if listings: ...

    items = '\n'.join(
        f'  <url><loc>{u}</loc></url>' for u in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{items}\n'
        '</urlset>'
    )
    _sitemap_cache['xml'] = xml
    _sitemap_cache['ts']  = now
    return xml


# ══════════════════════════════════════════════════════════════════════════════
# HTTP handler
# ══════════════════════════════════════════════════════════════════════════════
class BazarHandler(http.server.SimpleHTTPRequestHandler):

    def _send_json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    # ── OPTIONS ───────────────────────────────────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    # ── POST ──────────────────────────────────────────────────────────────────
    def do_POST(self):
        if self.path == '/api/boost-checkout':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                data = {}

            return_url   = data.get('return_url', 'http://localhost:5000')
            listing_id   = data.get('listing_id', '')
            firebase_uid = data.get('firebase_uid', '')
            plan         = data.get('plan', 'free').lower()

            amount_pence = 80 if plan == 'pro' else 100
            price_label  = ('Boost to Top — PRO (£0.80)' if plan == 'pro'
                            else 'Boost to Top (£1.00)')

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
                            'unit_amount': amount_pence,
                            'product_data': {'name': price_label},
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata={
                        'firebase_uid': firebase_uid,
                        'listing_id':   listing_id,
                        'source':       'boost_to_top',
                    },
                )
                self._send_json(200, {'success': True, 'url': session.url})
            except Exception as e:
                self._send_json(500, {'success': False, 'error': str(e)})
            return

        self.send_response(404)
        self.end_headers()

    # ── GET ───────────────────────────────────────────────────────────────────
    def do_GET(self):
        host          = self.headers.get('Host', '')
        is_production = 'bazar.uk' in host
        parsed        = urllib.parse.urlparse(self.path)
        path          = parsed.path
        qs            = parsed.query

        # API: config
        if path == '/api/config':
            self._send_json(200, {'googleMapsApiKey': GOOGLE_MAPS_API_KEY})
            return

        # API: products (dev fallback)
        if path.startswith('/api/products/'):
            pid = path.split('/api/products/')[-1].split('?')[0]
            try:
                with open('products.json') as f:
                    products = json.load(f)
                product = products.get(pid)
                if product:
                    self._send_json(200, product)
                else:
                    self._send_json(404, {'error': 'not found'})
            except Exception:
                self._send_json(500, {'error': 'server error'})
            return

        # Sitemap
        if path == '/sitemap.xml':
            xml = build_sitemap().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/xml; charset=utf-8')
            self.end_headers()
            self.wfile.write(xml)
            return

        # 301 redirect: card.html?id=123 → /listing/123
        if path == '/card.html':
            qp = urllib.parse.parse_qs(qs)
            lid = qp.get('id', [None])[0]
            if lid and lid.isdigit():
                self.send_response(301)
                self.send_header('Location', f'/listing/{lid}')
                self.end_headers()
                return

        # /listing/{id} → serve card.html content with SEO
        m = re.match(r'^/listing/(\d+)$', path)
        if m:
            html_file = os.path.join(SITE_ROOT, 'card.html')
            if os.path.isfile(html_file):
                self._serve_seo_page(html_file, 'listing', {'id': m.group(1)})
                return

        # Dev homepage redirect
        if not is_production and path in ('/', '/index.html'):
            self.path = '/dev-index.html'
            return super().do_GET()

        # Determine page type for SEO injection
        page_type, params = resolve_page_type(path, qs)

        if page_type in ('homepage', 'listing', 'category', 'category_city',
                         'category_city_district', 'search', 'internal'):
            # Determine which HTML file to serve
            html_filename = {
                'homepage': 'index.html' if is_production else 'dev-index.html',
                'listing':  'card.html',
                'search':   'search.html',
            }.get(page_type)

            if html_filename is None:
                # Category pages don't have a dedicated HTML file yet –
                # serve search.html as a base (JS will load listings)
                html_filename = 'search.html'

            html_file = os.path.join(SITE_ROOT, html_filename)
            if os.path.isfile(html_file):
                self._serve_seo_page(html_file, page_type, params)
                return

        # Fallback: let SimpleHTTPRequestHandler serve the file normally
        super().do_GET()

    # ── SEO-aware file server ─────────────────────────────────────────────────
    def _serve_seo_page(self, html_file: str, page_type: str, params: dict):
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                html = f.read()
        except Exception:
            self.send_response(500)
            self.end_headers()
            return

        seo_data = fetch_seo_data(page_type, params)
        seo_head = build_seo_head(seo_data)
        html     = inject_seo(html, seo_head)

        # Inject visible H1 / breadcrumbs for listing pages (server-rendered body)
        ssr = seo_data.get('ssr')
        if ssr:
            html = inject_ssr_body(html, ssr)

        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def log_message(self, format, *args):
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════
class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

with ReusableTCPServer(('0.0.0.0', PORT), BazarHandler) as httpd:
    print(f'Bazar SEO server running on port {PORT}')
    httpd.serve_forever()
