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
LARAVEL_API_BASE   = 'https://admin.bazar.uk/api'
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


def _make_slug(title: str = '', district: str = '', city: str = '') -> str:
    """Generate a URL-safe slug: {title}-{district}-{city}, lowercase, hyphens.
    District and city are only appended if they are not already present in the title.
    """
    def _norm(s: str) -> str:
        s = (s or '').lower()
        s = re.sub(r'[^a-z0-9\s]', ' ', s)
        return re.sub(r'\s+', ' ', s).strip()

    t = _norm(title)
    d = _norm(district)
    c = _norm(city)

    parts = [t] if t else []
    if d and d not in t:
        parts.append(d)
    if c and c not in t and c not in d:
        parts.append(c)

    text = ' '.join(parts)
    text = re.sub(r'\s+', '-', text.strip())
    text = re.sub(r'-+', '-', text)
    return text[:80].rstrip('-')


def resolve_page_type(path: str, qs: str = '') -> tuple:
    """
    Returns (page_type, params_dict).
    page_type: homepage | listing | category | category_city |
               category_city_district | search | internal | other
    """
    p = path.lstrip('/')

    if p in ('', 'index.html'):
        return 'homepage', {}

    # card.html?id=123  (legacy URL – redirected in do_GET)
    if p == 'card.html':
        qp = urllib.parse.parse_qs(qs)
        lid = qp.get('id', [None])[0]
        if lid:
            return 'listing', {'id': lid}
        return 'other', {}

    # /listing/{id} or /listing/{id}-{slug}  (legacy – redirected in do_GET)
    m = re.match(r'^listing/(\d+)', p)
    if m:
        return 'listing', {'id': m.group(1)}

    # /{id}-{slug} or /{id}  — new canonical listing URL (ID-first)
    m = re.match(r'^(\d+)(-[a-z0-9-]+)?$', p)
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
        # /property/for-rent/short-term  →  property_transaction_modifier
        if parts[0] == 'property' and parts[1] in ('for-rent', 'for-sale') and parts[2] == 'short-term':
            return 'property_transaction_modifier', {
                'transaction': parts[1], 'modifier': 'short-term'
            }
        # /property/for-rent/{city} or /property/for-sale/{city}  →  property_transaction_city
        if parts[0] == 'property' and parts[1] in ('for-rent', 'for-sale'):
            return 'property_transaction_city', {
                'transaction': parts[1], 'city': parts[2]
            }
        # /rooms/london/short-term  →  category_city_modifier
        if parts[2] == 'short-term':
            return 'category_city_modifier', {
                'category': parts[0], 'city': parts[1], 'modifier': 'short-term'
            }
        return 'category_city_district', {
            'category': parts[0], 'city': parts[1], 'district': parts[2]
        }
    if len(parts) == 2:
        # /property/for-rent or /property/for-sale  →  property_transaction
        if parts[0] == 'property' and parts[1] in ('for-rent', 'for-sale'):
            return 'property_transaction', {'transaction': parts[1]}
        # /rooms/short-term  →  category_modifier
        if parts[1] == 'short-term':
            return 'category_modifier', {
                'category': parts[0], 'modifier': 'short-term'
            }
        return 'category_city', {'category': parts[0], 'city': parts[1]}
    if len(parts) == 1:
        return 'category', {'category': parts[0]}

    return 'other', {}


# ══════════════════════════════════════════════════════════════════════════════
# Layer 2 – SEO data fetcher
# ══════════════════════════════════════════════════════════════════════════════
CATEGORY_LABELS = {
    'property':    'Property',    'real-estate': 'Property',
    'cars':        'Cars',        'motors':      'Motors',
    'vehicles':    'Vehicles',    'rooms':       'Rooms',
    'flats':       'Flats',
    'jobs':        'Jobs',        'electronics': 'Electronics',
    'furniture':   'Furniture',   'fashion':     'Fashion',
    'services':    'Services',    'pets':        'Pets',
    'sports':      'Sports',      'kids':        'Kids',
    'garden':      'Garden',      'tools':       'Tools',
}

# Verb phrase used in title/H1: "Cars for sale" / "Rooms to rent" / "Jobs"
CATEGORY_ACTION = {
    'property':  'for sale',   'real-estate': 'for sale',
    'cars':      'for sale',   'motors':      'for sale',
    'vehicles':  'for sale',   'rooms':       'to rent',
    'flats':     'for Rent',
    'jobs':      '',           'electronics': 'for sale',
    'furniture': 'for sale',   'fashion':     'for sale',
    'services':  '',           'pets':        'for sale',
    'sports':    'for sale',   'kids':        'for sale',
    'garden':    'for sale',   'tools':       'for sale',
}

# Base intro sentence per category (UK-level)
CATEGORY_INTROS = {
    'property':    'Browse property listings across the UK — flats, houses, villas and more.',
    'real-estate': 'Browse property listings across the UK — flats, houses, villas and more.',
    'cars':        'Browse new and used car listings across the UK from private sellers and dealers.',
    'motors':      'Browse motors and vehicles for sale across the UK on Bazar.',
    'vehicles':    'Browse vehicles for sale across the UK — cars, vans, bikes and more.',
    'rooms':       'Find rooms to rent across the UK. Short-term and long-term rentals available.',
    'flats':       'Find flats to rent across the UK. Short-term and long-term rentals available.',
    'jobs':        'Browse job listings across the UK. Find local opportunities on Bazar.',
    'electronics': 'Buy and sell electronics across the UK — phones, laptops, TVs and more.',
    'furniture':   'Browse furniture listings across the UK. New and second-hand pieces from local sellers.',
    'fashion':     'Buy and sell fashion across the UK — clothing, shoes, accessories and more.',
    'services':    'Find local services across the UK. Tradespeople, cleaners, tutors and more.',
    'pets':        'Find pets for sale and adoption across the UK on Bazar.',
    'sports':      'Buy and sell sports equipment across the UK on Bazar.',
    'kids':        'Buy and sell kids items across the UK — toys, clothes, prams and more.',
    'garden':      'Browse garden items for sale across the UK on Bazar.',
    'tools':       'Buy and sell tools across the UK. Power tools, hand tools and more.',
}

CURRENCY_SYMBOL = {'GBP': '£', 'USD': '$', 'EUR': '€'}

def _api_get(path: str, cache_key: str = None):
    """HTTP GET to the Laravel API with caching."""
    if cache_key:
        cached = _cache_get(cache_key)
        if cached:
            return cached

    for url, headers in [
        (f'{LARAVEL_API_BASE}{path}', {}),
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
        'title':       'Free UK Classifieds – Buy & Sell | Bazar UK',
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
            seo['canonical'] = f'{PUBLIC_DOMAIN}/{lid}'
            seo['robots'] = 'noindex, follow'
            return seo

        # ── Status check: only active listings are indexable ──────────────────
        status = listing.get('status', 'active')

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
        # With district:    "{title} – £{price} in {district}, {city} | Bazar UK"
        # Without district: "{title} – £{price} in {city} | Bazar UK"
        # District is MANDATORY when present (critical for SEO long-tail)
        if district and city:
            location_str = f'{district}, {city}'
        elif city:
            location_str = city
        else:
            location_str = 'UK'

        raw_title = title + f' in {location_str}'
        if price_str:
            raw_title += f' – {price_str}'
        raw_title += ' | Bazar UK'
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

        slug = _make_slug(title, district, city)
        canonical = f'{PUBLIC_DOMAIN}/{lid}-{slug}' if slug else f'{PUBLIC_DOMAIN}/{lid}'

        if status != 'active':
            seo['canonical'] = canonical
            seo['robots'] = 'noindex, follow'

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

        city_slug_url = re.sub(r'[^a-z0-9]+', '-', city.lower()).strip('-') if city else ''
        city_url = f'{PUBLIC_DOMAIN}/property/{city_slug_url}' if city_slug_url else ''

        bc_items = [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": PUBLIC_DOMAIN},
            {"@type": "ListItem", "position": 2, "name": cat_label, "item": f"{PUBLIC_DOMAIN}/property"},
        ]
        if city_url:
            bc_items.append({"@type": "ListItem", "position": 3, "name": city, "item": city_url})
        bc_items.append({"@type": "ListItem", "position": len(bc_items) + 1, "name": title, "item": canonical})

        breadcrumb_schema = {"@type": "BreadcrumbList", "itemListElement": bc_items}

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
        listing_breadcrumbs = [
            ('Home', '/'),
            (cat_label, '/property'),
        ]
        if city and city_slug_url:
            listing_breadcrumbs.append((city, f'/property/{city_slug_url}'))
        listing_breadcrumbs.append((type_label, None))

        seo['ssr'] = {
            'prop_title':  title,
            'breadcrumbs': listing_breadcrumbs,
        }

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
        action    = CATEGORY_ACTION.get(cat, 'for sale')
        intro     = CATEGORY_INTROS.get(cat,
                        f'Browse {cat_label.lower()} listings across the UK on Bazar.')
        canonical = f'{PUBLIC_DOMAIN}/{cat}'

        # H1: "Cars for sale in the UK" / "Jobs in the UK" / "Rooms to Rent in the UK"
        h1_phrase = f'{cat_label} {action}'.strip()
        h1 = f'{h1_phrase} in the UK'

        # Title (max ~65 chars)
        raw_title = f'{h1} | Bazar UK'
        seo_title = raw_title[:65] + '…' if len(raw_title) > 68 else raw_title

        desc = f'{intro} Find great deals on Bazar UK classifieds.'
        if len(desc) > 160:
            desc = desc[:157] + '…'

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": h1_phrase, "item": canonical},
            ]
        }
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "name": seo_title,
                    "description": desc,
                    "url": canonical,
                    "breadcrumb": breadcrumb_schema,
                },
                breadcrumb_schema,
            ]
        }

        seo.update({
            'title':       seo_title,
            'description': desc,
            'canonical':   canonical,
            'json_ld':     json.dumps(schema),
        })

        inventory = _api_get('/sitemap-inventory?min=1', 'sitemap_inventory')
        city_slugs = (inventory or {}).get(cat, [])
        city_links = [
            (slug.replace('-', ' ').title(), f'/{cat}/{slug}')
            for slug in city_slugs[:12] if slug
        ]

        related_links = []
        if cat == 'flats':
            related_links = [('Looking for short-term rentals?', 'View short-term flats', '/flats/short-term')]

        seo['ssr'] = {
            'h1':            h1,
            'intro':         intro,
            'breadcrumbs':   [
                ('Home', '/'),
                (cat_label, None),
            ],
            'city_links':    city_links,
            'cat_label':     h1_phrase,
            'related_links': related_links,
            'type':          'category',
        }
        return seo

    # ── Category + modifier (e.g. /rooms/short-term) ──────────────────────────
    elif page_type == 'category_modifier':
        cat       = params.get('category', '')
        modifier  = params.get('modifier', '')
        cat_label = CATEGORY_LABELS.get(cat, cat.replace('-', ' ').title())
        canonical = f'{PUBLIC_DOMAIN}/{cat}/short-term'

        h1    = f'Short-Term {cat_label} for Rent in the UK' if cat == 'flats' else f'Short-Term {cat_label} to Rent in the UK'
        if cat == 'rooms':
            intro = ('Find short-term rooms to rent across the UK. '
                     'Perfect for temporary stays, students, and flexible living.')
        elif cat == 'flats':
            intro = ('Find short-term flats to rent across the UK. '
                     'Perfect for temporary stays, relocations, and flexible living.')
        else:
            intro = (f'Find short-term {cat_label.lower()} to rent across the UK. '
                     f'Ideal for temporary stays and flexible rentals.')
        desc  = intro[:160]

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": cat_label, "item": f'{PUBLIC_DOMAIN}/{cat}'},
                {"@type": "ListItem", "position": 3,
                 "name": "Short-Term", "item": canonical},
            ]
        }
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "name": h1,
                    "description": desc,
                    "url": canonical,
                    "breadcrumb": breadcrumb_schema,
                },
                breadcrumb_schema,
            ]
        }
        seo.update({
            'title':       f'{h1} | Bazar UK',
            'description': desc,
            'canonical':   canonical,
            'json_ld':     json.dumps(schema),
        })
        related_links = []
        if cat == 'flats':
            related_links = [('Looking for long-term rentals?', 'View long-term flats', '/flats')]

        seo['ssr'] = {
            'h1':            h1,
            'intro':         intro,
            'breadcrumbs':   [
                ('Home', '/'),
                (cat_label, f'/{cat}'),
                ('Short-Term', None),
            ],
            'related_links': related_links,
            'type':          'category',
        }
        return seo

    # ── /property/for-rent or /property/for-sale ──────────────────────────────
    elif page_type == 'property_transaction':
        transaction = params.get('transaction', 'for-rent')
        is_rent     = (transaction == 'for-rent')
        verb        = 'for Rent' if is_rent else 'for Sale'
        canonical   = f'{PUBLIC_DOMAIN}/property/{transaction}'

        h1    = f'Real Estate {verb} in the UK'
        intro = (
            f'Browse thousands of properties {verb.lower()} across the UK. '
            f'Flats, houses, rooms, commercial properties and more.'
        )
        desc  = intro[:160]

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": f'Real Estate {verb}', "item": canonical},
            ]
        }
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "name": h1,
                    "description": desc,
                    "url": canonical,
                    "breadcrumb": breadcrumb_schema,
                },
                breadcrumb_schema,
            ]
        }
        seo.update({
            'title':       f'{h1} | Bazar UK',
            'description': desc,
            'canonical':   canonical,
            'json_ld':     json.dumps(schema),
        })
        related_links = []
        if is_rent:
            related_links = [('Looking for short-term rentals?', 'View short-term properties', '/property/for-rent/short-term')]

        seo['ssr'] = {
            'h1':            h1,
            'intro':         intro,
            'breadcrumbs':   [
                ('Home', '/'),
                (f'Real Estate {verb}', None),
            ],
            'related_links': related_links,
            'type':          'category',
        }
        return seo

    # ── /property/for-rent/short-term ─────────────────────────────────────────
    elif page_type == 'property_transaction_modifier':
        transaction = params.get('transaction', 'for-rent')
        canonical   = f'{PUBLIC_DOMAIN}/property/{transaction}/short-term'
        parent_url  = f'{PUBLIC_DOMAIN}/property/{transaction}'

        h1    = 'Short-Term Real Estate for Rent in the UK'
        intro = (
            'Find short-term properties for rent across the UK. '
            'Ideal for temporary stays, corporate lets, and flexible rentals.'
        )
        desc  = intro[:160]

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": "Real Estate for Rent", "item": parent_url},
                {"@type": "ListItem", "position": 3,
                 "name": "Short-Term", "item": canonical},
            ]
        }
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "name": h1,
                    "description": desc,
                    "url": canonical,
                    "breadcrumb": breadcrumb_schema,
                },
                breadcrumb_schema,
            ]
        }
        seo.update({
            'title':       f'{h1} | Bazar UK',
            'description': desc,
            'canonical':   canonical,
            'json_ld':     json.dumps(schema),
        })
        seo['ssr'] = {
            'h1':            h1,
            'intro':         intro,
            'breadcrumbs':   [
                ('Home', '/'),
                ('Real Estate for Rent', f'/property/for-rent'),
                ('Short-Term', None),
            ],
            'related_links': [('Looking for long-term rentals?', 'View all properties for rent', '/property/for-rent')],
            'type':          'category',
        }
        return seo

    # ── /property/for-rent/{city} or /property/for-sale/{city} ───────────────
    elif page_type == 'property_transaction_city':
        transaction = params.get('transaction', 'for-rent')
        city_slug   = params.get('city', '')
        city        = city_slug.replace('-', ' ').title()
        is_rent     = (transaction == 'for-rent')
        verb        = 'for Rent' if is_rent else 'for Sale'
        parent_url  = f'{PUBLIC_DOMAIN}/property/{transaction}'
        canonical   = f'{PUBLIC_DOMAIN}/property/{transaction}/{city_slug}'

        h1    = f'Real Estate {verb} in {city}'
        intro = (
            f'Browse properties {verb.lower()} in {city}. '
            f'Flats, houses, rooms and commercial properties in {city} on Bazar UK.'
        )
        desc  = intro[:160]

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": f'Real Estate {verb}', "item": parent_url},
                {"@type": "ListItem", "position": 3,
                 "name": city, "item": canonical},
            ]
        }
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "name": h1,
                    "description": desc,
                    "url": canonical,
                    "breadcrumb": breadcrumb_schema,
                },
                breadcrumb_schema,
            ]
        }
        seo.update({
            'title':       f'{h1} | Bazar UK',
            'description': desc,
            'canonical':   canonical,
            'json_ld':     json.dumps(schema),
        })
        seo['ssr'] = {
            'h1':          h1,
            'intro':       intro,
            'breadcrumbs': [
                ('Home', '/'),
                (f'Real Estate {verb}', f'/property/{transaction}'),
                (city, None),
            ],
            'type': 'category',
        }
        return seo

    # ── Category + city + modifier (e.g. /rooms/london/short-term) ────────────
    elif page_type == 'category_city_modifier':
        cat       = params.get('category', '')
        city_slug = params.get('city', '')
        city      = city_slug.replace('-', ' ').title()
        cat_label = CATEGORY_LABELS.get(cat, cat.replace('-', ' ').title())
        canonical = f'{PUBLIC_DOMAIN}/{cat}/{city_slug}/short-term'
        cat_url   = f'{PUBLIC_DOMAIN}/{cat}'

        verb  = 'for Rent' if cat == 'flats' else 'to Rent'
        h1    = f'Short-Term {cat_label} {verb} in {city}'
        intro = (f'Find short-term {cat_label.lower()} for rent in {city}. '
                 f'Ideal for temporary stays and flexible rentals.')
        desc  = intro[:160]

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": cat_label, "item": cat_url},
                {"@type": "ListItem", "position": 3,
                 "name": city, "item": f'{PUBLIC_DOMAIN}/{cat}/{city_slug}'},
                {"@type": "ListItem", "position": 4,
                 "name": "Short-Term", "item": canonical},
            ]
        }
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "name": h1,
                    "description": desc,
                    "url": canonical,
                    "breadcrumb": breadcrumb_schema,
                },
                breadcrumb_schema,
            ]
        }
        seo.update({
            'title':       f'{h1} | Bazar UK',
            'description': desc,
            'canonical':   canonical,
            'json_ld':     json.dumps(schema),
        })
        related_links = []
        if cat == 'flats':
            related_links = [('Looking for long-term rentals?', f'View long-term flats in {city}', f'/flats/{city_slug}')]

        seo['ssr'] = {
            'h1':            h1,
            'intro':         intro,
            'breadcrumbs':   [
                ('Home', '/'),
                (cat_label, f'/{cat}'),
                (city, f'/{cat}/{city_slug}'),
                ('Short-Term', None),
            ],
            'related_links': related_links,
            'type':          'category',
        }
        return seo

    # ── Category + city ───────────────────────────────────────────────────────
    elif page_type == 'category_city':
        cat       = params.get('category', '')
        city_slug = params.get('city', '')
        city      = city_slug.replace('-', ' ').title()
        cat_label = CATEGORY_LABELS.get(cat, cat.replace('-', ' ').title())
        action    = CATEGORY_ACTION.get(cat, 'for sale')
        canonical = f'{PUBLIC_DOMAIN}/{cat}/{city_slug}'
        cat_url   = f'{PUBLIC_DOMAIN}/{cat}'

        # H1 phrases
        h1_phrase_cat  = f'{cat_label} {action}'.strip()   # "Cars for sale"
        h1_phrase_city = f'{h1_phrase_cat} in {city}'      # "Cars for sale in London"
        h1 = h1_phrase_city

        raw_title = f'{h1_phrase_city} | Bazar UK'
        seo_title = raw_title[:65] + '…' if len(raw_title) > 68 else raw_title

        base_intro = CATEGORY_INTROS.get(cat,
                         f'Browse {cat_label.lower()} listings on Bazar.')
        city_intro = (f'Browse {cat_label.lower()} {action} in {city}. '
                      f'Find local deals from sellers in {city} on Bazar UK.')

        desc = city_intro
        if len(desc) > 160:
            desc = desc[:157] + '…'

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": h1_phrase_cat, "item": cat_url},
                {"@type": "ListItem", "position": 3,
                 "name": city, "item": canonical},
            ]
        }
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "name": seo_title,
                    "description": desc,
                    "url": canonical,
                    "breadcrumb": breadcrumb_schema,
                },
                breadcrumb_schema,
            ]
        }

        seo.update({
            'title':       seo_title,
            'description': desc,
            'canonical':   canonical,
            'json_ld':     json.dumps(schema),
        })
        related_links = []
        if cat == 'flats':
            related_links = [('Looking for short-term rentals?', f'View short-term flats in {city}', f'/flats/{city_slug}/short-term')]

        seo['ssr'] = {
            'h1':            h1,
            'intro':         city_intro,
            'breadcrumbs':   [
                ('Home', '/'),
                (h1_phrase_cat, f'/{cat}'),
                (city, None),
            ],
            'related_links': related_links,
            'type':          'category',
        }
        return seo

    # ── Category + city + district (noindex, architecture supported) ──────────
    elif page_type == 'category_city_district':
        cat          = params.get('category', '')
        city_slug    = params.get('city', '')
        district_slug= params.get('district', '')
        city         = city_slug.replace('-', ' ').title()
        district     = district_slug.replace('-', ' ').title()
        cat_label    = CATEGORY_LABELS.get(cat, cat.replace('-', ' ').title())
        action       = CATEGORY_ACTION.get(cat, 'for sale')
        canonical    = f'{PUBLIC_DOMAIN}/{cat}/{city_slug}/{district_slug}'
        h1_phrase_cat= f'{cat_label} {action}'.strip()
        h1 = f'{h1_phrase_cat} in {district}, {city}'

        seo.update({
            'title':       f'{h1} | Bazar UK',
            'description': (f'Browse {cat_label.lower()} {action} in {district}, {city}. '
                            f'Find local listings on Bazar UK.'),
            'canonical':   canonical,
            'robots':      'noindex, follow',
        })
        seo['ssr'] = {
            'h1':          h1,
            'intro':       (f'Browse {cat_label.lower()} {action} in {district}, {city} '
                            f'on Bazar UK classifieds.'),
            'breadcrumbs': [
                ('Home', '/'),
                (h1_phrase_cat, f'/{cat}'),
                (city, f'/{cat}/{city_slug}'),
                (district, None),
            ],
            'type': 'category',
        }
        return seo

    # ── Search (noindex always) ───────────────────────────────────────────────
    elif page_type == 'search':
        seo.update({
            'title':   'Search | Bazar UK',
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
        f'<meta name="google-site-verification" content="Tw8NlNC_J7btA3jopUVmkaAIfZrinCVS9mPlFH1UWWY">',
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
_RE_HEAD_OPEN      = re.compile(r'(<head[^>]*>)', re.I)
_RE_PROP_TITLE     = re.compile(r'<p([^>]*id="prop-title"[^>]*)>[^<]*</p>', re.I)
_RE_BREADCRUMB     = re.compile(r'(<ul[^>]+id="breadcrumb"[^>]*>).*?(</ul>)', re.I | re.S)
_RE_SR_BREADCRUMB  = re.compile(r'<ul[^>]+id="srBreadcrumb"[^>]*>.*?</ul>', re.I | re.S)
_RE_SR_RESULTS_DIV    = re.compile(r'(<div\s+class="sr-results">)', re.I)
_RE_SR_HERO_SLOT      = re.compile(r'<!--\s*SR_CAT_HERO\s*-->', re.I)

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
            # m.group(1) = attributes string e.g. ' class="card-head__title" id="prop-title"'
            html = html[:m.start()] + f'<h1{m.group(1)}>{_esc(prop_title)}</h1>' + html[m.end():]

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


def inject_ssr_category(html: str, ssr: dict) -> str:
    """Inject visible H1, intro text, breadcrumbs, city links and related links into search.html
    for category and category+city pages."""

    h1             = ssr.get('h1', '')
    intro          = ssr.get('intro', '')
    breadcrumbs    = ssr.get('breadcrumbs', [])
    city_links     = ssr.get('city_links', [])
    cat_label      = ssr.get('cat_label', '')
    related_links  = ssr.get('related_links', [])

    # ── Build replacement srBreadcrumb ────────────────────────────────────────
    if breadcrumbs:
        items = []
        for i, (label, href) in enumerate(breadcrumbs):
            is_last = (i == len(breadcrumbs) - 1)
            safe_label = _esc(label)
            if not is_last:
                items.append(
                    f'<li><a href="{_attr(href)}">{safe_label}</a>'
                    f'<span class="icon-arrow-r"></span></li>'
                )
            else:
                items.append(f'<li>{safe_label}</li>')
        new_ul = ('<ul class="bread-custom" id="srBreadcrumb">' +
                  ''.join(items) + '</ul>')
        m = _RE_SR_BREADCRUMB.search(html)
        if m:
            html = html[:m.start()] + new_ul + html[m.end():]

    # ── Inject H1 + intro paragraph after breadcrumbs (SR_CAT_HERO slot) ───────
    if h1:
        hero_html = (
            f'\n               <div class="sr-cat-hero" id="srCatHero">'
            f'<h1 class="sr-cat-h1" id="srCatH1">{_esc(h1)}</h1>'
        )
        if intro:
            hero_html += f'<p class="sr-cat-intro" id="srCatIntro">{_esc(intro)}</p>'
        if related_links:
            for (text, link_text, href) in related_links:
                hero_html += (
                    f'<p class="sr-cat-related" id="srCatRelated">'
                    f'{_esc(text)} '
                    f'<a href="{_attr(href)}">{_esc(link_text)} →</a>'
                    f'</p>'
                )
        hero_html += '</div>'

        m = _RE_SR_HERO_SLOT.search(html)
        if m:
            html = html[:m.start()] + hero_html + html[m.end():]

    # ── Inject city links nav before </body> ─────────────────────────────────
    if city_links:
        links_html = ''.join(
            f'<a href="{_attr(href)}" style="color:#888;display:block;padding:2px 0">'
            f'{_esc(f"{cat_label} in {label}" if cat_label else label)}</a>'
            for label, href in city_links
        )
        nav = (
            f'\n<nav aria-label="Browse by city" style="font-size:13px;padding:10px 16px 20px;">'
            f'<span style="color:#aaa;display:block;margin-bottom:4px">Popular cities:</span>'
            f'{links_html}</nav>'
        )
        html = html.replace('</body>', nav + '\n</body>', 1)

    return html


# ══════════════════════════════════════════════════════════════════════════════
# Sitemap (Phase 3 – DB-driven, cached)
# ══════════════════════════════════════════════════════════════════════════════
_sitemap_cache = {'xml': None, 'ts': 0}
SITEMAP_TTL = 3600  # 1 hour

# Only the canonical category slugs (no aliases like 'real-estate', 'motors')
CANONICAL_CATEGORIES = [
    'property', 'cars', 'vehicles', 'rooms', 'flats', 'jobs',
    'electronics', 'furniture', 'fashion', 'services',
    'pets', 'sports', 'kids', 'garden', 'tools',
]

# Minimum active listing count for a city page to appear in sitemap.
# Prevents thin/empty pages from being submitted to Google.
SITEMAP_CITY_MIN_COUNT = 3

def build_sitemap() -> str:
    now = time.time()
    if _sitemap_cache['xml'] and now - _sitemap_cache['ts'] < SITEMAP_TTL:
        return _sitemap_cache['xml']

    # Each entry: (loc_url, lastmod_str_or_None)
    entries = [(PUBLIC_DOMAIN + '/', None)]

    # /{category} — all canonical categories (always included)
    for cat in CANONICAL_CATEGORIES:
        entries.append((f'{PUBLIC_DOMAIN}/{cat}', None))

    # /{category}/{city} — only cities with real inventory.
    # Fetches from the Laravel API: returns city slugs per category
    # grouped by actual active listing count >= SITEMAP_CITY_MIN_COUNT.
    inventory = _api_get(
        f'/sitemap-inventory?min={SITEMAP_CITY_MIN_COUNT}',
        'sitemap_inventory'
    )
    if inventory:
        for cat, cities in inventory.items():
            if cat in CANONICAL_CATEGORIES and isinstance(cities, list):
                for city_slug in cities:
                    if city_slug:
                        entries.append((f'{PUBLIC_DOMAIN}/{cat}/{city_slug}', None))

    # Individual listing URLs — only active listings, with lastmod.
    # noindex listings are already excluded because endpoint filters status=active.
    listings = _api_get('/sitemap-listings', 'sitemap_listings')
    if listings and isinstance(listings, list):
        for item in listings:
            lid = item.get('id')
            updated = item.get('updated_at', '')
            lastmod = updated if updated else None  # ISO 8601: YYYY-MM-DDTHH:MM:SS+00:00
            if lid:
                slug = _make_slug(
                    item.get('title', ''),
                    item.get('district', ''),
                    item.get('city', ''),
                )
                url = f'{PUBLIC_DOMAIN}/{lid}-{slug}' if slug else f'{PUBLIC_DOMAIN}/{lid}'
                entries.append((url, lastmod))

    def _url_tag(loc, lastmod):
        if lastmod:
            return f'  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>'
        return f'  <url><loc>{loc}</loc></url>'

    items = '\n'.join(_url_tag(loc, lm) for loc, lm in entries)
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

        # 301 redirect: card.html?id=123 → /{id}-{slug}
        if path == '/card.html':
            qp = urllib.parse.parse_qs(qs)
            lid = qp.get('id', [None])[0]
            if lid and lid.isdigit():
                listing = _api_get(f'/properties/{lid}', f'listing_{lid}')
                if listing:
                    slug = _make_slug(
                        listing.get('title', ''),
                        listing.get('district', ''),
                        listing.get('city', ''),
                    )
                    dest = f'/{lid}-{slug}' if slug else f'/{lid}'
                else:
                    dest = f'/{lid}'
                self.send_response(301)
                self.send_header('Location', dest)
                self.end_headers()
                return

        # 301 redirect: /listing/{id} or /listing/{id}-{slug} → /{id}-{slug}
        m = re.match(r'^/listing/(\d+)', path)
        if m:
            lid = m.group(1)
            listing = _api_get(f'/properties/{lid}', f'listing_{lid}')
            if listing:
                slug = _make_slug(
                    listing.get('title', ''),
                    listing.get('district', ''),
                    listing.get('city', ''),
                )
                dest = f'/{lid}-{slug}' if slug else f'/{lid}'
            else:
                dest = f'/{lid}'
            self.send_response(301)
            self.send_header('Location', dest)
            self.end_headers()
            return

        # /{id}-{slug} → serve card.html with SEO
        # /{id}        → 301 redirect to /{id}-{slug}
        m = re.match(r'^/(\d+)(-.+)?$', path)
        if m:
            lid = m.group(1)
            has_slug = bool(m.group(2))
            if not has_slug:
                listing = _api_get(f'/properties/{lid}', f'listing_{lid}')
                if listing:
                    slug = _make_slug(
                        listing.get('title', ''),
                        listing.get('district', ''),
                        listing.get('city', ''),
                    )
                    dest = f'/{lid}-{slug}' if slug else f'/{lid}'
                    if dest != path:
                        self.send_response(301)
                        self.send_header('Location', dest)
                        self.end_headers()
                        return
            html_file = os.path.join(SITE_ROOT, 'card.html')
            if os.path.isfile(html_file):
                self._serve_seo_page(html_file, 'listing', {'id': lid})
                return

        # Dev homepage redirect
        if not is_production and path in ('/', '/index.html'):
            self.path = '/dev-index.html'
            return super().do_GET()

        # Determine page type for SEO injection
        p_clean = path.lstrip('/')
        page_type, params = resolve_page_type(path, qs)

        if page_type in ('homepage', 'listing', 'category', 'category_modifier',
                         'category_city', 'category_city_modifier',
                         'category_city_district', 'search',
                         'property_transaction', 'property_transaction_modifier',
                         'property_transaction_city'):
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

        # internal pages (cabinet, post-ad, messages, policy pages, etc.):
        # serve the actual .html file directly — no SEO injection needed
        # since these are noindex pages served at their root-level URL.
        if page_type == 'internal':
            actual = os.path.join(SITE_ROOT, p_clean)
            if os.path.isfile(actual):
                super().do_GET()
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

        # All HTML files use relative asset paths (css/, img/, js/, post-ad.html…).
        # When Python serves them at deep URLs like /listing/11 or /property/london,
        # the browser would resolve relative paths against the wrong directory.
        # <base href="/"> fixes all paths globally without touching any HTML file.
        seo_head = '<base href="/">\n    ' + seo_head

        html     = inject_seo(html, seo_head)

        # Inject visible server-rendered body content (H1, breadcrumbs, intro)
        ssr = seo_data.get('ssr')
        if ssr:
            if ssr.get('type') == 'category':
                html = inject_ssr_category(html, ssr)
            else:
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
