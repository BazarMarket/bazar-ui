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
import sqlite3
import base64
import email
import email.parser
import io
import uuid

# ── Configuration ─────────────────────────────────────────────────────────────
PORT               = int(os.environ.get('BAZAR_PORT', 5000))
PUBLIC_DOMAIN      = 'https://www.bazar.uk'
LARAVEL_API_BASE   = os.environ.get('LARAVEL_API_BASE', 'https://admin.bazar.uk/api')
LARAVEL_API_HOST   = LARAVEL_API_BASE.split('/')[2] if '/' in LARAVEL_API_BASE else 'admin.bazar.uk'
SITE_ROOT          = os.environ.get('BAZAR_SITE_ROOT', os.path.dirname(os.path.abspath(__file__)))
SEO_CACHE_TTL      = 300  # seconds (5 min)
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')
STRIPE_SECRET_KEY   = os.environ.get('STRIPE_SECRET_KEY', '')
GEMINI_API_KEY      = (os.environ.get('GEMINI_API_KEY', '') or
                       os.environ.get('GOOGLE_API_KEY', ''))
GOOGLE_API_KEY      = os.environ.get('GOOGLE_API_KEY', '')

# ── Google Cloud Vision credentials (service account JSON) ────────────────────
_VISION_CREDS: dict = {}
_raw_vision_json = os.environ.get('GOOGLE_VISION_CREDENTIALS_JSON', '')
if _raw_vision_json:
    try:
        # Support both: JSON content directly OR a path to a JSON file
        if _raw_vision_json.strip().startswith('{'):
            _VISION_CREDS = json.loads(_raw_vision_json)
        else:
            _creds_path = _raw_vision_json.strip()
            if not os.path.isabs(_creds_path):
                _creds_path = os.path.join('/etc/bazar', _creds_path)
            with open(_creds_path) as _f:
                _VISION_CREDS = json.load(_f)
    except Exception as _e:
        print(f'[VISION] Failed to load credentials: {_e}', flush=True)

_vision_token_cache: dict = {'token': '', 'exp': 0}
_vision_token_lock  = threading.Lock()
CHAT_DB             = os.path.join(SITE_ROOT, 'bazar_chat.db')

# ── Chat DB init ──────────────────────────────────────────────────────────────
_chat_lock = threading.Lock()

def _chat_db():
    conn = sqlite3.connect(CHAT_DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _init_chat_db():
    with _chat_lock:
        conn = _chat_db()
        stmts = [
            '''CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                ad_id       TEXT DEFAULT '',
                ad_title    TEXT DEFAULT '',
                ad_url      TEXT DEFAULT '',
                ad_photo    TEXT DEFAULT '',
                ad_price    TEXT DEFAULT '',
                seller_name TEXT DEFAULT '',
                buyer_id    TEXT DEFAULT '',
                buyer_name  TEXT DEFAULT '',
                last_msg    TEXT DEFAULT '',
                last_time   REAL DEFAULT 0,
                unread_seller INTEGER DEFAULT 0,
                unread_buyer  INTEGER DEFAULT 0
            )''',
            '''CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                conv_id     TEXT NOT NULL,
                sender_id   TEXT DEFAULT '',
                sender_name TEXT DEFAULT '',
                text        TEXT DEFAULT '',
                time        REAL DEFAULT 0,
                type        TEXT DEFAULT 'text'
            )''',
            'CREATE INDEX IF NOT EXISTS idx_msgs_conv ON messages(conv_id, id)',
            'CREATE INDEX IF NOT EXISTS idx_convs_buyer ON conversations(buyer_id)',
            'CREATE INDEX IF NOT EXISTS idx_convs_seller ON conversations(seller_name)',
            '''CREATE TABLE IF NOT EXISTS property_comments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id TEXT NOT NULL,
                uid         TEXT DEFAULT '',
                username    TEXT DEFAULT 'Anonymous',
                text        TEXT NOT NULL,
                created_at  REAL DEFAULT 0
            )''',
            'CREATE INDEX IF NOT EXISTS idx_comments_prop ON property_comments(property_id, id)',
            '''CREATE TABLE IF NOT EXISTS listing_plans (
                ad_id         TEXT PRIMARY KEY,
                plan          TEXT DEFAULT 'free',
                activated_at  REAL DEFAULT 0,
                duration_days INTEGER DEFAULT 30,
                expires_at    REAL DEFAULT 0
            )''',
            '''CREATE TABLE IF NOT EXISTS customer_profiles (
                uid        TEXT PRIMARY KEY,
                gender     TEXT DEFAULT 'male',
                updated_at REAL DEFAULT 0
            )''',
        ]
        for s in stmts:
            try:
                conn.execute(s)
            except Exception:
                pass
        conn.commit()
        conn.close()

_init_chat_db()

# ── Moderation DB init ────────────────────────────────────────────────────────
MOD_DB = CHAT_DB  # reuse same SQLite file

def _init_mod_db():
    with _chat_lock:
        conn = sqlite3.connect(MOD_DB, check_same_thread=False)
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS moderation_reviews (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id      INTEGER DEFAULT 0,
                title            TEXT DEFAULT '',
                description      TEXT DEFAULT '',
                firebase_uid     TEXT DEFAULT '',
                ai_text_flagged  INTEGER DEFAULT 0,
                ai_reasons       TEXT DEFAULT '[]',
                ai_confidence    REAL DEFAULT 0.0,
                ai_image_flagged INTEGER DEFAULT 0,
                ai_image_reasons TEXT DEFAULT '[]',
                status           TEXT DEFAULT 'pending',
                reviewed_at      REAL DEFAULT 0,
                created_at       REAL DEFAULT 0
            );
        ''')
        # Migrate existing rows (ignore errors if columns already exist)
        for col_def in [
            'ai_image_flagged INTEGER DEFAULT 0',
            'ai_image_reasons TEXT DEFAULT "[]"',
        ]:
            try:
                conn.execute(f'ALTER TABLE moderation_reviews ADD COLUMN {col_def}')
            except Exception:
                pass
        conn.commit()
        conn.close()

_init_mod_db()

# ── Gemini AI for ticket auto-reply ───────────────────────────────────────────
_BAZAR_SYSTEM_PROMPT = """You are a helpful support assistant for Bazar (www.bazar.uk) — a UK online marketplace specialising in property listings (for sale, long-term rent, short-term rent) as well as other goods.

Your job is to answer customer support questions clearly and concisely. Here is key knowledge about Bazar:

POSTING ADS:
- Free ads can be posted in "My Ads" → "+ New Ad". Fill in category, title, description, price, photos.
- Ads are reviewed and go live within a few hours.

PROMOTIONS:
- VIP (red badge): puts your ad at top of search results and category pages. Paid monthly from wallet.
- TOP (orange badge): similar to VIP but slightly lower placement. Paid monthly from wallet.

PAYMENTS & WALLET:
- Top up balance in "My Payments" tab — choose preset amount or enter custom, select card, click "Top Up". Funds appear instantly.
- Withdraw in "My Payments" → Withdraw tab. Enter amount and bank details. Takes 1–3 business days.

SUBSCRIPTIONS:
- Monthly subscription plans available under "My Subscriptions".

ACCOUNT:
- Login issues: try "Log out from all devices" in My Settings.
- Email support: info@bazar.uk (response within 24–48 hours).

RULES:
- Be concise and professional. Use plain English.
- If you cannot answer confidently or the issue requires account-level access or human judgment, end your response with exactly the tag: [NEED_HUMAN]
- Do NOT include [NEED_HUMAN] if you can answer the question adequately.
- Never make up pricing or policies you are unsure about — say so and include [NEED_HUMAN] instead.
"""

def _gemini_reply(subject: str, message: str) -> tuple[str, bool]:
    """Call Gemini 2.5 Flash. Returns (reply_text, needs_human)."""
    if not GEMINI_API_KEY:
        return ('', True)
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}'
    payload = {
        'systemInstruction': {'parts': [{'text': _BAZAR_SYSTEM_PROMPT}]},
        'contents': [{'role': 'user', 'parts': [{'text': f'Subject: {subject}\n\n{message}'}]}],
        'generationConfig': {'temperature': 0.4, 'maxOutputTokens': 600},
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        text = result['candidates'][0]['content']['parts'][0]['text'].strip()
        needs_human = '[NEED_HUMAN]' in text
        clean_text = text.replace('[NEED_HUMAN]', '').strip()
        return (clean_text, needs_human)
    except Exception as exc:
        return ('', True)


def _gemini_reply_with_context(subject: str, messages: list) -> tuple[str, bool]:
    """Call Gemini 2.5 Flash with full conversation history. Returns (reply_text, needs_human).
    messages = list of dicts: [{sender_type, message}, ...]
    """
    if not GEMINI_API_KEY:
        return ('', True)
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}'
    contents = []
    for msg in messages:
        sender = msg.get('sender_type', 'client')
        text   = msg.get('message', '').strip()
        if not text:
            continue
        if sender == 'client':
            contents.append({'role': 'user',  'parts': [{'text': text}]})
        else:
            contents.append({'role': 'model', 'parts': [{'text': text}]})
    if not contents:
        contents = [{'role': 'user', 'parts': [{'text': f'Subject: {subject}'}]}]
    payload = {
        'systemInstruction': {'parts': [{'text': _BAZAR_SYSTEM_PROMPT}]},
        'contents': contents,
        'generationConfig': {'temperature': 0.4, 'maxOutputTokens': 600},
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
        text = result['candidates'][0]['content']['parts'][0]['text'].strip()
        needs_human = '[NEED_HUMAN]' in text
        clean_text  = text.replace('[NEED_HUMAN]', '').strip()
        return (clean_text, needs_human)
    except Exception:
        return ('', True)


def _fetch_ticket_with_messages(ticket_id: int) -> dict | None:
    """Fetch ticket + messages from Laravel. Returns dict or None."""
    try:
        req = urllib.request.Request(
            f'{LARAVEL_API_BASE}/tickets/{ticket_id}?with_messages=1',
            headers={'Accept': 'application/json'},
            method='GET',
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return None

# ── Gemini AI content moderation ──────────────────────────────────────────────
_COMMENT_MOD_PROMPT = """You are a content moderation AI for Bazar (www.bazar.uk), a UK property marketplace.
Analyse the following user comment and determine if it violates content policies.

Policy violations to detect:
1. Profanity or offensive language (swearing, insults, vulgar words)
2. Hate speech or discrimination
3. Sexual or explicit content
4. Spam or advertising
5. Threats or harassment

Comment: {comment}

Respond ONLY with valid JSON, no markdown, no explanation:
{{"flagged": true, "reasons": ["short reason"], "confidence": 0.9}}
If comment is acceptable: {{"flagged": false, "reasons": [], "confidence": 0.95}}"""

def _gemini_moderate_comment(comment: str) -> dict:
    """Run Gemini text moderation on a user comment."""
    if not GEMINI_API_KEY:
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}
    prompt = _COMMENT_MOD_PROMPT.format(comment=(comment or '')[:1000])
    url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
           f'gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}')
    payload = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.1,
            'maxOutputTokens': 200,
            'thinkingConfig': {'thinkingBudget': 0},
        },
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            result = json.loads(resp.read())
        raw = result['candidates'][0]['content']['parts'][0]['text'].strip()
        raw = raw.strip('`').strip()
        if raw.lower().startswith('json'):
            raw = raw[4:].strip()
        parsed = json.loads(raw)
        print(f'[COMMENT-MOD] flagged={parsed.get("flagged")} '
              f'reasons={parsed.get("reasons")} text={comment[:60]!r}', flush=True)
        return parsed
    except Exception as exc:
        print(f'[COMMENT-MOD] Gemini error: {exc}', flush=True)
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}

_MOD_PROMPT = """You are a content moderation AI for Bazar (www.bazar.uk), a UK property marketplace.
Analyse the following property listing and determine if it violates content policies.

Policy violations to detect:
1. Profanity or offensive language
2. Hate speech or discrimination
3. Sexual or explicit content
4. Spam, scam, or clearly fraudulent content
5. Content completely unrelated to property/real estate

Title: {title}
Description: {description}

Respond ONLY with valid JSON, no markdown, no explanation:
{{"flagged": true, "reasons": ["short reason"], "confidence": 0.9}}
If content is acceptable: {{"flagged": false, "reasons": [], "confidence": 0.95}}"""

_YT_MOD_PROMPT = """You are a content moderator for Bazar (www.bazar.uk), a UK marketplace for properties, cars, phones, and electronics.
A user wants to attach a YouTube video to their marketplace listing.

Video title: {title}
Channel/author: {author}

Decide if this video is suitable as a supporting media attachment for a product or property listing.

BLOCK if the video appears to be:
- Adult, sexual, or pornographic content
- A music track, song, or music video (including concert recordings, karaoke, lyric videos)
- A full-length movie, TV episode, or documentary
- Unrelated entertainment (movie trailers unrelated to a product being sold, TV show clips, vlogs)

ALLOW if the video appears to be:
- A product demo, unboxing, hands-on review, or test drive
- A game trailer, gameplay footage, or game review (for someone selling a game)
- A property walkthrough, virtual tour, or real estate presentation
- An instructional or how-to video directly related to a product
- Any video that clearly supports what someone is trying to sell or rent

Reply ONLY with valid JSON, no markdown, no explanation:
{{"ok": true, "reason": ""}}
or
{{"ok": false, "reason": "short English explanation for the user"}}"""

def _gemini_moderate_youtube(title: str, author: str) -> dict:
    """Check YouTube video title/author against content policy. Returns {ok, reason}."""
    if not GEMINI_API_KEY:
        return {'ok': True, 'reason': ''}
    prompt = _YT_MOD_PROMPT.format(
        title=(title or '')[:200],
        author=(author or '')[:100],
    )
    url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
           f'gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}')
    payload = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.1,
            'maxOutputTokens': 100,
            'thinkingConfig': {'thinkingBudget': 0},
        },
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
        raw = result['candidates'][0]['content']['parts'][0]['text'].strip()
        raw = raw.strip('`').strip()
        if raw.lower().startswith('json'):
            raw = raw[4:].strip()
        parsed = json.loads(raw)
        print(f'[YT-MOD] ok={parsed.get("ok")} reason={parsed.get("reason")!r} '
              f'title={title[:60]!r}', flush=True)
        return parsed
    except Exception as exc:
        print(f'[YT-MOD] Gemini error: {exc}', flush=True)
        return {'ok': True, 'reason': ''}

def _gemini_moderate(title: str, description: str) -> dict:
    """Run Gemini text moderation. Returns dict with flagged, reasons, confidence."""
    if not GEMINI_API_KEY:
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}
    prompt = _MOD_PROMPT.format(
        title=(title or '')[:500],
        description=(description or '')[:2000]
    )
    url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
           f'gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}')
    payload = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.1,
            'maxOutputTokens': 300,
            'thinkingConfig': {'thinkingBudget': 0},
        },
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        raw = result['candidates'][0]['content']['parts'][0]['text'].strip()
        raw = raw.strip('`').strip()
        if raw.lower().startswith('json'):
            raw = raw[4:].strip()
        parsed = json.loads(raw)
        print(f'[MODERATION] Gemini text check: flagged={parsed.get("flagged")} '
              f'confidence={parsed.get("confidence")} reasons={parsed.get("reasons")} '
              f'title={title[:60]!r}', flush=True)
        return parsed
    except Exception as exc:
        print(f'[MODERATION] Gemini error: {exc}', flush=True)
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}

# ── Google Cloud Vision SafeSearch ────────────────────────────────────────────
def _get_vision_token() -> str:
    """Return a valid OAuth2 Bearer token for the Vision API. Cached 58 min."""
    if not _VISION_CREDS:
        return ''
    with _vision_token_lock:
        now = int(time.time())
        if _vision_token_cache['token'] and now < _vision_token_cache['exp']:
            return _vision_token_cache['token']
        try:
            import jwt as _jwt  # pyjwt — available on Hetzner
            from cryptography.hazmat.primitives import serialization as _ser
            from cryptography.hazmat.backends import default_backend as _be
            private_key = _ser.load_pem_private_key(
                _VISION_CREDS['private_key'].encode(),
                password=None, backend=_be(),
            )
            claim = {
                'iss':   _VISION_CREDS['client_email'],
                'scope': 'https://www.googleapis.com/auth/cloud-vision',
                'aud':   'https://oauth2.googleapis.com/token',
                'iat':   now,
                'exp':   now + 3600,
            }
            signed = _jwt.encode(claim, private_key, algorithm='RS256')
            body = urllib.parse.urlencode({
                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'assertion':  signed,
            }).encode()
            req = urllib.request.Request(
                'https://oauth2.googleapis.com/token',
                data=body,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                token = json.loads(resp.read()).get('access_token', '')
            if token:
                _vision_token_cache['token'] = token
                _vision_token_cache['exp']   = now + 3500
            return token
        except Exception:
            return ''

_VISION_LEVELS = {
    'UNKNOWN': 0, 'VERY_UNLIKELY': 1, 'UNLIKELY': 2,
    'POSSIBLE': 3, 'LIKELY': 4, 'VERY_LIKELY': 5,
}

def _vision_safesearch(image_urls: list) -> dict:
    """Run SafeSearch detection on up to 3 image URLs.
    Returns {flagged, reasons, confidence}."""
    if not image_urls:
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}
    # Prefer service account; fall back to API key
    if _VISION_CREDS:
        token = _get_vision_token()
        auth_header = f'Bearer {token}' if token else ''
        api_key_param = ''
    elif GOOGLE_API_KEY:
        auth_header = ''
        api_key_param = f'?key={GOOGLE_API_KEY}'
    else:
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}
    if not auth_header and not api_key_param:
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}
    # Normalise URLs
    checked = []
    for u in image_urls[:3]:
        if u and not str(u).startswith('http'):
            u = f'https://www.bazar.uk/storage/{u}'
        if u:
            checked.append(str(u))
    if not checked:
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}
    requests_body = [
        {'image': {'source': {'imageUri': u}},
         'features': [{'type': 'SAFE_SEARCH_DETECTION'}]}
        for u in checked
    ]
    try:
        payload = json.dumps({'requests': requests_body}).encode()
        headers_v = {'Content-Type': 'application/json'}
        if auth_header:
            headers_v['Authorization'] = auth_header
        req = urllib.request.Request(
            f'https://vision.googleapis.com/v1/images:annotate{api_key_param}',
            data=payload,
            headers=headers_v,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception:
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}
    reasons: list = []
    max_conf = 0.0
    for i, response in enumerate(data.get('responses', [])):
        ss = response.get('safeSearchAnnotation', {})
        adult    = _VISION_LEVELS.get(ss.get('adult',    'UNKNOWN'), 0)
        violence = _VISION_LEVELS.get(ss.get('violence', 'UNKNOWN'), 0)
        racy     = _VISION_LEVELS.get(ss.get('racy',     'UNKNOWN'), 0)
        print(f'[VISION] Image {i+1}: adult={ss.get("adult")} violence={ss.get("violence")} racy={ss.get("racy")}', flush=True)
        if adult >= 3:      # POSSIBLE+
            reasons.append(f'adult content (image {i+1})')
            max_conf = max(max_conf, adult / 5.0)
        if violence >= 4:   # LIKELY+
            reasons.append(f'violent content (image {i+1})')
            max_conf = max(max_conf, violence / 5.0)
        if racy >= 3:       # POSSIBLE+
            reasons.append(f'explicit/racy content (image {i+1})')
            max_conf = max(max_conf, racy / 5.0)
    return {'flagged': len(reasons) > 0, 'reasons': reasons,
            'confidence': round(max_conf, 2)}


def _vision_safesearch_bytes(image_bytes_list: list) -> dict:
    """Run SafeSearch on raw image bytes (base64-encoded). Up to 3 images."""
    if not image_bytes_list:
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}
    if _VISION_CREDS:
        token = _get_vision_token()
        auth_header = f'Bearer {token}' if token else ''
        api_key_param = ''
    elif GOOGLE_API_KEY:
        auth_header = ''
        api_key_param = f'?key={GOOGLE_API_KEY}'
    else:
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}
    if not auth_header and not api_key_param:
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}
    requests_body = []
    for img_bytes in image_bytes_list[:3]:
        try:
            b64 = base64.b64encode(img_bytes).decode('utf-8')
            requests_body.append({
                'image': {'content': b64},
                'features': [{'type': 'SAFE_SEARCH_DETECTION'}],
            })
        except Exception:
            continue
    if not requests_body:
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}
    try:
        payload = json.dumps({'requests': requests_body}).encode()
        headers_v = {'Content-Type': 'application/json'}
        if auth_header:
            headers_v['Authorization'] = auth_header
        req = urllib.request.Request(
            f'https://vision.googleapis.com/v1/images:annotate{api_key_param}',
            data=payload,
            headers=headers_v,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except Exception:
        return {'flagged': False, 'reasons': [], 'confidence': 0.0}
    reasons: list = []
    max_conf = 0.0
    for i, response in enumerate(data.get('responses', [])):
        ss = response.get('safeSearchAnnotation', {})
        adult    = _VISION_LEVELS.get(ss.get('adult',    'UNKNOWN'), 0)
        violence = _VISION_LEVELS.get(ss.get('violence', 'UNKNOWN'), 0)
        racy     = _VISION_LEVELS.get(ss.get('racy',     'UNKNOWN'), 0)
        print(f'[VISION] Image {i+1}: adult={ss.get("adult")} violence={ss.get("violence")} racy={ss.get("racy")}', flush=True)
        if adult >= 3:      # POSSIBLE+
            reasons.append(f'adult content (image {i+1})')
            max_conf = max(max_conf, adult / 5.0)
        if violence >= 4:   # LIKELY+
            reasons.append(f'violent content (image {i+1})')
            max_conf = max(max_conf, violence / 5.0)
        if racy >= 3:       # POSSIBLE+
            reasons.append(f'racy content (image {i+1})')
            max_conf = max(max_conf, racy / 5.0)
    result = {'flagged': len(reasons) > 0, 'reasons': reasons,
              'confidence': round(max_conf, 2)}
    print(f'[MODERATION] Vision bytes check: flagged={result["flagged"]} '
          f'confidence={result["confidence"]} reasons={result["reasons"]} '
          f'images={len(image_bytes_list)}', flush=True)
    return result


def _parse_multipart(body_bytes: bytes, content_type: str):
    """Parse multipart/form-data manually (boundary-split).
    Returns (fields_dict, image_bytes_list).
    Robust against large binary payloads that confuse email.message_from_bytes."""
    try:
        boundary = None
        for seg in content_type.split(';'):
            seg = seg.strip()
            if seg.lower().startswith('boundary='):
                boundary = seg[9:].strip().strip('"')
                break
        if not boundary:
            return {}, []

        sep = ('--' + boundary).encode()
        fields: dict = {}
        images: list = []

        parts = body_bytes.split(sep)
        for part in parts[1:]:          # skip preamble before first boundary
            if part.startswith(b'--'):  # final boundary '--'
                break
            # Strip leading CRLF after boundary line
            if part.startswith(b'\r\n'):
                part = part[2:]
            # Split headers from body
            hdr_end = part.find(b'\r\n\r\n')
            if hdr_end == -1:
                continue
            hdr_raw  = part[:hdr_end].decode('utf-8', errors='replace')
            content  = part[hdr_end + 4:]
            # Strip trailing CRLF that separates body from next boundary
            if content.endswith(b'\r\n'):
                content = content[:-2]

            # Parse Content-Disposition
            name = filename = None
            for line in hdr_raw.split('\r\n'):
                if not line.lower().startswith('content-disposition'):
                    continue
                for token in line.split(';'):
                    token = token.strip()
                    if token.lower().startswith('name='):
                        name = token[5:].strip().strip('"')
                    elif token.lower().startswith('filename='):
                        filename = token[9:].strip().strip('"')

            if name is None:
                continue
            if filename:
                if content:
                    images.append(content)
            else:
                fields[name] = content.decode('utf-8', errors='replace')

        return fields, images
    except Exception as exc:
        print(f'[MODERATION] Multipart parse error: {exc}', flush=True)
        return {}, []


def _set_property_status_internal(prop_id: int, status: str) -> bool:
    """Call Laravel set-status endpoint from the moderation server (no user auth)."""
    try:
        url     = f'{LARAVEL_API_BASE}/properties/{prop_id}/set-status'
        payload = json.dumps({'status': status}).encode()
        req     = urllib.request.Request(
            url, data=payload,
            headers={
                'Content-Type':    'application/json',
                'Accept':          'application/json',
                'X-Bazar-Internal': 'moderation',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status == 200
    except Exception:
        return False

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
    'publish-options.html', 'real-estate.html', 'map-search.html',
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

    # card.html?id=123 or card?id=123  (legacy URL – redirected in do_GET)
    if p in ('card.html', 'card'):
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

    # latest-updates — dedicated route with H1 heading
    if p == 'latest-updates':
        return 'latest_updates', {}

    # search
    if p == 'search.html' or p.startswith('search'):
        return 'search', {}

    # internal / private pages (match both with and without .html extension)
    if p in INTERNAL_PAGES or (p + '.html') in INTERNAL_PAGES:
        return 'internal', {}

    # /cabinet/* deep links (e.g. /cabinet/profile, /cabinet/settings) → serve cabinet.html
    if p.startswith('cabinet/'):
        return 'internal_subroute', {'file': 'cabinet.html'}

    # static assets – let them pass through unchanged
    if '.' in p.split('/')[-1]:
        return 'other', {}

    parts = [x for x in p.split('/') if x]
    if len(parts) == 5:
        # /cars/for-rent/{make}/{city}/{district}
        if parts[0] == 'cars' and parts[1] == 'for-rent':
            return 'cars_make_city_district', {
                'make': parts[2], 'city': parts[3], 'district': parts[4], 'is_rent': True
            }
        # /cars/for-short-term-rent/{make}/{city}/{district}
        if parts[0] == 'cars' and parts[1] == 'for-short-term-rent':
            return 'cars_make_city_district', {
                'make': parts[2], 'city': parts[3], 'district': parts[4], 'is_short_rent': True
            }
    if len(parts) == 3:
        # /property/for-rent/short-term  →  property_transaction_modifier
        if parts[0] == 'property' and parts[1] in ('for-rent', 'for-sale') and parts[2] == 'short-term':
            return 'property_transaction_modifier', {
                'transaction': parts[1], 'modifier': 'short-term'
            }
        # /property/shop/for-sale  →  301 redirect to /property-for-sale/shop
        if parts[0] == 'property' and parts[1] in PROPERTY_SUBTYPES and parts[2] == 'for-sale':
            return 'redirect_301', {'location': f'/property-for-sale/{parts[1]}'}
        # /property/house/for-rent  →  301 redirect to /property-to-rent/house
        if parts[0] == 'property' and parts[1] in PROPERTY_SUBTYPES and parts[2] == 'for-rent':
            return 'redirect_301', {'location': f'/property-to-rent/{parts[1]}'}
        # /property/shop/short-term  →  301 redirect to /property-short-rent/shop
        if parts[0] == 'property' and parts[1] in PROPERTY_SUBTYPES and parts[2] == 'short-term':
            return 'redirect_301', {'location': f'/property-short-rent/{parts[1]}'}
        # /property/for-rent/{city} or /property/for-sale/{city}  →  301 to clean URL
        if parts[0] == 'property' and parts[1] in ('for-rent', 'for-sale'):
            _pfx = 'property-to-rent' if parts[1] == 'for-rent' else 'property-for-sale'
            return 'redirect_301', {'location': f'/{_pfx}/{parts[2]}'}
        # /rooms/london/short-term  →  category_city_modifier
        if parts[2] == 'short-term':
            return 'category_city_modifier', {
                'category': parts[0], 'city': parts[1], 'modifier': 'short-term'
            }
        # /motors-for-sale/{make}/{city}
        if parts[0] == 'motors-for-sale':
            return 'cars_make_city', {'make': parts[1], 'city': parts[2]}
        # Legacy /cars/{make}/{city} → 301
        if parts[0] == 'cars' and parts[1] not in ('for-rent', 'for-short-term-rent'):
            return 'redirect_301', {'location': f'/motors-for-sale/{parts[1]}/{parts[2]}'}
        # /cars/for-rent/{make}
        if parts[0] == 'cars' and parts[1] == 'for-rent':
            return 'cars_make', {'make': parts[2], 'is_rent': True}
        # /cars/for-short-term-rent/{make}
        if parts[0] == 'cars' and parts[1] == 'for-short-term-rent':
            return 'cars_make', {'make': parts[2], 'is_short_rent': True}
        # /property-for-sale/{subtype}/{city} or /property-to-rent/{subtype}/{city}
        if parts[0] in ('property-for-sale', 'property-to-rent', 'property-short-rent'):
            return 'property_subtype_city', {
                'transaction': parts[0], 'subtype': parts[1], 'city': parts[2]
            }
        return 'category_city_district', {
            'category': parts[0], 'city': parts[1], 'district': parts[2]
        }
    if len(parts) == 4:
        # /motors-for-sale/{make}/{city}/{district}
        if parts[0] == 'motors-for-sale':
            return 'cars_make_city_district', {
                'make': parts[1], 'city': parts[2], 'district': parts[3]
            }
        # Legacy /cars/{make}/{city}/{district} → 301
        if parts[0] == 'cars' and parts[1] not in ('for-rent', 'for-short-term-rent'):
            return 'redirect_301', {'location': f'/motors-for-sale/{parts[1]}/{parts[2]}/{parts[3]}'}
        # /cars/for-rent/{make}/{city}
        if parts[0] == 'cars' and parts[1] == 'for-rent':
            return 'cars_make_city_district', {
                'make': parts[2], 'city': parts[3], 'district': '', 'is_rent': True
            }
        # /cars/for-short-term-rent/{make}/{city}
        if parts[0] == 'cars' and parts[1] == 'for-short-term-rent':
            return 'cars_make_city_district', {
                'make': parts[2], 'city': parts[3], 'district': '', 'is_short_rent': True
            }
        # /property-for-sale/{subtype}/{city}/{district}
        if parts[0] in ('property-for-sale', 'property-to-rent', 'property-short-rent'):
            return 'property_subtype_city_district', {
                'transaction': parts[0], 'subtype': parts[1], 'city': parts[2], 'district': parts[3]
            }
    if len(parts) == 2:
        # /property/for-rent or /property/for-sale  →  property_transaction
        if parts[0] == 'property' and parts[1] in ('for-rent', 'for-sale'):
            return 'property_transaction', {'transaction': parts[1]}
        # /property/shop, /property/office, etc.  →  property_subtype
        if parts[0] == 'property' and parts[1] in PROPERTY_SUBTYPES:
            return 'property_subtype', {'subtype': parts[1]}
        # /property-for-sale/house, /property-for-sale/shop etc.  →  property_subtype_sale
        if parts[0] == 'property-for-sale' and parts[1] in PROPERTY_SUBTYPES:
            return 'property_subtype_sale', {'subtype': parts[1]}
        # /property-for-sale/land, /property-for-sale/building, /property-for-sale/business-or-investment
        if parts[0] == 'property-for-sale' and parts[1] in {'land', 'building', 'business-or-investment'}:
            return 'property_sale_type', {'sale_type': parts[1]}
        # /property-for-sale/flats  →  category_transaction (new SEO URL)
        if parts[0] == 'property-for-sale' and parts[1] in CATEGORY_LABELS:
            return 'category_transaction', {'category': parts[1], 'transaction': 'for-sale'}
        # /property-to-rent/house, /property-to-rent/shop etc.  →  property_subtype_rent
        if parts[0] == 'property-to-rent' and parts[1] in PROPERTY_SUBTYPES:
            return 'property_subtype_rent', {'subtype': parts[1]}
        # /property-to-rent/flats, /property-to-rent/rooms  →  category_transaction (rent)
        if parts[0] == 'property-to-rent' and parts[1] in CATEGORY_LABELS:
            return 'category_transaction', {'category': parts[1], 'transaction': 'for-rent'}
        # /property-for-sale/{city}  →  property_transaction_city (clean URL)
        if parts[0] == 'property-for-sale':
            return 'property_transaction_city', {'transaction': 'for-sale', 'city': parts[1]}
        # /property-to-rent/{city}  →  property_transaction_city (clean URL)
        if parts[0] == 'property-to-rent':
            return 'property_transaction_city', {'transaction': 'for-rent', 'city': parts[1]}
        # /property-short-rent/house, /property-short-rent/shop etc.  →  property_subtype_modifier
        if parts[0] == 'property-short-rent' and parts[1] in PROPERTY_SUBTYPES:
            return 'property_subtype_modifier', {'subtype': parts[1]}
        # /property-short-rent/flats, /property-short-rent/rooms  →  category_modifier
        if parts[0] == 'property-short-rent' and parts[1] in CATEGORY_LABELS:
            return 'category_modifier', {'category': parts[1], 'modifier': 'short-term'}
        # /property-short-rent/{anything} → property_subtype_modifier (catch-all)
        if parts[0] == 'property-short-rent':
            return 'property_subtype_modifier', {'subtype': parts[1]}
        # /flats/for-sale, /rooms/for-sale  →  301 redirect to /property-for-sale/{cat}
        if parts[1] == 'for-sale' and parts[0] in CATEGORY_LABELS:
            return 'redirect_301', {'location': f'/property-for-sale/{parts[0]}'}
        # /flats/short-term, /rooms/short-term  →  301 redirect to /property-short-rent/{cat}
        if parts[1] == 'short-term' and parts[0] in CATEGORY_LABELS:
            return 'redirect_301', {'location': f'/property-short-rent/{parts[0]}'}
        # /{cat}/short-term  →  category_modifier (fallback)
        if parts[1] == 'short-term':
            return 'category_modifier', {
                'category': parts[0], 'modifier': 'short-term'
            }
        # /motors-for-sale/cars  →  cars category page
        if parts[0] == 'motors-for-sale' and parts[1] == 'cars':
            return 'cars_category', {}
        # /motors-for-sale/{make}
        if parts[0] == 'motors-for-sale':
            return 'cars_make', {'make': parts[1]}
        # /cars/for-rent  →  motors to rent landing page
        if parts[0] == 'cars' and parts[1] == 'for-rent':
            return 'cars_rent', {}
        # /cars/for-short-term-rent  →  motors short-term rent landing page
        if parts[0] == 'cars' and parts[1] == 'for-short-term-rent':
            return 'cars_short_rent', {}
        # Legacy /cars/{make} → 301
        if parts[0] == 'cars' and parts[1] not in ('for-rent', 'for-short-term-rent'):
            return 'redirect_301', {'location': f'/motors-for-sale/{parts[1]}'}
        return 'category_city', {'category': parts[0], 'city': parts[1]}
    if len(parts) == 1:
        # /flats, /rooms  →  301 redirect to /property-to-rent/{cat}
        if parts[0] in {'flats', 'rooms'}:
            return 'redirect_301', {'location': f'/property-to-rent/{parts[0]}'}
        # /property-for-sale  →  property_transaction (for-sale)
        if parts[0] == 'property-for-sale':
            return 'property_transaction', {'transaction': 'for-sale'}
        # /property-to-rent  →  property_transaction (for-rent)
        if parts[0] == 'property-to-rent':
            return 'property_transaction', {'transaction': 'for-rent'}
        # /property-short-rent  →  property_transaction_modifier
        if parts[0] == 'property-short-rent':
            return 'property_transaction_modifier', {'transaction': 'for-rent'}
        # /motors-for-sale  →  category cars
        if parts[0] == 'motors-for-sale':
            return 'category', {'category': 'cars'}
        # /motors-for-rent  →  motors to rent parent page
        if parts[0] == 'motors-for-rent':
            return 'motors_rent_parent', {}
        # /motors-for-short-term-rent  →  motors short-term rent parent page
        if parts[0] == 'motors-for-short-term-rent':
            return 'motors_short_rent_parent', {}
        # Legacy /cars → 301 redirect
        if parts[0] == 'cars':
            return 'redirect_301', {'location': '/motors-for-sale'}
        return 'category', {'category': parts[0]}

    return 'other', {}


# ══════════════════════════════════════════════════════════════════════════════
# Layer 2 – SEO data fetcher
# ══════════════════════════════════════════════════════════════════════════════
CATEGORY_LABELS = {
    'property':    'Property',    'real-estate': 'Property',
    'cars':        'Motors for Sale', 'motors':  'Motors',
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
    'cars':      '',           'motors':      'for sale',
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
    'cars':        'Browse new and used motors for sale across the UK from private sellers and dealers.',
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

FLATS_POPULAR_CITIES = [
    ('London',       'london'),
    ('Manchester',   'manchester'),
    ('Birmingham',   'birmingham'),
    ('Leeds',        'leeds'),
    ('Liverpool',    'liverpool'),
    ('Bristol',      'bristol'),
    ('Sheffield',    'sheffield'),
    ('Edinburgh',    'edinburgh'),
    ('Glasgow',      'glasgow'),
    ('Nottingham',   'nottingham'),
    ('Leicester',    'leicester'),
    ('Cardiff',      'cardiff'),
]

PROPERTY_SUBTYPES = {'shop', 'restaurant', 'industrial', 'office', 'hotel', 'house', 'studio', 'penthouse', 'duplex'}

PROPERTY_SUBTYPE_SEO = {
    'shop': {
        'label':       'Shops',
        'h1':          'Shops for Rent in the UK',
        'h1_short':    'Short-Term Shops for Rent in the UK',
        'intro':       ('Browse shops and retail spaces for rent across the UK. '
                        'Find commercial properties suitable for businesses, retail stores, '
                        'and investments in prime locations.'),
        'intro_short': ('Find short-term shops and retail spaces for rent across the UK. '
                        'Flexible commercial lets for businesses of all sizes.'),
    },
    'restaurant': {
        'label':       'Restaurants',
        'h1':          'Restaurants for Rent in the UK',
        'h1_short':    'Short-Term Restaurants for Rent in the UK',
        'intro':       ('Explore restaurants and food businesses for rent across the UK. '
                        'Ideal for cafes, takeaways, and fully equipped restaurant spaces.'),
        'intro_short': ('Find short-term restaurant spaces for rent across the UK. '
                        'Ideal for pop-ups, cafes, and temporary food businesses.'),
    },
    'industrial': {
        'label':       'Industrial Property',
        'h1':          'Industrial Property for Rent in the UK',
        'h1_short':    'Short-Term Industrial Property for Rent in the UK',
        'intro':       ('Browse industrial properties for rent across the UK, '
                        'including warehouses, factories, and storage facilities.'),
        'intro_short': ('Find short-term industrial units and warehouses for rent across the UK. '
                        'Flexible leases for businesses of all sizes.'),
    },
    'office': {
        'label':       'Offices',
        'h1':          'Offices for Rent in the UK',
        'h1_short':    'Short-Term Offices for Rent in the UK',
        'intro':       ('Find office spaces for rent across the UK, from small offices to large '
                        'commercial workspaces in major business locations.'),
        'intro_short': ('Find short-term office spaces for rent across the UK. '
                        'Flexible desk and workspace solutions for modern businesses.'),
    },
    'hotel': {
        'label':       'Hotels',
        'h1':          'Hotels for Rent in the UK',
        'h1_short':    'Short-Term Hotels for Rent in the UK',
        'intro':       ('Browse hotels and hospitality properties for rent across the UK. '
                        'Suitable for investors and operators in the hospitality industry.'),
        'intro_short': ('Find short-term hotel and hospitality property lets across the UK. '
                        'Ideal for seasonal operators and event-based businesses.'),
    },
    'house': {
        'label':       'Houses',
        'h1':          'Houses for Rent in the UK',
        'h1_short':    'Short-Term Houses for Rent in the UK',
        'intro':       ('Browse houses for long-term rent across the UK. '
                        'Find detached, semi-detached, terraced houses, cottages, and villas.'),
        'intro_short': ('Find short-term houses for rent across the UK. '
                        'Ideal for temporary stays, family relocations, and flexible living.'),
    },
}

PROPERTY_TYPE_NAV = [
    ('Flats',       '/flats'),
    ('Rooms',       '/rooms'),
    ('Shops',       '/property/shop'),
    ('Offices',     '/property/office'),
    ('Industrial',  '/property/industrial'),
    ('Restaurants', '/property/restaurant'),
    ('Hotels',      '/property/hotel'),
]

PROPERTY_TYPE_NAV_SALE = [
    ('Flats',       '/property-for-sale/flats'),
    ('Houses',      '/property-for-sale/house'),
    ('Shops',       '/property-for-sale/shop'),
    ('Offices',     '/property-for-sale/office'),
    ('Industrial',  '/property-for-sale/industrial'),
    ('Restaurants', '/property-for-sale/restaurant'),
    ('Hotels',      '/property-for-sale/hotel'),
]

PROPERTY_SUBTYPE_SALE_SEO = {
    'shop': {
        'label':  'Shops',
        'h1':     'Shops for Sale in the UK',
        'intro':  ('Browse shops and retail properties for sale across the UK. '
                   'Find freehold and leasehold retail units in prime locations.'),
    },
    'restaurant': {
        'label':  'Restaurants',
        'h1':     'Restaurants for Sale in the UK',
        'intro':  ('Explore restaurants and food businesses for sale across the UK. '
                   'Find fully equipped premises for cafes, takeaways, and dining establishments.'),
    },
    'industrial': {
        'label':  'Industrial Property',
        'h1':     'Industrial Property for Sale in the UK',
        'intro':  ('Browse industrial properties for sale across the UK, '
                   'including warehouses, factories, and storage units.'),
    },
    'office': {
        'label':  'Offices',
        'h1':     'Offices for Sale in the UK',
        'intro':  ('Find office buildings and commercial workspaces for sale across the UK. '
                   'Investment and owner-occupier opportunities in all major business locations.'),
    },
    'hotel': {
        'label':  'Hotels',
        'h1':     'Hotels for Sale in the UK',
        'intro':  ('Browse hotels and hospitality businesses for sale across the UK. '
                   'Ideal for investors and operators in the hospitality industry.'),
    },
    'house': {
        'label':  'Houses',
        'h1':     'Houses for Sale in the UK',
        'intro':  ('Browse houses for sale across the UK. Find detached, semi-detached, '
                   'terraced houses, cottages, bungalows, and villas in all major UK towns and cities.'),
    },
}

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
        _lt_norm = listing_type.lower() if listing_type else 'sale'
        _pt_norm = prop_type.lower() if prop_type else ''
        action_label = {
            'sale': 'for sale', 'long_rent': 'to rent',
            'short_rent': 'to rent', 'Sale': 'for sale',
            'Long_rent': 'to rent', 'Short_rent': 'to rent',
        }.get(listing_type, 'for sale')

        city_slug_url = re.sub(r'[^a-z0-9]+', '-', city.lower()).strip('-') if city else ''
        dist_slug_url = re.sub(r'[^a-z0-9]+', '-', district.lower()).strip('-') if district else ''

        # ── Cars: custom breadcrumb ───────────────────────────────────────────
        if _pt_norm == 'car':
            _is_short_rent = (_lt_norm == 'short_rent')
            _is_long_rent  = (_lt_norm in ('long_rent', 'rent'))
            if _is_short_rent:
                cat_label     = 'Motors for Short-Term Rent'
                _cat_rel_url  = '/motors-for-short-term-rent'
                _cars_rel_url = '/cars/for-short-term-rent'
            elif _is_long_rent:
                cat_label     = 'Motors to Rent'
                _cat_rel_url  = '/motors-for-rent'
                _cars_rel_url = '/cars/for-rent'
            else:
                cat_label     = 'Motors for Sale'
                _cat_rel_url  = '/motors-for-sale'
                _cars_rel_url = '/motors-for-sale/cars'
                _make_url_base = '/motors-for-sale'
            cat_url     = f'{PUBLIC_DOMAIN}{_cat_rel_url}'
            # Context-specific "Cars" sub-label (one level below the motors parent)
            if _is_short_rent:
                parent_label   = 'Cars for Short-Term Rent'
                parent_url     = _cars_rel_url
                _make_url_base = _cars_rel_url
            elif _is_long_rent:
                parent_label   = 'Cars to Rent'
                parent_url     = _cars_rel_url
                _make_url_base = _cars_rel_url
            else:
                parent_label   = 'Cars for Sale'
                parent_url     = _cars_rel_url
            car_make     = listing.get('car_make') or ''
            sub_label    = car_make
            sub_slug     = re.sub(r'[^a-z0-9]+', '-', car_make.lower()).strip('-') if car_make else ''
            _sub_url     = f'{_make_url_base}/{sub_slug}' if sub_slug else ''
            _city_url    = f'{_sub_url}/{city_slug_url}' if _sub_url and city_slug_url else ''
            _dist_url    = f'{_city_url}/{dist_slug_url}' if _city_url and dist_slug_url else ''
            is_real_estate = False

        # ── Property: existing breadcrumb logic ───────────────────────────────
        else:
            cat_label  = f'Property {action_label}'
            if _lt_norm == 'short_rent':
                cat_url = f'{PUBLIC_DOMAIN}/property-short-rent'
            elif _lt_norm == 'long_rent' or _pt_norm == 'room':
                cat_url = f'{PUBLIC_DOMAIN}/property-to-rent'
            else:
                cat_url = f'{PUBLIC_DOMAIN}/property-for-sale'

            sub_type = '' if _pt_norm == 'room' else (listing.get('sub_type') or '')
            if sub_type:
                sub_label = sub_type
                sub_slug  = re.sub(r'[^a-z0-9]+', '-', sub_type.lower()).strip('-')
            elif _pt_norm:
                _ptLabelMap = {'flat':'Flats','flats':'Flats','apartment':'Flats',
                               'studio':'Flats','penthouse':'Flats','duplex':'Flats',
                               'house':'House','room':'Rooms','land':'Land','building':'Building',
                               'office':'Office','shop':'Shop','restaurant':'Restaurant',
                               'industrial':'Industrial','hotel':'Hotel'}
                _ptSlugMap  = {'flat':'flats','flats':'flats','apartment':'flats','room':'rooms',
                               'studio':'flats','penthouse':'flats','duplex':'flats'}
                sub_slug  = _ptSlugMap.get(_pt_norm, _pt_norm)
                sub_label = _ptLabelMap.get(sub_slug, sub_slug.replace('-',' ').title())
            else:
                sub_label, sub_slug = '', ''

            real_estate_types = {'apartment', 'house', 'flat', 'room', 'villa',
                                 'studio', 'bungalow', 'maisonette', 'cottage'}
            is_real_estate = prop_type.lower() in real_estate_types

            _cat_rel_url  = cat_url.replace(PUBLIC_DOMAIN, '') or '/property'
            _sub_url  = f'{_cat_rel_url}/{sub_slug}' if sub_slug else ''
            _city_url = f'{_sub_url}/{city_slug_url}' if _sub_url and city_slug_url else ''
            _dist_url = f'{_city_url}/{dist_slug_url}' if _city_url and dist_slug_url else ''

            _flat_sub_slugs = {'studio', 'penthouse', 'duplex'}
            parent_label = 'Flats' if sub_slug in _flat_sub_slugs else ''
            parent_url   = f'{_cat_rel_url}/flats' if parent_label else ''

        bc_items = [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": PUBLIC_DOMAIN},
            {"@type": "ListItem", "position": 2, "name": cat_label, "item": cat_url},
        ]
        pos = 3
        if parent_label and parent_url:
            bc_items.append({"@type": "ListItem", "position": pos, "name": parent_label, "item": f'{PUBLIC_DOMAIN}{parent_url}'})
            pos += 1
        if sub_label and _sub_url:
            bc_items.append({"@type": "ListItem", "position": pos, "name": sub_label, "item": f'{PUBLIC_DOMAIN}{_sub_url}'})
            pos += 1
        if city and _city_url:
            bc_items.append({"@type": "ListItem", "position": pos, "name": city, "item": f'{PUBLIC_DOMAIN}{_city_url}'})
            pos += 1
        if district and _dist_url:
            bc_items.append({"@type": "ListItem", "position": pos, "name": district, "item": f'{PUBLIC_DOMAIN}{_dist_url}'})

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

        # ── SSR blocks: structured listing crumb (used by inject_ssr_body) ────
        seo['ssr'] = {
            'prop_title':    title,
            'listing_id':    str(lid),
            'listing_crumb': {
                'cat_label':    cat_label,
                'cat_url':      _cat_rel_url,
                'parent_label': parent_label,
                'parent_url':   parent_url,
                'sub_label':    sub_label,
                'sub_url':      _sub_url,
                'city':         city,
                'city_url':     _city_url,
                'district':     district,
                'dist_url':     _dist_url,
            },
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
        if cat == 'flats' and not city_links:
            city_links = [
                (label, f'/flats/{slug}') for label, slug in FLATS_POPULAR_CITIES
            ]

        related_links = []
        if cat == 'flats':
            related_links = [('Looking for short-term rentals?', 'Browse short-term flats across the UK', '/property-short-rent/flats')]

        seo['ssr'] = {
            'h1':            h1,
            'intro':         intro,
            'breadcrumbs':   [
                ('Home', '/'),
                (cat_label, None),
            ],
            'city_links':    city_links,
            'cat_label':     cat_label,
            'related_links': related_links,
            'type':          'category',
        }
        return seo

    # ── Category + modifier (e.g. /rooms/short-term) ──────────────────────────
    elif page_type == 'category_modifier':
        cat       = params.get('category', '')
        modifier  = params.get('modifier', '')
        cat_label = CATEGORY_LABELS.get(cat, cat.replace('-', ' ').title())
        canonical = f'{PUBLIC_DOMAIN}/property-short-rent/{cat}'

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

        short_rent_url = f'{PUBLIC_DOMAIN}/property-short-rent'
        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": "Property for Short-Term Rent", "item": short_rent_url},
                {"@type": "ListItem", "position": 3,
                 "name": cat_label, "item": canonical},
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
            related_links = [('Looking for long-term rentals?', 'Browse long-term flats across the UK', '/flats')]

        seo['ssr'] = {
            'h1':            h1,
            'intro':         intro,
            'breadcrumbs':   [
                ('Home', '/'),
                ('Property for Short-Term Rent', '/property-short-rent'),
                (cat_label, None),
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
        canonical   = f'{PUBLIC_DOMAIN}/property-to-rent' if is_rent else f'{PUBLIC_DOMAIN}/property-for-sale'

        if is_rent:
            h1    = 'Property for Rent in the UK'
            intro = ('Browse all types of property for rent across the UK, including flats, '
                     'houses, rooms, and commercial spaces. Find both long-term and short-term '
                     'rental options to suit your needs.')
        else:
            h1    = 'Property for Sale in the UK'
            intro = ('Discover property for sale across the UK, including flats, houses, land, '
                     'and commercial property. Browse listings from private sellers and agents '
                     'in all regions.')
        desc  = intro[:160]

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": h1, "item": canonical},
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
        _city_prefix = 'property-to-rent' if is_rent else 'property-for-sale'
        city_links = [
            (label, f'/{_city_prefix}/{slug}')
            for label, slug in FLATS_POPULAR_CITIES
        ]
        related_links = []
        if is_rent:
            related_links = [('Looking for short-term rentals?', 'Browse short-term properties for rent', '/property-short-rent')]
            type_links = PROPERTY_TYPE_NAV
        else:
            type_links = PROPERTY_TYPE_NAV_SALE

        seo['ssr'] = {
            'h1':            h1,
            'intro':         intro,
            'breadcrumbs':   [
                ('Home', '/'),
                (h1, None),
            ],
            'city_links':    city_links,
            'cat_label':     f'Property {verb}',
            'type_links':    type_links,
            'related_links': related_links,
            'type':          'category',
        }
        return seo

    # ── /property/for-rent/short-term ─────────────────────────────────────────
    elif page_type == 'property_transaction_modifier':
        transaction = params.get('transaction', 'for-rent')
        canonical   = f'{PUBLIC_DOMAIN}/property-short-rent'
        parent_url  = f'{PUBLIC_DOMAIN}/property-to-rent'

        h1    = 'Short-Term Property for Rent in the UK'
        intro = ('Explore short-term property rentals across the UK, including flats, rooms, '
                 'and houses. Ideal for temporary stays, business trips, and flexible living.')
        desc  = intro[:160]

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": "Property for Short-Term Rent", "item": canonical},
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
                ('Property for Short-Term Rent', None),
            ],
            'related_links': [('Looking for long-term rentals?', 'Browse all properties for long-term rent', '/property-to-rent')],
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
        parent_url  = f'{PUBLIC_DOMAIN}/property-to-rent' if is_rent else f'{PUBLIC_DOMAIN}/property-for-sale'
        _tx_prefix  = 'property-to-rent' if is_rent else 'property-for-sale'
        canonical   = f'{PUBLIC_DOMAIN}/{_tx_prefix}/{city_slug}'

        if is_rent:
            h1    = f'Property for Rent in {city}'
            intro = (f'Browse all property for rent in {city}, including flats, houses, and rooms. '
                     f'Find both long-term and short-term rental options across the city.')
        else:
            h1    = f'Property for Sale in {city}'
            intro = (f'Explore property for sale in {city}, including flats, houses, and '
                     f'investment opportunities. Find the best deals across the city.')
        desc  = intro[:160]

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": f'Property {verb}', "item": parent_url},
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
        parent_label = 'Property for Rent' if is_rent else 'Property for Sale'
        seo['ssr'] = {
            'h1':          h1,
            'intro':       intro,
            'breadcrumbs': [
                ('Home', '/'),
                (parent_label, '/property-to-rent' if is_rent else '/property-for-sale'),
                (city, None),
            ],
            'type': 'category',
        }
        return seo

    # ── /property/{subtype} (e.g. /property/shop, /property/office) ───────────
    elif page_type == 'property_subtype':
        subtype  = params.get('subtype', '')
        data     = PROPERTY_SUBTYPE_SEO.get(subtype, {})
        label    = data.get('label', subtype.title())
        h1       = data.get('h1', f'{label} for Rent in the UK')
        intro    = data.get('intro', f'Browse {label.lower()} for rent across the UK on Bazar.')
        canonical = f'{PUBLIC_DOMAIN}/property/{subtype}'
        desc      = intro[:160]

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": "Property for Rent", "item": f'{PUBLIC_DOMAIN}/property-to-rent'},
                {"@type": "ListItem", "position": 3,
                 "name": h1, "item": canonical},
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
        city_links = [
            (lbl, f'/property/{subtype}/{slug}')
            for lbl, slug in FLATS_POPULAR_CITIES
        ]
        seo['ssr'] = {
            'h1':          h1,
            'intro':       intro,
            'breadcrumbs': [
                ('Home', '/'),
                ('Property for Rent', '/property-to-rent'),
                (h1, None),
            ],
            'city_links':  city_links,
            'cat_label':   label,
            'related_links': [('Looking for short-term options?', f'Browse short-term {label.lower()} for rent', f'/property-short-rent/{subtype}')],
            'type':        'category',
        }
        return seo

    # ── /property/{subtype}/short-term ────────────────────────────────────────
    elif page_type == 'property_subtype_modifier':
        subtype   = params.get('subtype', '')
        data      = PROPERTY_SUBTYPE_SEO.get(subtype, {})
        label     = data.get('label', subtype.title())
        h1        = data.get('h1_short', f'Short-Term {label} for Rent in the UK')
        intro     = data.get('intro_short', f'Find short-term {label.lower()} for rent across the UK on Bazar.')
        canonical = f'{PUBLIC_DOMAIN}/property-short-rent/{subtype}'
        parent_url = f'{PUBLIC_DOMAIN}/property-to-rent/{subtype}'
        desc      = intro[:160]

        short_rent_url = f'{PUBLIC_DOMAIN}/property-short-rent'
        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": "Property for Short-Term Rent", "item": short_rent_url},
                {"@type": "ListItem", "position": 3,
                 "name": label, "item": canonical},
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
                ('Property for Short-Term Rent', '/property-short-rent'),
                (label, None),
            ],
            'related_links': [(f'Looking for long-term options?', f'Browse all {label.lower()} for rent', f'/property-to-rent/{subtype}')],
            'type':        'category',
        }
        return seo

    # ── /property/{subtype}/for-rent (e.g. /property/house/for-rent) ──────────
    elif page_type == 'property_subtype_rent':
        subtype   = params.get('subtype', '')
        data      = PROPERTY_SUBTYPE_SEO.get(subtype, {})
        label     = data.get('label', subtype.title())
        h1        = data.get('h1', f'{label} for Rent in the UK')
        intro     = data.get('intro', f'Browse {label.lower()} for rent across the UK on Bazar.')
        canonical = f'{PUBLIC_DOMAIN}/property-to-rent/{subtype}'
        desc      = intro[:160]

        _is_flat_subtype = subtype in {'studio', 'penthouse', 'duplex'}
        _bc_items_rent = [
            {"@type": "ListItem", "position": 1,
             "name": "Home", "item": PUBLIC_DOMAIN},
            {"@type": "ListItem", "position": 2,
             "name": "Property for Rent", "item": f'{PUBLIC_DOMAIN}/property-to-rent'},
        ]
        if _is_flat_subtype:
            _bc_items_rent.append({"@type": "ListItem", "position": 3,
                "name": "Flats", "item": f'{PUBLIC_DOMAIN}/property-to-rent/flats'})
            _bc_items_rent.append({"@type": "ListItem", "position": 4,
                "name": h1, "item": canonical})
        else:
            _bc_items_rent.append({"@type": "ListItem", "position": 3,
                "name": h1, "item": canonical})
        breadcrumb_schema = {"@type": "BreadcrumbList", "itemListElement": _bc_items_rent}
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
        city_links = [
            (lbl, f'/property-to-rent/{subtype}/{slug}')
            for lbl, slug in FLATS_POPULAR_CITIES
        ]
        seo['ssr'] = {
            'h1':          h1,
            'intro':       intro,
            'breadcrumbs': (
                [('Home', '/'), ('Property for Rent', '/property-to-rent'),
                 ('Flats', '/property-to-rent/flats'), (h1, None)]
                if _is_flat_subtype else
                [('Home', '/'), ('Property for Rent', '/property-to-rent'), (h1, None)]
            ),
            'city_links':  city_links,
            'cat_label':   label,
            'related_links': [
                ('Looking for short-term options?', f'Browse short-term {label.lower()} for rent', f'/property-short-rent/{subtype}'),
                ('Looking to buy instead?', f'Browse {label.lower()} for sale', f'/property-for-sale/{subtype}'),
            ],
            'type': 'category',
        }
        return seo

    # ── /property-for-sale/flats, /property-to-rent/flats etc. ───────────────
    elif page_type == 'category_transaction':
        cat         = params.get('category', '')
        transaction = params.get('transaction', 'for-sale')
        is_rent     = (transaction == 'for-rent')
        cat_label   = CATEGORY_LABELS.get(cat, cat.replace('-', ' ').title())

        if is_rent:
            canonical        = f'{PUBLIC_DOMAIN}/property-to-rent/{cat}'
            h1               = f'{cat_label} to Rent in the UK'
            intro            = (f'Browse {cat_label.lower()} to rent across the UK. '
                                f'Find long-term lets from private landlords and letting agents nationwide.')
            bc_parent_label  = 'Property to Rent'
            bc_parent_url    = f'{PUBLIC_DOMAIN}/property-to-rent'
            related_links    = [(f'Looking to buy instead?', f'Browse {cat_label.lower()} for sale', f'/property-for-sale/{cat}')]
        else:
            canonical        = f'{PUBLIC_DOMAIN}/property-for-sale/{cat}'
            h1               = f'{cat_label} for Sale in the UK'
            intro            = (f'Browse {cat_label.lower()} for sale across the UK. '
                                f'Find the best deals on {cat_label.lower()} from private sellers and agents nationwide.')
            bc_parent_label  = 'Property for Sale'
            bc_parent_url    = f'{PUBLIC_DOMAIN}/property-for-sale'
            related_links    = [(f'Looking to rent instead?', f'Browse {cat_label.lower()} for rent', f'/property-to-rent/{cat}')]

        desc = intro[:160]

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": bc_parent_label, "item": bc_parent_url},
                {"@type": "ListItem", "position": 3,
                 "name": h1, "item": canonical},
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
                (bc_parent_label, '/property-to-rent' if is_rent else '/property-for-sale'),
                (h1, None),
            ],
            'related_links': related_links,
            'type':        'category',
        }
        return seo

    # ── /property/{subtype}/for-sale ──────────────────────────────────────────
    elif page_type == 'property_subtype_sale':
        subtype   = params.get('subtype', '')
        data      = PROPERTY_SUBTYPE_SALE_SEO.get(subtype, {})
        label     = data.get('label', subtype.title())
        h1        = data.get('h1', f'{label} for Sale in the UK')
        intro     = data.get('intro', f'Browse {label.lower()} for sale across the UK on Bazar.')
        canonical = f'{PUBLIC_DOMAIN}/property-for-sale/{subtype}'
        desc      = intro[:160]

        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2,
                 "name": "Property for Sale", "item": f'{PUBLIC_DOMAIN}/property-for-sale'},
                {"@type": "ListItem", "position": 3,
                 "name": h1, "item": canonical},
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
        city_links = [
            (lbl, f'/property/{subtype}/for-sale/{slug}')
            for lbl, slug in FLATS_POPULAR_CITIES
        ]
        seo['ssr'] = {
            'h1':          h1,
            'intro':       intro,
            'breadcrumbs': [
                ('Home', '/'),
                ('Property for Sale', '/property-for-sale'),
                (h1, None),
            ],
            'city_links':  city_links,
            'cat_label':   label,
            'related_links': [(f'Looking to rent instead?', f'Browse {label.lower()} for rent', f'/property/{subtype}')],
            'type':        'category',
        }
        return seo

    # ── /property-for-sale/land, /property-for-sale/building, etc. ───────────
    elif page_type == 'property_sale_type':
        sale_type = params.get('sale_type', '')
        label_map = {
            'land':                   'Land',
            'building':               'Buildings',
            'business-or-investment': 'Business or Investment',
        }
        label    = label_map.get(sale_type, sale_type.replace('-', ' ').title())
        h1       = f'{label} for Sale in the UK'
        intro    = f'Browse {label.lower()} for sale across the UK. Find the best deals from private sellers and agents.'
        canonical = f'{PUBLIC_DOMAIN}/property-for-sale/{sale_type}'
        desc     = intro[:160]
        breadcrumb_schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": PUBLIC_DOMAIN},
                {"@type": "ListItem", "position": 2, "name": "Property for Sale", "item": f'{PUBLIC_DOMAIN}/property-for-sale'},
                {"@type": "ListItem", "position": 3, "name": h1, "item": canonical},
            ]
        }
        schema = {"@context": "https://schema.org", "@graph": [
            {"@type": "CollectionPage", "name": h1, "description": desc, "url": canonical, "breadcrumb": breadcrumb_schema},
            breadcrumb_schema,
        ]}
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
                ('Property for Sale', '/property-for-sale'),
                (h1, None),
            ],
            'city_links':    [],
            'cat_label':     label,
            'related_links': [],
            'type':          'category',
        }
        return seo

    # ── /property-for-sale/{subtype}/{city} ──────────────────────────────────
    elif page_type == 'property_subtype_city':
        _trans  = params.get('transaction', 'property-for-sale')
        _sub    = params.get('subtype', '')
        _city_s = params.get('city', '')
        _city   = _city_s.replace('-', ' ').title()
        _sub_label = _sub.replace('-', ' ').title()
        _is_short = (_trans == 'property-short-rent')
        _trans_label = 'for Short-Term Rent' if _is_short else ('for Rent' if 'rent' in _trans else 'for Sale')
        _trans_cat   = 'Property for Short-Term Rent' if _is_short else ('Property for Sale' if 'sale' in _trans else 'Property to Rent')
        _trans_base  = f'/{_trans}'
        _is_flat_sub = _sub in {'studio', 'penthouse', 'duplex'}
        _flats_base  = f'{_trans_base}/flats'
        h1       = f'{_sub_label} {_trans_label} in {_city}'
        intro    = f'Browse {_sub_label.lower()} {_trans_label.lower()} in {_city}. Find the best deals from private sellers and agents.'
        canonical = f'{PUBLIC_DOMAIN}{_trans_base}/{_sub}/{_city_s}'
        desc = intro[:160]
        _bc_items = [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": PUBLIC_DOMAIN},
            {"@type": "ListItem", "position": 2, "name": _trans_cat, "item": f'{PUBLIC_DOMAIN}{_trans_base}'},
        ]
        if _is_flat_sub:
            _bc_items.append({"@type": "ListItem", "position": 3, "name": "Flats", "item": f'{PUBLIC_DOMAIN}{_flats_base}'})
            _bc_items.append({"@type": "ListItem", "position": 4, "name": _sub_label, "item": f'{PUBLIC_DOMAIN}{_trans_base}/{_sub}'})
            _bc_items.append({"@type": "ListItem", "position": 5, "name": h1, "item": canonical})
        else:
            _bc_items.append({"@type": "ListItem", "position": 3, "name": _sub_label, "item": f'{PUBLIC_DOMAIN}{_trans_base}/{_sub}'})
            _bc_items.append({"@type": "ListItem", "position": 4, "name": h1, "item": canonical})
        breadcrumb_schema = {"@type": "BreadcrumbList", "itemListElement": _bc_items}
        schema = {"@context": "https://schema.org", "@graph": [
            {"@type": "CollectionPage", "name": h1, "description": desc, "url": canonical, "breadcrumb": breadcrumb_schema},
            breadcrumb_schema,
        ]}
        seo.update({'title': f'{h1} | Bazar UK', 'description': desc, 'canonical': canonical, 'json_ld': json.dumps(schema)})
        _bc_crumbs = [('Home', '/'), (_trans_cat, _trans_base)]
        if _is_flat_sub:
            _bc_crumbs.append(('Flats', _flats_base))
        _bc_crumbs += [(_sub_label, f'{_trans_base}/{_sub}'), (h1, None)]
        seo['ssr'] = {
            'h1': h1, 'intro': intro,
            'breadcrumbs': _bc_crumbs,
            'city_links': [], 'cat_label': _sub_label, 'related_links': [], 'type': 'category',
        }
        return seo

    # ── /property-for-sale/{subtype}/{city}/{district} ────────────────────────
    elif page_type == 'property_subtype_city_district':
        _trans  = params.get('transaction', 'property-for-sale')
        _sub    = params.get('subtype', '')
        _city_s = params.get('city', '')
        _dist_s = params.get('district', '')
        _city   = _city_s.replace('-', ' ').title()
        _dist   = _dist_s.replace('-', ' ').title()
        _sub_label = _sub.replace('-', ' ').title()
        _is_short = (_trans == 'property-short-rent')
        _trans_label = 'for Short-Term Rent' if _is_short else ('for Rent' if 'rent' in _trans else 'for Sale')
        _trans_cat   = 'Property for Short-Term Rent' if _is_short else ('Property for Sale' if 'sale' in _trans else 'Property to Rent')
        _trans_base  = f'/{_trans}'
        _is_flat_sub = _sub in {'studio', 'penthouse', 'duplex'}
        _flats_base  = f'{_trans_base}/flats'
        h1       = f'{_sub_label} {_trans_label} in {_dist}, {_city}'
        intro    = f'Browse {_sub_label.lower()} {_trans_label.lower()} in {_dist}, {_city}. Find local deals from private sellers and agents.'
        canonical = f'{PUBLIC_DOMAIN}{_trans_base}/{_sub}/{_city_s}/{_dist_s}'
        desc = intro[:160]
        _bc_items = [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": PUBLIC_DOMAIN},
            {"@type": "ListItem", "position": 2, "name": _trans_cat, "item": f'{PUBLIC_DOMAIN}{_trans_base}'},
        ]
        if _is_flat_sub:
            _bc_items.append({"@type": "ListItem", "position": 3, "name": "Flats", "item": f'{PUBLIC_DOMAIN}{_flats_base}'})
            _bc_items.append({"@type": "ListItem", "position": 4, "name": _sub_label, "item": f'{PUBLIC_DOMAIN}{_trans_base}/{_sub}'})
            _bc_items.append({"@type": "ListItem", "position": 5, "name": f'{_sub_label} in {_city}', "item": f'{PUBLIC_DOMAIN}{_trans_base}/{_sub}/{_city_s}'})
            _bc_items.append({"@type": "ListItem", "position": 6, "name": h1, "item": canonical})
        else:
            _bc_items.append({"@type": "ListItem", "position": 3, "name": _sub_label, "item": f'{PUBLIC_DOMAIN}{_trans_base}/{_sub}'})
            _bc_items.append({"@type": "ListItem", "position": 4, "name": f'{_sub_label} in {_city}', "item": f'{PUBLIC_DOMAIN}{_trans_base}/{_sub}/{_city_s}'})
            _bc_items.append({"@type": "ListItem", "position": 5, "name": h1, "item": canonical})
        breadcrumb_schema = {"@type": "BreadcrumbList", "itemListElement": _bc_items}
        schema = {"@context": "https://schema.org", "@graph": [
            {"@type": "CollectionPage", "name": h1, "description": desc, "url": canonical, "breadcrumb": breadcrumb_schema},
            breadcrumb_schema,
        ]}
        seo.update({'title': f'{h1} | Bazar UK', 'description': desc, 'canonical': canonical, 'json_ld': json.dumps(schema)})
        _bc_crumbs = [('Home', '/'), (_trans_cat, _trans_base)]
        if _is_flat_sub:
            _bc_crumbs.append(('Flats', _flats_base))
        _bc_crumbs += [
            (_sub_label, f'{_trans_base}/{_sub}'),
            (_city, f'{_trans_base}/{_sub}/{_city_s}'),
            (h1, None),
        ]
        seo['ssr'] = {
            'h1': h1, 'intro': intro,
            'breadcrumbs': _bc_crumbs,
            'city_links': [], 'cat_label': _sub_label, 'related_links': [], 'type': 'category',
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
            related_links = [('Looking for long-term rentals?', f'Browse long-term flats in {city}', f'/flats/{city_slug}')]

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
            related_links = [('Looking for short-term rentals?', f'Browse short-term flats in {city}', f'/flats/{city_slug}/short-term')]

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

    # ── Cars: make / make+city / make+city+district ───────────────────────────
    elif page_type in ('cars_make', 'cars_make_city', 'cars_make_city_district'):
        make_slug    = params.get('make', '')
        city_slug    = params.get('city', '')
        district_slug= params.get('district', '')
        is_rent       = bool(params.get('is_rent', False))
        is_short_rent = bool(params.get('is_short_rent', False))
        make   = make_slug.replace('-', ' ').title()
        city   = city_slug.replace('-', ' ').title()
        district = district_slug.replace('-', ' ').title()

        if is_short_rent:
            cat_label  = 'Motors for Short-Term Rent'
            action     = 'for short-term rent'
            _cat_url   = '/motors-for-short-term-rent'
            _cars_base = '/cars/for-short-term-rent'
        elif is_rent:
            cat_label  = 'Motors to Rent'
            action     = 'to rent'
            _cat_url   = '/motors-for-rent'
            _cars_base = '/cars/for-rent'
        else:
            cat_label  = 'Motors for Sale'
            action     = 'for sale'
            _cat_url   = '/motors-for-sale'
            _cars_base = '/motors-for-sale'

        if district and city:
            h1 = f'{make} cars {action} in {district}, {city}'
            canonical = f'{PUBLIC_DOMAIN}{_cars_base}/{make_slug}/{city_slug}/{district_slug}'
        elif city:
            h1 = f'{make} cars {action} in {city}'
            canonical = f'{PUBLIC_DOMAIN}{_cars_base}/{make_slug}/{city_slug}'
        else:
            h1 = f'{make} cars {action}'
            canonical = f'{PUBLIC_DOMAIN}{_cars_base}/{make_slug}'

        intro = (f'Browse {make} cars {action}'
                 + (f' in {district}, {city}' if district and city else
                    f' in {city}' if city else ' in the UK')
                 + ' on Bazar UK classifieds.')

        # Cars sub-label: one level below the motors parent
        if is_short_rent:
            _cars_label = 'Cars for Short-Term Rent'
            _cars_url   = '/cars/for-short-term-rent'
        elif is_rent:
            _cars_label = 'Cars to Rent'
            _cars_url   = '/cars/for-rent'
        else:
            _cars_label = 'Cars for Sale'
            _cars_url   = '/motors-for-sale/cars'
        breadcrumbs = [('Home', '/'), (cat_label, _cat_url), (_cars_label, _cars_url), (make, f'{_cars_base}/{make_slug}')]
        if city:
            breadcrumbs.append((city, f'{_cars_base}/{make_slug}/{city_slug}'))
        if district:
            breadcrumbs.append((district, None))

        _robots = 'index, follow' if not district else 'noindex, follow'
        seo.update({
            'title':       f'{h1} | Bazar UK',
            'description': intro,
            'canonical':   canonical,
            'robots':      _robots,
        })
        seo['ssr'] = {
            'h1':          h1,
            'intro':       intro,
            'breadcrumbs': breadcrumbs,
            'type':        'category',
            'car_make':    make_slug,
            'car_city':    city_slug,
            'car_district': district_slug,
        }
        return seo

    elif page_type == 'cars_category':
        seo.update({
            'title':       'Cars for Sale in the UK | Bazar UK',
            'description': 'Browse cars for sale across the UK on Bazar UK classifieds.',
            'canonical':   f'{PUBLIC_DOMAIN}/motors-for-sale/cars',
            'robots':      'index, follow',
        })
        seo['ssr'] = {
            'h1':    'Cars for Sale in the UK',
            'intro': 'Browse new and used cars for sale across the UK from private sellers and dealers.',
            'breadcrumbs': [
                ('Home', '/'),
                ('Motors for Sale', '/motors-for-sale'),
                ('Cars for Sale', None),
            ],
            'type': 'category',
        }
        return seo

    elif page_type == 'cars_rent':
        seo.update({
            'title':       'Cars to Rent in the UK | Bazar UK',
            'description': 'Browse cars for long-term rent across the UK on Bazar UK classifieds.',
            'canonical':   f'{PUBLIC_DOMAIN}/cars/for-rent',
            'robots':      'index, follow',
        })
        seo['ssr'] = {
            'h1':    'Cars to Rent in the UK',
            'intro': 'Browse cars available for long-term rent across the UK from private sellers and dealers.',
            'breadcrumbs': [
                ('Home', '/'),
                ('Motors to Rent', '/motors-for-rent'),
                ('Cars to Rent', None),
            ],
            'type': 'category',
        }
        return seo

    elif page_type == 'cars_short_rent':
        seo.update({
            'title':       'Cars for Short-Term Rent in the UK | Bazar UK',
            'description': 'Browse cars for short-term rent across the UK on Bazar UK classifieds.',
            'canonical':   f'{PUBLIC_DOMAIN}/cars/for-short-term-rent',
            'robots':      'index, follow',
        })
        seo['ssr'] = {
            'h1':    'Cars for Short-Term Rent in the UK',
            'intro': 'Browse cars available for short-term rent across the UK from private sellers and dealers.',
            'breadcrumbs': [
                ('Home', '/'),
                ('Motors for Short-Term Rent', '/motors-for-short-term-rent'),
                ('Cars for Short-Term Rent', None),
            ],
            'type': 'category',
        }
        return seo

    elif page_type == 'motors_rent_parent':
        seo.update({
            'title':       'Motors to Rent in the UK | Bazar UK',
            'description': 'Browse cars, vans, motorbikes and more to rent across the UK on Bazar UK classifieds.',
            'canonical':   f'{PUBLIC_DOMAIN}/motors-for-rent',
            'robots':      'index, follow',
        })
        seo['ssr'] = {
            'h1':    'Motors to Rent in the UK',
            'intro': 'Browse all motor vehicles available for long-term rent across the UK from private sellers and dealers.',
            'breadcrumbs': [
                ('Home', '/'),
                ('Motors to Rent', None),
            ],
            'type': 'category',
        }
        return seo

    elif page_type == 'motors_short_rent_parent':
        seo.update({
            'title':       'Motors for Short-Term Rent in the UK | Bazar UK',
            'description': 'Browse cars, vans, motorbikes and more for short-term rent across the UK on Bazar UK classifieds.',
            'canonical':   f'{PUBLIC_DOMAIN}/motors-for-short-term-rent',
            'robots':      'index, follow',
        })
        seo['ssr'] = {
            'h1':    'Motors for Short-Term Rent in the UK',
            'intro': 'Browse all motor vehicles available for short-term rent across the UK from private sellers and dealers.',
            'breadcrumbs': [
                ('Home', '/'),
                ('Motors for Short-Term Rent', None),
            ],
            'type': 'category',
        }
        return seo

    # ── Search (noindex always) ───────────────────────────────────────────────
    elif page_type == 'latest_updates':
        seo.update({
            'title':       'Latest Update | Bazar UK',
            'description': 'Browse the most recently listed properties and ads across the UK on Bazar.',
            'robots':      'index, follow',
            'ssr': {
                'type': 'category',
                'h1':   'Latest Update',
                'intro': 'The most recently listed ads across the UK. New properties, rooms, and more added every day.',
                'breadcrumbs': [
                    ('Home', '/'),
                    ('Latest Update', '/latest-updates'),
                ],
                'related_links': [],
                'city_links':    [],
                'type_links':    [],
            },
        })
        return seo

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
        '<!-- Google tag (gtag.js) -->',
        '<script async src="https://www.googletagmanager.com/gtag/js?id=AW-1808636054"></script>',
        '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag(\'js\',new Date());gtag(\'config\',\'AW-1808636054\');gtag(\'config\',\'G-3N283S7F8N\');</script>',
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
_RE_GTAG = re.compile(
    r'<!--\s*Google tag[^-]*-->\s*<script[^>]+googletagmanager[^>]*></script>\s*<script>window\.dataLayer.*?</script>',
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
    html = _RE_GTAG.sub('', html)
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

    # ── Inject listing ID as window.__cid so JS can reliably access it ────────
    listing_id = ssr.get('listing_id', '')
    if listing_id:
        cid_script = f'<script>window.__cid="{listing_id}";</script>'
        # Insert right after opening <body> tag
        html = re.sub(r'(<body[^>]*>)', r'\1' + cid_script, html, count=1)

    # ── Replace placeholder title in #prop-title ──────────────────────────────
    prop_title = ssr.get('prop_title', '')
    if prop_title:
        m = _RE_PROP_TITLE.search(html)
        if m:
            html = html[:m.start()] + f'<h1{m.group(1)}>{_esc(prop_title)}</h1>' + html[m.end():]

    # ── Replace breadcrumb list in #breadcrumb ────────────────────────────────
    # Use structured listing_crumb if available (generates HTML with JS-compatible IDs)
    listing_crumb = ssr.get('listing_crumb')
    if listing_crumb:
        items = []
        # Home (always first, static)
        items.append('<li><a href="/">Home</a><span class="icon-arrow-r"></span></li>')
        # Category (e.g. "Property for Sale")
        cl = listing_crumb.get('cat_label', '')
        cu = listing_crumb.get('cat_url', '/')
        if cl:
            items.append(f'<li><a href="{_attr(cu)}" id="bread-category">{_esc(cl)}</a>'
                         f'<span class="icon-arrow-r"></span></li>')
        # Parent (e.g. "Flats" for Studio / Penthouse / Duplex)
        pl = listing_crumb.get('parent_label', '')
        pu = listing_crumb.get('parent_url', '')
        if pl and pu:
            items.append(f'<li id="bread-parent-li"><a href="{_attr(pu)}" id="bread-parent">{_esc(pl)}</a>'
                         f'<span class="icon-arrow-r" id="bread-parent-arrow"></span></li>')
        # Sub-type (e.g. "Studio")
        sl = listing_crumb.get('sub_label', '')
        su = listing_crumb.get('sub_url', '')
        if sl:
            has_city = bool(listing_crumb.get('city', ''))
            arrow_style = '' if has_city else ' style="display:none;"'
            arrow = f'<span class="icon-arrow-r" id="bread-type-arrow"{arrow_style}></span>'
            items.append(f'<li><a href="{_attr(su)}" id="bread-type">{_esc(sl)}</a>{arrow}</li>')
        # City
        cv = listing_crumb.get('city', '')
        cvu = listing_crumb.get('city_url', '')
        if cv and cvu:
            has_dist = bool(listing_crumb.get('district', ''))
            city_arrow = (f'<span class="icon-arrow-r" id="bread-city-arrow"></span>'
                          if has_dist else '')
            items.append(f'<li id="bread-city-li"><a href="{_attr(cvu)}" id="bread-city">'
                         f'{_esc(cv)}</a>{city_arrow}</li>')
        # District
        dv = listing_crumb.get('district', '')
        dvu = listing_crumb.get('dist_url', '')
        if dv:
            d_link = (f'<a href="{_attr(dvu)}" id="bread-district">{_esc(dv)}</a>'
                      if dvu else f'<span id="bread-district">{_esc(dv)}</span>')
            items.append(f'<li id="bread-district-li">{d_link}</li>')

        new_ul = '<ul class="bread-custom" id="breadcrumb">\n' + \
                 '\n'.join(f'                        {li}' for li in items) + \
                 '\n                     </ul>'
        m = _RE_BREADCRUMB.search(html)
        if m:
            html = html[:m.start()] + new_ul + html[m.end():]

    elif ssr.get('breadcrumbs'):
        # Fallback: plain breadcrumb list (used by non-listing pages if needed)
        breadcrumbs = ssr['breadcrumbs']
        items = []
        for i, (label, href) in enumerate(breadcrumbs):
            is_last = (i == len(breadcrumbs) - 1)
            # Strip geographic suffix for cleaner breadcrumb display (H1 already has it)
            bc_label = label.replace(' in the UK', '').replace(' in the U.K.', '').strip()
            safe_label = _esc(bc_label)
            if not is_last:
                items.append(f'<li><a href="{href}">{safe_label}</a>'
                              f'<span class="icon-arrow-r"></span></li>')
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
    """Inject visible H1, intro text, breadcrumbs, city links, type links and related links into search.html
    for category and category+city pages."""

    h1             = ssr.get('h1', '')
    intro          = ssr.get('intro', '')
    breadcrumbs    = ssr.get('breadcrumbs', [])
    city_links     = ssr.get('city_links', [])
    cat_label      = ssr.get('cat_label', '')
    related_links  = ssr.get('related_links', [])
    type_links     = ssr.get('type_links', [])

    # ── Inject window.__bazarCarData for car category pages ──────────────────
    car_make     = ssr.get('car_make', '')
    car_city     = ssr.get('car_city', '')
    car_district = ssr.get('car_district', '')
    if car_make or (h1 and 'cars' in h1.lower()):
        _cd = json.dumps({'make': car_make, 'city': car_city, 'district': car_district})
        car_script = f'<script>window.__bazarCarData={_cd};</script>'
        html = re.sub(r'(<body[^>]*>)', r'\1' + car_script, html, count=1)

    # ── Build replacement srBreadcrumb ────────────────────────────────────────
    if breadcrumbs:
        items = []
        for i, (label, href) in enumerate(breadcrumbs):
            is_last = (i == len(breadcrumbs) - 1)
            # Strip geographic suffix for cleaner breadcrumb display (H1 already has it)
            bc_label = label.replace(' in the UK', '').replace(' in the U.K.', '').strip()
            safe_label = _esc(bc_label)
            if not is_last:
                if href:
                    items.append(
                        f'<li><a href="{_attr(href)}">{safe_label}</a>'
                        f'<span class="icon-arrow-r"></span></li>'
                    )
                else:
                    items.append(
                        f'<li><span>{safe_label}</span>'
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

    # ── Footer SEO placeholder — now empty (type_links moved before footer) ──
    html = html.replace('<!-- FOOTER_SEO_BOXES -->', '', 1)

    # ── Inject type_links + city_links as block before footer ─────────────────
    rows = []
    if type_links:
        type_tags = ''.join(
            f'<a href="{_attr(href)}" class="popular-city-tag">{_esc(label)}</a>'
            for label, href in type_links
        )
        rows.append(
            f'<div class="popular-cities-inner">'
            f'<span class="popular-cities-label">Browse by type:</span>'
            f'<div class="popular-cities-tags">{type_tags}</div>'
            f'</div>'
        )
    if city_links:
        city_tags = ''.join(
            f'<a href="{_attr(href)}" class="popular-city-tag">'
            f'{_esc(f"{cat_label} in {label}" if cat_label else label)}</a>'
            for label, href in city_links
        )
        rows.append(
            f'<div class="popular-cities-inner">'
            f'<span class="popular-cities-label">Also popular:</span>'
            f'<div class="popular-cities-tags">{city_tags}</div>'
            f'</div>'
        )
    if rows:
        popular_block = (
            f'<div class="popular-cities-block">'
            f'<div class="container">'
            + ''.join(rows) +
            f'</div>'
            f'</div>'
        )
        html = html.replace('<!-- POPULAR_CITIES_BLOCK -->', popular_block, 1)
    else:
        html = html.replace('<!-- POPULAR_CITIES_BLOCK -->', '', 1)

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
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Accept')
        self.end_headers()

    def _proxy_to_laravel(self, method, path, qs, body_data=None):
        if not path.startswith('/api/'):
            self.send_response(404)
            self.end_headers()
            return
        api_path = path[4:]
        qs_str   = ('?' + qs) if qs else ''
        url      = f'{LARAVEL_API_BASE}{api_path}{qs_str}'
        try:
            fwd_headers = {k: v for k, v in {
                'Accept':       self.headers.get('Accept', 'application/json'),
                'Content-Type': self.headers.get('Content-Type', ''),
            }.items() if v}
            req = urllib.request.Request(url, data=body_data, headers=fwd_headers, method=method)
            with urllib.request.urlopen(req, timeout=10) as resp:
                body         = resp.read()
                status       = resp.status
                content_type = resp.headers.get('Content-Type', 'application/json')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            self._send_json(502, {'error': 'api unavailable'})

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        self._proxy_to_laravel('DELETE', parsed.path, parsed.query)

    def do_PATCH(self):
        parsed   = urllib.parse.urlparse(self.path)
        clen     = int(self.headers.get('Content-Length', 0))
        body_data = self.rfile.read(clen) if clen > 0 else None
        self._proxy_to_laravel('PATCH', parsed.path, parsed.query, body_data)

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

        # ── /api/boost-complete ───────────────────────────────────────────────
        if self.path == '/api/boost-complete':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json(400, {'error': 'bad json'}); return

            session_id   = data.get('session_id', '')
            firebase_uid = data.get('firebase_uid', '')

            if not session_id:
                self._send_json(400, {'error': 'missing session_id'}); return

            # Forward to Laravel which handles Stripe verification,
            # property boost marking, and payment record creation
            try:
                pay_payload = json.dumps({'session_id': session_id, 'firebase_uid': firebase_uid}).encode()
                pay_req = urllib.request.Request(
                    f'{LARAVEL_API_BASE}/boost-complete',
                    data=pay_payload,
                    headers={
                        'Content-Type':     'application/json',
                        'Accept':           'application/json',
                        'X-Bazar-Internal': 'moderation',
                    },
                    method='POST',
                )
                with urllib.request.urlopen(pay_req, timeout=15) as pay_resp:
                    result_body = pay_resp.read().decode('utf-8')
                    result = json.loads(result_body)
                    listing_id = result.get('listing_id', '')
                    print(f'[BOOST] boost-complete ok listing={listing_id}', flush=True)
                    self._send_json(200, result)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8') if e.fp else ''
                print(f'[BOOST] boost-complete Laravel error {e.code}: {err_body}', flush=True)
                self._send_json(e.code, json.loads(err_body) if err_body else {'error': 'upstream error'})
            except Exception as e:
                print(f'[BOOST] boost-complete error: {e}', flush=True)
                self._send_json(500, {'error': str(e)})
            return

        # ── /api/chat/ensure ──────────────────────────────────────────────────
        if self.path == '/api/chat/ensure':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json(400, {'error': 'bad json'}); return
            cid = data.get('conv_id', '')
            if not cid:
                self._send_json(400, {'error': 'missing conv_id'}); return
            with _chat_lock:
                conn = _chat_db()
                row = conn.execute('SELECT id FROM conversations WHERE id=?', (cid,)).fetchone()
                if not row:
                    conn.execute('''INSERT INTO conversations
                        (id,ad_id,ad_title,ad_url,ad_photo,ad_price,seller_name,buyer_id,buyer_name,last_time)
                        VALUES (?,?,?,?,?,?,?,?,?,?)''', (
                        cid,
                        data.get('ad_id',''), data.get('ad_title',''), data.get('ad_url',''),
                        data.get('ad_photo',''), data.get('ad_price',''), data.get('seller_name',''),
                        data.get('buyer_id',''), data.get('buyer_name',''), time.time()
                    ))
                else:
                    new_seller = data.get('seller_name', '')
                    if new_seller:
                        conn.execute('UPDATE conversations SET seller_name=? WHERE id=?', (new_seller, cid))
                    new_photo = data.get('ad_photo', '')
                    if new_photo and 'product.jpg' not in new_photo and 'dev.bazar' not in new_photo:
                        conn.execute(
                            "UPDATE conversations SET ad_photo=? WHERE id=? AND (ad_photo='' OR ad_photo IS NULL OR ad_photo LIKE '%product.jpg%' OR ad_photo LIKE '%dev.bazar%')",
                            (new_photo, cid)
                        )
                conn.commit()
                conn.close()
            self._send_json(200, {'ok': True, 'conv_id': cid}); return

        # ── /api/chat/update-photo ────────────────────────────────────────────
        if self.path == '/api/chat/update-photo':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json(400, {'error': 'bad json'}); return
            cid   = data.get('conv_id', '')
            photo = data.get('photo', '')
            if not cid or not photo:
                self._send_json(400, {'error': 'missing fields'}); return
            with _chat_lock:
                conn = _chat_db()
                conn.execute(
                    "UPDATE conversations SET ad_photo=? WHERE id=? AND (ad_photo='' OR ad_photo IS NULL OR ad_photo LIKE '%product.jpg%')",
                    (photo, cid)
                )
                conn.commit()
                conn.close()
            self._send_json(200, {'ok': True}); return

        # ── /api/chat/send ────────────────────────────────────────────────────
        if self.path == '/api/chat/send':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json(400, {'error': 'bad json'}); return
            cid      = data.get('conv_id', '')
            sender   = data.get('sender_id', '')
            sname    = data.get('sender_name', '')
            text     = data.get('text', '').strip()
            mtype    = data.get('type', 'text')
            if not cid or not text:
                self._send_json(400, {'error': 'missing fields'}); return
            now = time.time()
            with _chat_lock:
                conn = _chat_db()
                cur = conn.execute('''INSERT INTO messages (conv_id,sender_id,sender_name,text,time,type)
                                      VALUES (?,?,?,?,?,?)''', (cid, sender, sname, text, now, mtype))
                msg_id = cur.lastrowid
                conv = conn.execute('SELECT buyer_id,unread_seller,unread_buyer FROM conversations WHERE id=?', (cid,)).fetchone()
                if conv:
                    is_buyer = conv['buyer_id'] == sender
                    if is_buyer:
                        conn.execute('UPDATE conversations SET last_msg=?,last_time=?,unread_seller=unread_seller+1 WHERE id=?',
                                     (text, now, cid))
                    else:
                        conn.execute('UPDATE conversations SET last_msg=?,last_time=?,unread_buyer=unread_buyer+1 WHERE id=?',
                                     (text, now, cid))
                conn.commit()
                conn.close()
            self._send_json(200, {'ok': True, 'id': msg_id}); return

        # ── /api/chat/clear-uid — wipe all chat history for a Firebase UID ──
        if self.path == '/api/chat/clear-uid':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json(400, {'error': 'bad json'}); return
            uid = data.get('firebase_uid', '').strip()
            if not uid:
                self._send_json(400, {'error': 'missing firebase_uid'}); return
            with _chat_lock:
                conn = _chat_db()
                # Delete all messages in conversations where this user is buyer
                conv_ids = [r[0] for r in conn.execute(
                    'SELECT id FROM conversations WHERE buyer_id=?', (uid,)
                ).fetchall()]
                if conv_ids:
                    conn.execute(
                        'DELETE FROM messages WHERE conv_id IN (%s)' % ','.join('?' * len(conv_ids)),
                        conv_ids
                    )
                conn.execute('DELETE FROM conversations WHERE buyer_id=?', (uid,))
                conn.commit()
                conn.close()
            self._send_json(200, {'ok': True, 'cleared': len(conv_ids)}); return

        # ── /api/chat/read ────────────────────────────────────────────────────
        if self.path == '/api/chat/read':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json(400, {'error': 'bad json'}); return
            cid  = data.get('conv_id', '')
            role = data.get('role', '')
            if cid and role in ('buyer', 'seller'):
                field = 'unread_buyer' if role == 'buyer' else 'unread_seller'
                with _chat_lock:
                    conn = _chat_db()
                    conn.execute(f'UPDATE conversations SET {field}=0 WHERE id=?', (cid,))
                    conn.commit()
                    conn.close()
            self._send_json(200, {'ok': True}); return

        # ── /api/moderation/approve ───────────────────────────────────────────
        path_only0 = self.path.split('?')[0]
        if path_only0 == '/api/moderation/approve':
            client_ip = self.client_address[0]
            if client_ip not in ('127.0.0.1', '::1'):
                self._send_json(403, {'error': 'forbidden'}); return
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json(400, {'error': 'bad json'}); return
            review_id = data.get('id')
            if not review_id:
                self._send_json(400, {'error': 'id required'}); return
            with _chat_lock:
                conn = sqlite3.connect(MOD_DB, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                row = conn.execute('SELECT property_id FROM moderation_reviews WHERE id=?', (review_id,)).fetchone()
                if row and row['property_id']:
                    _set_property_status_internal(int(row['property_id']), 'active')
                conn.execute('UPDATE moderation_reviews SET status=?, reviewed_at=? WHERE id=?',
                             ('approved', time.time(), review_id))
                conn.commit()
                conn.close()
            self._send_json(200, {'ok': True}); return

        # ── /api/moderation/reject ────────────────────────────────────────────
        if path_only0 == '/api/moderation/reject':
            client_ip = self.client_address[0]
            if client_ip not in ('127.0.0.1', '::1'):
                self._send_json(403, {'error': 'forbidden'}); return
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json(400, {'error': 'bad json'}); return
            review_id = data.get('id')
            if not review_id:
                self._send_json(400, {'error': 'id required'}); return
            with _chat_lock:
                conn = sqlite3.connect(MOD_DB, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                row = conn.execute('SELECT property_id FROM moderation_reviews WHERE id=?', (review_id,)).fetchone()
                if row and row['property_id']:
                    _set_property_status_internal(int(row['property_id']), 'rejected')
                conn.execute('UPDATE moderation_reviews SET status=?, reviewed_at=? WHERE id=?',
                             ('rejected', time.time(), review_id))
                conn.commit()
                conn.close()
            self._send_json(200, {'ok': True}); return

        # ── /api/moderation/remove-by-property — browser-callable, auth by uid ──
        if path_only0 == '/api/moderation/remove-by-property':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json(400, {'error': 'bad json'}); return
            prop_id = data.get('property_id')
            firebase_uid = data.get('firebase_uid', '')
            if not prop_id:
                self._send_json(400, {'error': 'property_id required'}); return
            with _chat_lock:
                conn = sqlite3.connect(MOD_DB, check_same_thread=False)
                if firebase_uid:
                    conn.execute('DELETE FROM moderation_reviews WHERE property_id=? AND firebase_uid=?',
                                 (prop_id, firebase_uid))
                else:
                    conn.execute('DELETE FROM moderation_reviews WHERE property_id=?', (prop_id,))
                conn.commit()
                conn.close()
            self._send_json(200, {'ok': True}); return

        # ── /api/moderation/delete — admin deletes listing from queue + Laravel ──
        if path_only0 == '/api/moderation/delete':
            client_ip = self.client_address[0]
            if client_ip not in ('127.0.0.1', '::1'):
                self._send_json(403, {'error': 'forbidden'}); return
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json(400, {'error': 'bad json'}); return
            review_id = data.get('id')
            if not review_id:
                self._send_json(400, {'error': 'id required'}); return
            with _chat_lock:
                conn = sqlite3.connect(MOD_DB, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                row = conn.execute('SELECT property_id FROM moderation_reviews WHERE id=?', (review_id,)).fetchone()
                if row and row['property_id']:
                    _set_property_status_internal(int(row['property_id']), 'deleted')
                conn.execute('DELETE FROM moderation_reviews WHERE id=?', (review_id,))
                conn.commit()
                conn.close()
            self._send_json(200, {'ok': True}); return

        # ── /api/comments ─────────────────────────────────────────────────────
        if path_only0 == '/api/comments':
            # GET /api/comments?property_id=X
            if self.command == 'GET':
                prop_id = qs.get('property_id', [''])[0].strip()
                if not prop_id:
                    self._send_json(400, {'error': 'property_id required'}); return
                with _chat_lock:
                    conn = _chat_db()
                    rows = conn.execute(
                        'SELECT id, username, text, created_at FROM property_comments '
                        'WHERE property_id=? ORDER BY id ASC', (prop_id,)
                    ).fetchall()
                    conn.close()
                result = [{'id': r['id'], 'username': r['username'],
                           'text': r['text'], 'created_at': r['created_at']} for r in rows]
                self._send_json(200, {'comments': result}); return
            # POST /api/comments
            if self.command == 'POST':
                length = int(self.headers.get('Content-Length', 0))
                body   = self.rfile.read(length)
                try:
                    data = json.loads(body) if body else {}
                except Exception:
                    data = {}
                prop_id  = str(data.get('property_id', '')).strip()
                text     = str(data.get('text', '')).strip()
                username = str(data.get('username', 'Anonymous')).strip()[:80] or 'Anonymous'
                uid      = str(data.get('uid', '')).strip()[:128]
                if not prop_id or not text:
                    self._send_json(400, {'error': 'property_id and text required'}); return
                if len(text) > 2000:
                    self._send_json(400, {'error': 'Comment too long'}); return
                # ── AI moderation ──
                _cm_result = _gemini_moderate_comment(text)
                if _cm_result.get('flagged'):
                    _cm_reasons = _cm_result.get('reasons', [])
                    self._send_json(200, {
                        'ok': False,
                        'flagged': True,
                        'reason': ', '.join(_cm_reasons) or 'inappropriate content',
                    }); return
                now = time.time()
                with _chat_lock:
                    conn = _chat_db()
                    conn.execute(
                        'INSERT INTO property_comments (property_id, uid, username, text, created_at) '
                        'VALUES (?,?,?,?,?)', (prop_id, uid, username, text, now)
                    )
                    conn.commit()
                    row_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
                    conn.close()
                self._send_json(200, {'ok': True, 'id': row_id,
                                      'username': username, 'created_at': now}); return

        # ── /api/tickets (create ticket + Gemini AI reply) ───────────────────
        if path_only0 == '/api/tickets':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json(400, {'error': 'bad json'}); return
            subject = data.get('subject', '').strip()
            message = data.get('message', '').strip()
            if not subject or not message:
                self._send_json(422, {'error': 'subject and message required'}); return
            # 1. Create ticket in Laravel
            try:
                create_req = urllib.request.Request(
                    f'{LARAVEL_API_BASE}/tickets',
                    data=json.dumps(data).encode(),
                    headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                    method='POST',
                )
                with urllib.request.urlopen(create_req, timeout=10) as r:
                    ticket_resp = json.loads(r.read())
            except Exception as e:
                self._send_json(500, {'error': 'failed to create ticket', 'detail': str(e)}); return
            ticket = ticket_resp.get('ticket', {})
            ticket_id = ticket.get('id')
            if not ticket_id:
                self._send_json(500, {'error': 'no ticket id returned'}); return
            # 2. Call Gemini AI
            ai_text, needs_human = _gemini_reply(subject, message)
            new_status = 'need_human' if needs_human or not ai_text else 'ai_answered'
            # 3. Save AI reply (or mark need_human) in Laravel
            try:
                status_payload = {
                    'status': new_status,
                    'ai_confidence': 'low' if needs_human else 'high',
                }
                if ai_text:
                    status_payload['ai_message'] = ai_text
                status_req = urllib.request.Request(
                    f'{LARAVEL_API_BASE}/tickets/{ticket_id}/status',
                    data=json.dumps(status_payload).encode(),
                    headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                    method='POST',
                )
                with urllib.request.urlopen(status_req, timeout=10) as r:
                    updated = json.loads(r.read())
                ticket = updated.get('ticket', ticket)
            except Exception:
                pass
            self._send_json(201, {'ok': True, 'ticket': ticket}); return

        # ── /api/ticket-upload — upload & compress image for ticket messages ────
        if path_only0 == '/api/ticket-upload':
            content_len  = int(self.headers.get('Content-Length', 0))
            body_bytes   = self.rfile.read(content_len) if content_len > 0 else b''
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self._send_json(400, {'error': 'multipart/form-data required'}); return
            _, image_bytes_list = _parse_multipart(body_bytes, content_type)
            if not image_bytes_list:
                self._send_json(400, {'error': 'no file uploaded'}); return
            raw_bytes = image_bytes_list[0]
            try:
                from PIL import Image as _PILImage
                img = _PILImage.open(io.BytesIO(raw_bytes))
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                max_dim = 1200
                if max(img.size) > max_dim:
                    ratio = max_dim / max(img.size)
                    img = img.resize(
                        (int(img.size[0] * ratio), int(img.size[1] * ratio)),
                        _PILImage.LANCZOS
                    )
                out = io.BytesIO()
                img.save(out, format='JPEG', quality=85, optimize=True)
                compressed = out.getvalue()
            except Exception as e:
                self._send_json(500, {'error': f'image error: {e}'}); return
            uploads_dir = os.path.join(SITE_ROOT, 'uploads', 'tickets')
            os.makedirs(uploads_dir, mode=0o777, exist_ok=True)
            try:
                os.chmod(uploads_dir, 0o777)
                os.chmod(os.path.dirname(uploads_dir), 0o777)
            except OSError:
                pass
            filename = uuid.uuid4().hex + '.jpg'
            with open(os.path.join(uploads_dir, filename), 'wb') as fh:
                fh.write(compressed)
            url = f'{PUBLIC_DOMAIN}/uploads/tickets/{filename}'
            self._send_json(200, {'ok': True, 'url': url}); return

        # ── /api/ticket-followup — client sends follow-up, AI auto-replies ──────
        if path_only0 == '/api/ticket-followup':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json(400, {'error': 'bad json'}); return
            ticket_id    = data.get('ticket_id')
            firebase_uid = data.get('firebase_uid', '').strip()
            followup_text = data.get('message', '').strip()
            attachments  = data.get('attachments', [])
            if not isinstance(attachments, list):
                attachments = []
            if not ticket_id or not firebase_uid or (not followup_text and not attachments):
                self._send_json(422, {'error': 'ticket_id, firebase_uid and message or attachments required'}); return
            # 1. Save client message + set status=open in Laravel
            try:
                status_req = urllib.request.Request(
                    f'{LARAVEL_API_BASE}/tickets/{ticket_id}/status',
                    data=json.dumps({
                        'status': 'open',
                        'client_followup': followup_text or '(image)',
                        'firebase_uid': firebase_uid,
                        'attachments': attachments,
                    }).encode(),
                    headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                    method='POST',
                )
                with urllib.request.urlopen(status_req, timeout=10) as r:
                    saved = json.loads(r.read())
            except Exception as e:
                self._send_json(500, {'error': 'failed to save message', 'detail': str(e)}); return
            # 2. Fetch full ticket thread for context
            def _ai_followup_reply(tid, uid):
                ticket_data = _fetch_ticket_with_messages(tid)
                if not ticket_data:
                    return
                ticket_obj = ticket_data.get('ticket', {})
                subject    = ticket_obj.get('subject', '')
                messages   = ticket_obj.get('messages', [])
                if not messages:
                    return
                ai_text, needs_human = _gemini_reply_with_context(subject, messages)
                new_status = 'need_human' if needs_human or not ai_text else 'ai_answered'
                try:
                    payload = {'status': new_status, 'ai_confidence': 'low' if needs_human else 'high'}
                    if ai_text:
                        payload['ai_message'] = ai_text
                    req2 = urllib.request.Request(
                        f'{LARAVEL_API_BASE}/tickets/{tid}/status',
                        data=json.dumps(payload).encode(),
                        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                        method='POST',
                    )
                    urllib.request.urlopen(req2, timeout=10).close()
                except Exception:
                    pass
            threading.Thread(target=_ai_followup_reply, args=(ticket_id, firebase_uid), daemon=True).start()
            self._send_json(200, {'ok': True, 'ticket': saved.get('ticket', {})}); return

        # ── /api/admin/ticket-suggest — IP-restricted AI draft for admin ─────────
        if path_only0 == '/api/admin/ticket-suggest':
            client_ip = self.client_address[0]
            if client_ip not in ('127.0.0.1', '::1'):
                self._send_json(403, {'error': 'forbidden'}); return
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json(400, {'error': 'bad json'}); return
            ticket_id = data.get('ticket_id')
            if not ticket_id:
                self._send_json(400, {'error': 'ticket_id required'}); return
            ticket_data = _fetch_ticket_with_messages(int(ticket_id))
            if not ticket_data:
                self._send_json(404, {'error': 'ticket not found'}); return
            ticket_obj = ticket_data.get('ticket', {})
            subject    = ticket_obj.get('subject', '')
            messages   = ticket_obj.get('messages', [])
            ai_text, needs_human = _gemini_reply_with_context(subject, messages)
            self._send_json(200, {'suggestion': ai_text, 'needs_human': needs_human}); return

        # ── /api/properties (POST) — async AI moderation ────────────────────────
        # Flow: parse → forward to Laravel as pending → reply to client fast →
        #       background thread runs Gemini+Vision → if clean set active,
        #       if flagged stays pending and logged to moderation_reviews.
        path_only = self.path.split('?')[0]
        if path_only == '/api/properties':
            content_len  = int(self.headers.get('Content-Length', 0))
            body_bytes   = self.rfile.read(content_len) if content_len > 0 else b''
            content_type = self.headers.get('Content-Type', '')

            # Parse body: multipart/form-data (real uploads) or JSON (API)
            title            = ''
            description      = ''
            firebase_uid     = ''
            image_bytes_list = []
            image_urls       = []

            if 'multipart/form-data' in content_type:
                fields, image_bytes_list = _parse_multipart(body_bytes, content_type)
                title        = fields.get('title', '') or ''
                description  = fields.get('description', '') or ''
                firebase_uid = fields.get('firebase_uid', '') or ''
                print(f'[MODERATION] Multipart parsed: title={repr(title[:40])} '
                      f'images={len(image_bytes_list)} fields={list(fields.keys())}', flush=True)
            else:
                try:
                    body_data = json.loads(body_bytes) if body_bytes else {}
                except Exception:
                    body_data = {}
                title        = str(body_data.get('title', '') or '')
                description  = str(body_data.get('description', '') or body_data.get('body', '') or '')
                firebase_uid = str(body_data.get('firebase_uid', '') or '')
                raw_images   = (body_data.get('images') or body_data.get('photos') or
                                body_data.get('media') or [])
                if isinstance(raw_images, str):
                    try:
                        raw_images = json.loads(raw_images)
                    except Exception:
                        raw_images = [raw_images] if raw_images else []
                image_urls = [str(u) for u in (raw_images or []) if u]

            # Step 1: Forward to Laravel immediately, ALWAYS as pending.
            # The background moderation will set it to active if clean.
            fwd_url = f'{LARAVEL_API_BASE}/properties'
            qs_str  = ('?' + self.path[len(path_only)+1:]) if '?' in self.path else ''
            fwd_url += qs_str
            fwd_headers = {
                'Accept':              self.headers.get('Accept', 'application/json'),
                'Content-Type':        content_type or 'application/json',
                'X-Bazar-Moderation':  'pending',
            }
            fwd_headers = {k: v for k, v in fwd_headers.items() if v}
            try:
                req = urllib.request.Request(fwd_url, data=body_bytes, headers=fwd_headers, method='POST')
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_body   = resp.read()
                    resp_status = resp.status
                    resp_ct     = resp.headers.get('Content-Type', 'application/json')

                # Step 2: Extract prop_id for async moderation
                prop_id = 0
                try:
                    prop    = json.loads(resp_body)
                    prop_id = (prop.get('id') or prop.get('property_id') or
                               (prop.get('data') or {}).get('id') or 0)
                except Exception:
                    pass

                # Step 3: Reply to client right away (well within Nginx timeout)
                self.send_response(resp_status)
                self.send_header('Content-Type', resp_ct)
                self.send_header('Content-Length', str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)

                # Step 4: Run AI moderation in background thread (fire and forget)
                if prop_id:
                    _pid   = int(prop_id)
                    _title = title
                    _desc  = description
                    _uid   = firebase_uid
                    _imgs  = list(image_bytes_list)
                    _urls  = list(image_urls)

                    def _moderate_async():
                        try:
                            print(f'[MODERATION] Starting async check for property {_pid}', flush=True)
                            txt_r = {}
                            img_r = {}

                            def _rt():
                                nonlocal txt_r
                                txt_r = _gemini_moderate(_title, _desc)

                            def _rv():
                                nonlocal img_r
                                if _imgs:
                                    img_r = _vision_safesearch_bytes(_imgs)
                                elif _urls:
                                    img_r = _vision_safesearch(_urls)

                            t1 = threading.Thread(target=_rt, daemon=True)
                            t2 = threading.Thread(target=_rv, daemon=True)
                            t1.start(); t2.start()
                            t1.join(timeout=30); t2.join(timeout=30)

                            txt_flagged = bool(txt_r.get('flagged', False))
                            img_flagged = bool(img_r.get('flagged', False))
                            flagged     = txt_flagged or img_flagged

                            if not flagged:
                                # Clean → promote to active
                                _set_property_status_internal(_pid, 'active')
                                print(f'[MODERATION] Property {_pid} CLEAN → set active', flush=True)
                            else:
                                # Flagged → force pending (in case it was created as active), log to DB
                                _set_property_status_internal(_pid, 'pending')
                                all_reasons = list(txt_r.get('reasons', []))
                                if img_flagged:
                                    all_reasons += img_r.get('reasons', [])
                                all_conf = max(
                                    txt_r.get('confidence', 0.0),
                                    img_r.get('confidence', 0.0),
                                )
                                print(
                                    f'[MODERATION] Property {_pid} FLAGGED → forced pending, '
                                    f'reasons={all_reasons}',
                                    flush=True,
                                )
                                with _chat_lock:
                                    conn = sqlite3.connect(MOD_DB, check_same_thread=False)
                                    conn.execute(
                                        '''INSERT INTO moderation_reviews
                                           (property_id, title, description, firebase_uid,
                                            ai_text_flagged, ai_reasons, ai_confidence,
                                            ai_image_flagged, ai_image_reasons,
                                            status, created_at)
                                           VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                                        (_pid, _title[:500], _desc[:2000], _uid,
                                         1 if txt_flagged else 0,
                                         json.dumps(all_reasons),
                                         all_conf,
                                         1 if img_flagged else 0,
                                         json.dumps(img_r.get('reasons', [])),
                                         'pending', time.time())
                                    )
                                    conn.commit()
                                    conn.close()
                        except Exception as exc:
                            print(f'[MODERATION] Async error for property {_pid}: {exc}', flush=True)

                    threading.Thread(target=_moderate_async, daemon=True).start()

            except urllib.error.HTTPError as e:
                b = e.read()
                self.send_response(e.code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(b)))
                self.end_headers()
                self.wfile.write(b)
            except Exception:
                self._send_json(502, {'error': 'gateway error'})
            return

        # ── /api/properties/{id}/delete — forward to Laravel + clean mod queue ──
        _del_m = re.match(r'^/api/properties/(\d+)/delete$', path_only)
        if _del_m:
            prop_id_del = int(_del_m.group(1))
            content_len = int(self.headers.get('Content-Length', 0))
            body_del    = self.rfile.read(content_len) if content_len > 0 else b''
            fwd_headers = {
                'Accept':       self.headers.get('Accept', 'application/json'),
                'Content-Type': self.headers.get('Content-Type', 'application/json'),
            }
            try:
                req = urllib.request.Request(
                    f'{LARAVEL_API_BASE}/properties/{prop_id_del}/delete',
                    data=body_del, headers=fwd_headers, method='POST')
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp_body = resp.read()
                    resp_status = resp.status
                    resp_ct = resp.headers.get('Content-Type', 'application/json')
                # Clean moderation queue on success
                if resp_status == 200:
                    with _chat_lock:
                        conn = sqlite3.connect(MOD_DB, check_same_thread=False)
                        conn.execute('DELETE FROM moderation_reviews WHERE property_id=?', (prop_id_del,))
                        conn.commit()
                        conn.close()
                self.send_response(resp_status)
                self.send_header('Content-Type', resp_ct)
                self.send_header('Content-Length', str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
            except urllib.error.HTTPError as e:
                b = e.read()
                self.send_response(e.code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(b)))
                self.end_headers()
                self.wfile.write(b)
            except Exception:
                self._send_json(502, {'error': 'gateway error'})
            return

        # ── /api/save-gender — persist gender in our SQLite (authoritative) ──
        if path_only == '/api/save-gender':
            _sg_cl = int(self.headers.get('Content-Length', 0))
            _sg_body = self.rfile.read(_sg_cl) if _sg_cl > 0 else b''
            try:
                _sg_data = json.loads(_sg_body) if _sg_body else {}
                _sg_uid    = _sg_data.get('uid', '').strip()
                _sg_gender = _sg_data.get('gender', '').strip().lower()
                if _sg_uid and _sg_gender in ('male', 'female'):
                    with _chat_lock:
                        _sg_conn = _chat_db()
                        _sg_conn.execute(
                            'INSERT OR REPLACE INTO customer_profiles (uid, gender, updated_at) VALUES (?,?,?)',
                            (_sg_uid, _sg_gender, time.time()))
                        _sg_conn.commit(); _sg_conn.close()
                    self._send_json(200, {'ok': True})
                else:
                    self._send_json(400, {'error': 'missing uid or invalid gender'})
            except Exception as e:
                self._send_json(500, {'error': str(e)})
            return

        # ── /api/moderate-avatar — SafeSearch check for profile avatar uploads ──
        if path_only == '/api/moderate-avatar':
            _ma_cl = int(self.headers.get('Content-Length', 0))
            _ma_body = self.rfile.read(_ma_cl) if _ma_cl > 0 else b''
            try:
                _ma_data = json.loads(_ma_body) if _ma_body else {}
                _ma_img  = _ma_data.get('image', '')  # data:image/...;base64,...
                if not _ma_img:
                    self._send_json(400, {'ok': False, 'error': 'no image'})
                    return
                # Strip data URL prefix → raw bytes
                if ',' in _ma_img:
                    _ma_b64 = _ma_img.split(',', 1)[1]
                else:
                    _ma_b64 = _ma_img
                try:
                    _ma_bytes = base64.b64decode(_ma_b64)
                except Exception:
                    self._send_json(400, {'ok': False, 'error': 'invalid base64'})
                    return
                _ma_result = _vision_safesearch_bytes([_ma_bytes])
                if _ma_result.get('flagged'):
                    _ma_reasons = _ma_result.get('reasons', [])
                    print(f'[AVATAR-MOD] BLOCKED — {_ma_reasons}', flush=True)
                    self._send_json(200, {
                        'ok': False,
                        'flagged': True,
                        'reason': ', '.join(_ma_reasons) or 'inappropriate content',
                    })
                else:
                    self._send_json(200, {'ok': True, 'flagged': False})
            except Exception as e:
                print(f'[AVATAR-MOD] error: {e}', flush=True)
                # On error — allow the upload (fail open, don't block users on API outage)
                self._send_json(200, {'ok': True, 'flagged': False})
            return

        # ── /api/validate-youtube — oEmbed existence check + Gemini content moderation ──
        if path_only == '/api/validate-youtube':
            _vy_cl   = int(self.headers.get('Content-Length', 0))
            _vy_body = self.rfile.read(_vy_cl) if _vy_cl > 0 else b''
            try:
                _vy_data = json.loads(_vy_body) if _vy_body else {}
                _vy_url  = (_vy_data.get('url') or '').strip()
                if not _vy_url:
                    self._send_json(200, {'ok': True}); return
                # Extract video ID (watch, shorts, youtu.be)
                _vy_m = re.search(
                    r'(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})',
                    _vy_url)
                if not _vy_m:
                    self._send_json(200, {'ok': False,
                        'reason': 'Invalid YouTube URL — please use a youtube.com/watch or youtu.be link'})
                    return
                _vy_vid = _vy_m.group(1)
                # oEmbed — fails for private / deleted / age-restricted videos
                _vy_oembed = (f'https://www.youtube.com/oembed'
                              f'?url=https://www.youtube.com/watch?v={_vy_vid}&format=json')
                try:
                    _vy_req = urllib.request.Request(
                        _vy_oembed, headers={'User-Agent': 'Mozilla/5.0 BazarBot/1.0'})
                    with urllib.request.urlopen(_vy_req, timeout=8) as _vy_r:
                        _vy_meta = json.loads(_vy_r.read())
                    _vy_title  = _vy_meta.get('title', '')
                    _vy_author = _vy_meta.get('author_name', '')
                except Exception:
                    self._send_json(200, {'ok': False,
                        'reason': 'This video is unavailable, private, or age-restricted '
                                  'and cannot be added to your listing'})
                    return
                # Gemini content classification
                _vy_result = _gemini_moderate_youtube(_vy_title, _vy_author)
                self._send_json(200, _vy_result)
            except Exception as _vy_e:
                print(f'[YT-MOD] endpoint error: {_vy_e}', flush=True)
                self._send_json(200, {'ok': True})  # fail open — never block on API outage
            return

        # Generic POST proxy → forward any unhandled /api/* POST to LARAVEL_API_BASE
        if path_only.startswith('/api/'):
            api_path = path_only[len('/api'):]
            # ── Intercept activate-plan to track per-listing plans locally ──
            _apm = re.match(r'^/properties/(\d+)/activate-plan$', api_path)
            if _apm:
                _ap_ad_id = _apm.group(1)
                try:
                    _ap_cl = int(self.headers.get('Content-Length', 0))
                    _ap_body = self.rfile.read(_ap_cl) if _ap_cl > 0 else b''
                    _ap_json = json.loads(_ap_body) if _ap_body else {}
                    _ap_plan = _ap_json.get('plan', '')
                    _ap_dur  = int(_ap_json.get('duration_days', 30))
                    if _ap_plan and _ap_ad_id:
                        with _chat_lock:
                            _apc = sqlite3.connect(CHAT_DB)
                            _apc.row_factory = sqlite3.Row
                            # If existing plan is still active AND same plan type, extend
                            # from its expires_at so remaining days are preserved.
                            # If switching to a DIFFERENT plan (e.g. PRO→VIP), start fresh
                            # from now — do NOT carry over remaining days from the old plan.
                            _ap_existing = _apc.execute(
                                'SELECT plan, expires_at FROM listing_plans WHERE ad_id=?',
                                (_ap_ad_id,)).fetchone()
                            _ap_base = time.time()
                            if _ap_existing:
                                _ap_existing_plan = _ap_existing['plan']
                                _ap_existing_exp  = float(_ap_existing['expires_at'])
                                if _ap_existing_exp > _ap_base and _ap_existing_plan == _ap_plan:
                                    _ap_base = _ap_existing_exp  # same plan — extend
                            _ap_exp = _ap_base + _ap_dur * 86400
                            _apc.execute(
                                'INSERT OR REPLACE INTO listing_plans '
                                '(ad_id, plan, activated_at, duration_days, expires_at) '
                                'VALUES (?,?,?,?,?)',
                                (_ap_ad_id, _ap_plan, time.time(), _ap_dur, _ap_exp))
                            _apc.commit(); _apc.close()
                except Exception:
                    pass
                # Forward the original body to Laravel
                try:
                    _fwd_url = f'{LARAVEL_API_BASE}{api_path}'
                    _fwd_h = {
                        'Accept':       self.headers.get('Accept', 'application/json'),
                        'Content-Type': self.headers.get('Content-Type', 'application/json'),
                    }
                    _fwd_req = urllib.request.Request(_fwd_url, data=_ap_body, headers=_fwd_h, method='POST')
                    with urllib.request.urlopen(_fwd_req, timeout=5) as _fwd_r:
                        _fwd_body = _fwd_r.read()
                        _fwd_status = _fwd_r.status
                        _fwd_ct = _fwd_r.headers.get('Content-Type', 'application/json')
                    self.send_response(_fwd_status)
                    self.send_header('Content-Type', _fwd_ct)
                    self.send_header('Content-Length', str(len(_fwd_body)))
                    self.end_headers()
                    self.wfile.write(_fwd_body)
                except urllib.error.HTTPError as e:
                    _eb = e.read()
                    self.send_response(e.code)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(_eb)))
                    self.end_headers()
                    self.wfile.write(_eb)
                except Exception:
                    self._send_json(502, {'error': 'api unavailable'})
                return
            qs       = self.path[len(path_only)+1:] if '?' in self.path else ''
            qs_str   = ('?' + qs) if qs else ''
            url      = f'{LARAVEL_API_BASE}{api_path}{qs_str}'
            try:
                content_len = int(self.headers.get('Content-Length', 0))
                body_data   = self.rfile.read(content_len) if content_len > 0 else None
                fwd_headers = {
                    'Accept':       self.headers.get('Accept', 'application/json'),
                    'Content-Type': self.headers.get('Content-Type', 'application/json'),
                }
                fwd_headers = {k: v for k, v in fwd_headers.items() if v}
                req = urllib.request.Request(url, data=body_data, headers=fwd_headers, method='POST')
                with urllib.request.urlopen(req, timeout=5) as resp:
                    body         = resp.read()
                    status       = resp.status
                    content_type = resp.headers.get('Content-Type', 'application/json')
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except urllib.error.HTTPError as e:
                body = e.read()
                self.send_response(e.code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self._send_json(502, {'error': 'api unavailable'})
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

        # bare bazar.uk (no www) → 301 to www.bazar.uk so Firebase auth works
        if host in ('bazar.uk', 'bazar.uk:80', 'bazar.uk:443'):
            dest = 'https://www.bazar.uk' + path
            if qs:
                dest += '?' + qs
            self.send_response(301)
            self.send_header('Location', dest)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return

        # /admin/* → redirect to admin.bazar.uk (strip /admin prefix)
        if path == '/admin' or path.startswith('/admin/'):
            sub = path[len('/admin'):]  # '' or '/login' or '/users/...'
            dest = 'https://admin.bazar.uk' + (sub if sub else '/')
            if qs:
                dest += '?' + qs
            self.send_response(301)
            self.send_header('Location', dest)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return

        # API: config
        if path == '/api/config':
            self._send_json(200, {'googleMapsApiKey': GOOGLE_MAPS_API_KEY})
            return

        # ── GET /api/is-admin — always true in dev/Replit ────────────────────────
        if path == '/api/is-admin':
            self._send_json(200, {'admin': True})
            return

        # ── GET /api/properties/<id>/views — view count from MySQL ──────────────
        _pv_m = re.match(r'^/api/properties/(\d+)/views$', path)
        if _pv_m:
            _pv_id = int(_pv_m.group(1))
            try:
                import pymysql
                _pv_conn = pymysql.connect(
                    host=os.environ.get('DB_HOST', '127.0.0.1'),
                    user=os.environ.get('DB_USERNAME', 'bazar'),
                    password=os.environ.get('DB_PASSWORD', 'BazarSecure2026'),
                    database=os.environ.get('DB_DATABASE', 'bazar_dev'),
                    connect_timeout=3,
                    cursorclass=pymysql.cursors.DictCursor,
                )
                with _pv_conn:
                    with _pv_conn.cursor() as _pv_cur:
                        _pv_cur.execute(
                            'SELECT COUNT(*) AS cnt FROM property_views WHERE property_id=%s',
                            (_pv_id,)
                        )
                        _pv_row = _pv_cur.fetchone()
                        _pv_count = int(_pv_row['cnt']) if _pv_row else 0
                self._send_json(200, {'views': _pv_count})
            except Exception:
                self._send_json(200, {'views': 0})
            return

        # ── /api/ad-plan/<adId> — return current plan for a specific ad ────────
        _apm_get = re.match(r'^/api/ad-plan/(\d+)$', path)
        if _apm_get:
            _ap_id = _apm_get.group(1)
            try:
                with _chat_lock:
                    _apc = _chat_db()
                    _apr = _apc.execute(
                        'SELECT plan, expires_at FROM listing_plans WHERE ad_id=?',
                        (_ap_id,)).fetchone()
                    _apc.close()
                _now = time.time()
                if _apr and float(_apr['expires_at']) > _now:
                    _plan = _apr['plan']
                else:
                    _plan = 'free'
                self._send_json(200, {'plan': _plan, 'ad_id': _ap_id})
            except Exception as _e:
                self._send_json(200, {'plan': 'free', 'ad_id': _ap_id})
            return

        # ── /api/stats ────────────────────────────────────────────────────────
        if path == '/api/stats':
            # Short 30-second cache so count updates quickly after add/delete
            with _cache_lock:
                entry = _cache.get('stats_total')
                if entry and time.time() - entry['ts'] < 30:
                    self._send_json(200, entry['data']); return
            # Fetch max listing ID from sitemap-listings as approximate total
            listings = _api_get('/sitemap-listings', None)
            total = 0
            if listings and isinstance(listings, list):
                ids = [item.get('id', 0) for item in listings if isinstance(item, dict) and item.get('id')]
                if ids:
                    max_id = max(ids)
                    # Probe upward from max_id to find real maximum
                    probe = max_id
                    for step in (500, 100, 50, 10, 1):
                        while True:
                            candidate = probe + step
                            try:
                                req = urllib.request.Request(
                                    f'{LARAVEL_API_BASE}/properties/{candidate}',
                                    headers={'Accept': 'application/json'})
                                with urllib.request.urlopen(req, timeout=2) as r:
                                    d = json.loads(r.read().decode())
                                    if isinstance(d, dict) and d.get('id'):
                                        probe = candidate
                                        continue
                            except Exception:
                                pass
                            break
                    total = probe
            result = {'ads_total': total}
            _cache_set('stats_total', result)
            self._send_json(200, result); return

        # ── /api/moderation/queue ──────────────────────────────────────────────
        if path == '/api/moderation/queue':
            client_ip = self.client_address[0]
            if client_ip not in ('127.0.0.1', '::1'):
                self._send_json(403, {'error': 'forbidden'}); return
            with _chat_lock:
                conn = sqlite3.connect(MOD_DB, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    'SELECT * FROM moderation_reviews ORDER BY created_at DESC LIMIT 200'
                ).fetchall()
                pending = conn.execute(
                    'SELECT COUNT(*) as c FROM moderation_reviews WHERE status=?', ('pending',)
                ).fetchone()['c']
                conn.close()
            items = []
            for r in rows:
                items.append({
                    'id':                r['id'],
                    'property_id':       r['property_id'],
                    'title':             r['title'],
                    'description':       r['description'],
                    'firebase_uid':      r['firebase_uid'],
                    'ai_text_flagged':   bool(r['ai_text_flagged']),
                    'ai_image_flagged':  bool(r['ai_image_flagged'] if 'ai_image_flagged' in r.keys() else 0),
                    'ai_reasons':        json.loads(r['ai_reasons'] or '[]'),
                    'ai_image_reasons':  json.loads(r['ai_image_reasons'] if 'ai_image_reasons' in r.keys() else '[]') if (r['ai_image_reasons'] if 'ai_image_reasons' in r.keys() else None) else [],
                    'ai_confidence':     r['ai_confidence'],
                    'status':            r['status'],
                    'created_at':        r['created_at'],
                    'reviewed_at':       r['reviewed_at'],
                    'days_left':         max(0, 30 - int((time.time() - float(r['created_at'])) / 86400)),
                })
            self._send_json(200, {'items': items, 'pending_count': pending}); return

        # ── /api/comments (GET) ───────────────────────────────────────────────
        if path == '/api/comments':
            params  = urllib.parse.parse_qs(qs)
            prop_id = params.get('property_id', [''])[0].strip()
            if not prop_id:
                self._send_json(400, {'error': 'property_id required'}); return
            with _chat_lock:
                conn = _chat_db()
                rows = conn.execute(
                    'SELECT id, username, text, created_at FROM property_comments '
                    'WHERE property_id=? ORDER BY id ASC', (prop_id,)
                ).fetchall()
                conn.close()
            result = [{'id': r['id'], 'username': r['username'],
                       'text': r['text'], 'created_at': r['created_at']} for r in rows]
            self._send_json(200, {'comments': result}); return

        if path == '/api/chat/msgs':
            params = urllib.parse.parse_qs(qs)
            cid   = params.get('conv_id', [None])[0]
            since = int(params.get('since', ['0'])[0])
            if not cid:
                self._send_json(400, {'error': 'missing conv_id'}); return
            with _chat_lock:
                conn = _chat_db()
                rows = conn.execute(
                    'SELECT id,sender_id,sender_name,text,time,type FROM messages WHERE conv_id=? AND id>? ORDER BY id ASC',
                    (cid, since)
                ).fetchall()
                conn.close()
            msgs = [dict(r) for r in rows]
            self._send_json(200, {'messages': msgs}); return

        # ── /api/chat/convs ───────────────────────────────────────────────────
        if path == '/api/chat/convs':
            params = urllib.parse.parse_qs(qs)
            uid   = params.get('uid',   [None])[0]
            name  = params.get('name',  [None])[0]
            since_raw = params.get('since', [None])[0]
            since = None
            try:
                if since_raw: since = float(since_raw)
            except (ValueError, TypeError):
                pass
            if not uid and not name:
                self._send_json(400, {'error': 'missing uid'}); return
            with _chat_lock:
                conn = _chat_db()
                if uid and name:
                    if since:
                        rows = conn.execute(
                            'SELECT * FROM conversations WHERE (buyer_id=? OR seller_name=?) AND last_time>=? ORDER BY last_time DESC',
                            (uid, name, since)
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            'SELECT * FROM conversations WHERE buyer_id=? OR seller_name=? ORDER BY last_time DESC',
                            (uid, name)
                        ).fetchall()
                elif uid:
                    if since:
                        rows = conn.execute(
                            'SELECT * FROM conversations WHERE buyer_id=? AND last_time>=? ORDER BY last_time DESC',
                            (uid, since)
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            'SELECT * FROM conversations WHERE buyer_id=? ORDER BY last_time DESC', (uid,)
                        ).fetchall()
                else:
                    rows = conn.execute(
                        'SELECT * FROM conversations WHERE seller_name=? ORDER BY last_time DESC', (name,)
                    ).fetchall()
                conn.close()
            convs = [dict(r) for r in rows]
            self._send_json(200, {'conversations': convs}); return

        # API: products (dev fallback)
        # ── /api/properties/recent-enriched — recent list + old_price per item ──
        if path == '/api/properties/recent-enriched':
            qs_forward = ('?' + qs) if qs else ''
            recent = _api_get(f'/properties/recent{qs_forward}')
            if not recent or not isinstance(recent.get('data'), list):
                self._send_json(200, recent or {'data': []})
                return
            # Make independent copies of each ad dict so we never mutate the cache
            enriched_list = [dict(ad) for ad in recent['data']]

            # ── STEP 1: apply per-ad plan overrides FIRST (no lock needed — read-only SQLite) ──
            # ALWAYS reset is_vip/is_pro to False for every ad; only trust our local DB,
            # never trust Laravel's account-level subscription flags.
            _local_plans = {}
            try:
                _lp_c = sqlite3.connect(CHAT_DB, check_same_thread=False)
                _lp_rows = _lp_c.execute(
                    'SELECT ad_id, plan, expires_at FROM listing_plans WHERE expires_at > ?',
                    (time.time(),)).fetchall()
                _lp_c.close()
                _local_plans = {str(r[0]): {'plan': r[1], 'expires_at': r[2]} for r in _lp_rows}
            except Exception:
                pass
            for ad in enriched_list:
                lp = _local_plans.get(str(ad.get('id', '')))
                if lp:
                    ad['is_vip']    = (lp['plan'] == 'vip')
                    ad['is_pro']    = (lp['plan'] == 'pro')
                    # Convert Unix seconds → ISO string so JS new Date() parses correctly
                    import datetime as _dt
                    ad['expires_at'] = _dt.datetime.utcfromtimestamp(lp['expires_at']).strftime('%Y-%m-%dT%H:%M:%S.000000Z')
                else:
                    ad['is_vip']    = False
                    ad['is_pro']    = False
                    # Leave expires_at as-is for free ads

            # ── STEP 2: fetch extra detail fields (old_price, images, district) per ad ──
            # These threads MUST NOT touch is_vip / is_pro.
            lock = threading.Lock()
            def _fetch_old_price(idx, ad_id):
                try:
                    req = urllib.request.Request(
                        f'{LARAVEL_API_BASE}/properties/{ad_id}',
                        headers={'Accept': 'application/json'})
                    with urllib.request.urlopen(req, timeout=4) as r:
                        detail = json.loads(r.read().decode('utf-8'))
                    with lock:
                        enriched_list[idx]['old_price']    = detail.get('old_price')
                        enriched_list[idx]['district']     = detail.get('district') or ''
                        enriched_list[idx]['listing_type'] = detail.get('listing_type') or ''
                        enriched_list[idx]['images']       = detail.get('images') or []
                        enriched_list[idx]['car_make']     = detail.get('car_make') or ''
                        enriched_list[idx]['views']        = detail.get('views_count') or detail.get('views') or 0
                        if detail.get('created_at') and not enriched_list[idx].get('created_at'):
                            enriched_list[idx]['created_at'] = detail.get('created_at')
                    # Refresh per-listing cache so card.html gets fresh data too
                    _cache_set(f'listing_{ad_id}', detail)
                except Exception:
                    pass
            threads = []
            for i, ad in enumerate(enriched_list):
                ad_id = ad.get('id')
                if ad_id:
                    t = threading.Thread(target=_fetch_old_price, args=(i, ad_id))
                    t.daemon = True
                    t.start()
                    threads.append(t)
            for t in threads:
                t.join(timeout=5)

            recent['data'] = enriched_list
            self._send_json(200, recent)
            return

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

        # Generic /api/* proxy → forward to LARAVEL_API_BASE
        # This handles any /api/ path not explicitly handled above
        # (e.g. /api/properties/recent, /api/search/suggest, /api/customers/*, etc.)
        if path.startswith('/api/'):
            api_path = path[len('/api'):]   # keep leading slash
            qs_str   = ('?' + qs) if qs else ''
            url      = f'{LARAVEL_API_BASE}{api_path}{qs_str}'
            try:
                headers = {
                    'Accept':        self.headers.get('Accept', 'application/json'),
                    'Content-Type':  self.headers.get('Content-Type', 'application/json'),
                    'Authorization': self.headers.get('Authorization', ''),
                    'X-Firebase-UID': self.headers.get('X-Firebase-UID', ''),
                }
                headers = {k: v for k, v in headers.items() if v}
                # Read request body for POST/PUT/PATCH
                body_data = None
                if self.command in ('POST', 'PUT', 'PATCH'):
                    content_len = int(self.headers.get('Content-Length', 0))
                    if content_len > 0:
                        body_data = self.rfile.read(content_len)
                req = urllib.request.Request(url, data=body_data, headers=headers, method=self.command)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    body        = resp.read()
                    status      = resp.status
                    content_type = resp.headers.get('Content-Type', 'application/json')
                # ── Override expires_at for /api/properties/{id} from SQLite listing_plans ──
                _prop_m = re.match(r'^/properties/(\d+)$', api_path)
                if _prop_m and 'application/json' in content_type:
                    try:
                        _pd = json.loads(body)
                        if isinstance(_pd, dict):
                            _pid = _prop_m.group(1)
                            with _chat_lock:
                                _lp_conn = _chat_db()
                                _lp_row  = _lp_conn.execute(
                                    'SELECT plan, expires_at FROM listing_plans WHERE ad_id=? AND expires_at > ?',
                                    (_pid, time.time())
                                ).fetchone()
                                _lp_conn.close()
                            if _lp_row:
                                _lp_plan = _lp_row[0]
                                _lp_exp  = float(_lp_row[1])
                                import datetime as _dt
                                _pd['is_pro']    = (_lp_plan == 'pro')
                                _pd['is_vip']    = (_lp_plan == 'vip')
                                # Convert Unix seconds → ISO string so JS new Date() parses correctly
                                _pd['expires_at'] = _dt.datetime.utcfromtimestamp(_lp_exp).strftime('%Y-%m-%dT%H:%M:%S.000000Z')
                                _pd['days_left']  = max(0, round((_lp_exp - time.time()) / 86400))
                            else:
                                _pd['is_pro']    = False
                                _pd['is_vip']    = False
                                _pd['expires_at'] = None
                                _pd['days_left']  = 0
                            body = json.dumps(_pd).encode()
                    except Exception:
                        pass
                # ── Override gender+avatar for /api/customers/{uid} from SQLite ──
                _cust_m = re.match(r'^/customers/([^/?]+)$', api_path)
                if _cust_m and 'application/json' in content_type:
                    try:
                        _cd = json.loads(body)
                        if isinstance(_cd, dict):
                            _cuid = _cust_m.group(1)
                            # Check our authoritative customer_profiles table
                            with _chat_lock:
                                _cg_conn = _chat_db()
                                _cg_row  = _cg_conn.execute(
                                    'SELECT gender FROM customer_profiles WHERE uid=?', (_cuid,)
                                ).fetchone()
                                _cg_conn.close()
                            if _cg_row:
                                # We have a stored gender — authoritative, mark it
                                _gender = _cg_row[0]
                                _cd['gender']         = _gender
                                _cd['gender_from_db'] = True
                            else:
                                _gender = (_cd.get('gender') or 'male').lower()
                            _avatar = _cd.get('avatar') or ''
                            if not _avatar:
                                _cd['avatar'] = '/icon/woman.png' if _gender == 'female' else '/icon/man.svg'
                            body = json.dumps(_cd).encode()
                    except Exception:
                        pass
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except urllib.error.HTTPError as e:
                body = e.read()
                self.send_response(e.code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self._send_json(502, {'error': 'api unavailable'})
            return

        # Sitemap
        if path == '/sitemap.xml':
            xml = build_sitemap().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/xml; charset=utf-8')
            self.end_headers()
            self.wfile.write(xml)
            return

        # 301 redirect: card.html?id=123 or card?id=123 → /{id}-{slug}
        if path in ('/card.html', '/card'):
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

        # Generic 301: /*.html → /* (preserves query string)
        # /card.html?id=X is already handled above with special slug redirect.
        # /index.html is left as-is (homepage, no redirect needed).
        if path.endswith('.html') and path != '/index.html':
            clean_path = path[:-5]
            dest = clean_path + (f'?{qs}' if qs else '')
            self.send_response(301)
            self.send_header('Location', dest)
            self.end_headers()
            return

        # Static pages: serve *.html file at clean URL
        _STATIC_PAGES = [
            'about-us', 'contact-us', 'privacy-policy', 'advertising-policy',
            'terms-and-conditions', 'cookie-policy', 'terms-of-service',
            'withdrawals', 'refund-policy', 'payment-methods', 'payments-policy',
        ]
        for _page in _STATIC_PAGES:
            if path == f'/{_page}.html':
                self.send_response(301)
                self.send_header('Location', f'/{_page}')
                self.end_headers()
                return
            if path == f'/{_page}':
                html_file = os.path.join(SITE_ROOT, f'{_page}.html')
                if os.path.exists(html_file):
                    with open(html_file, 'rb') as fh:
                        body = fh.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

        # /post-ad → serve post-ad.html directly (no SEO injection needed)
        # Served from SITE_ROOT (not cwd) with no-cache to prevent stale versions
        if path == '/post-ad':
            html_file = os.path.join(SITE_ROOT, 'public', 'post-ad.html')
            if not os.path.isfile(html_file):
                html_file = os.path.join(SITE_ROOT, 'post-ad.html')
            try:
                with open(html_file, 'rb') as fh:
                    body = fh.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_response(500)
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

        # 301 redirect (e.g. /flats/for-sale → /property-for-sale/flats)
        if page_type == 'redirect_301':
            self.send_response(301)
            self.send_header('Location', params['location'])
            self.end_headers()
            return

        if page_type in ('homepage', 'listing', 'category', 'category_modifier',
                         'category_city', 'category_city_modifier',
                         'category_city_district', 'search', 'latest_updates',
                         'property_transaction', 'property_transaction_modifier',
                         'property_transaction_city',
                         'property_subtype', 'property_subtype_modifier',
                         'property_subtype_rent', 'property_subtype_sale',
                         'property_sale_type', 'category_transaction',
                         'property_subtype_city', 'property_subtype_city_district',
                         'cars_make', 'cars_make_city', 'cars_make_city_district',
                         'cars_category',
                         'cars_rent', 'cars_rent_make', 'cars_rent_make_city',
                         'cars_short_rent',
                         'motors_rent_parent', 'motors_short_rent_parent'):
            # Determine which HTML file to serve
            html_filename = {
                'homepage':       'index.html' if is_production else 'dev-index.html',
                'listing':        'card.html',
                'search':         'search.html',
                'latest_updates': 'search.html',
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
            if not os.path.isfile(actual):
                actual = os.path.join(SITE_ROOT, p_clean + '.html')
                if os.path.isfile(actual):
                    self.path = '/' + p_clean + '.html'
            if os.path.isfile(actual):
                super().do_GET()
                return

        # /cabinet/* deep links — serve cabinet.html directly
        if page_type == 'internal_subroute':
            fname = params.get('file', '')
            actual = os.path.join(SITE_ROOT, fname)
            if os.path.isfile(actual):
                self.path = '/' + fname
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
# Auto-delete expired listings (free plan, 30 days since creation/boost)
# ══════════════════════════════════════════════════════════════════════════════
def _auto_delete_expired():
    """Background thread: once per day, call Laravel to delete expired listings."""
    import time as _time
    _time.sleep(300)  # Wait 5 min after startup before first run
    while True:
        try:
            url     = f'{LARAVEL_API_BASE}/properties/auto-delete-expired'
            payload = b'{}'
            req     = urllib.request.Request(
                url, data=payload,
                headers={
                    'Content-Type':     'application/json',
                    'Accept':           'application/json',
                    'X-Bazar-Internal': 'moderation',
                },
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode('utf-8', errors='replace')
                print(f'[AUTO-DELETE] expired listings cleaned: {body}', flush=True)
        except Exception as exc:
            print(f'[AUTO-DELETE] error: {exc}', flush=True)
        _time.sleep(86400)  # Run once every 24 hours

threading.Thread(target=_auto_delete_expired, daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════
class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

with ReusableTCPServer(('0.0.0.0', PORT), BazarHandler) as httpd:
    print(f'Bazar SEO server running on port {PORT}')
    httpd.serve_forever()
