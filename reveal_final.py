#!/usr/bin/env python3
"""
Финальный рабочий скрипт reveal телефонов Gumtree через residential proxy.
Схема: логин через прокси (mobile UA) → reveal URL → srn=true → revealNumberUnmasked
Всё через curl subprocess (Python requests не умеет HTTPS CONNECT с auth).
"""
import re, json, subprocess, time, sys, logging, pymysql
from urllib.parse import unquote

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/var/log/bazar-reveal.log')
    ]
)
log = logging.getLogger()

DB = dict(host='127.0.0.1', user='bazar', password='BazarSecure2026',
          database='bazar_dev', charset='utf8mb4')

GT_EMAIL    = 'alexey_cy%40hotmail.com'   # %40 = @
GT_PASSWORD = '21Lexa21%21'              # %21 = !
PROXY_HOST  = 'geo.iproyal.com:12321'
PROXY_USER  = '1hFwYy0KNaTtK9UB'
PROXY_PASS  = 'KkfTkHRHGuRh0qfG_country-gb'
COOKIE_JAR  = '/tmp/gt_reveal_jar.txt'
MOBILE_UA   = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'

FAKE_PHONES = {'02604301904', '01617681162', '07998799430',
               '07376048198', '02604220101', '02604300101'}
UK_PHONE_RE = re.compile(r'^(07|01|02)\d{9}$')


def clean_phone(raw):
    if not raw:
        return None
    digits = re.sub(r'[\s\-\.\(\)\+]', '', str(raw))
    if digits.startswith('+44'):
        digits = '0' + digits[3:]
    if digits.startswith('44') and len(digits) == 12:
        digits = '0' + digits[2:]
    if not UK_PHONE_RE.match(digits):
        return None
    if digits in FAKE_PHONES:
        return None
    return digits


def get_client_data(html):
    m = re.search(r'window\.clientData\s*=\s*["\'](.+?)["\'];', html, re.S)
    if not m:
        return {}
    try:
        return json.loads(unquote(m.group(1)))
    except Exception:
        return {}


def curl(args, timeout=20, write_only_jar=False):
    """Обёртка для curl через residential proxy с cookie jar."""
    import os
    # Создаём пустой jar если не существует
    if not os.path.exists(COOKIE_JAR):
        open(COOKIE_JAR, 'w').close()
        try:
            os.chmod(COOKIE_JAR, 0o666)
        except Exception:
            pass

    base = [
        'curl', '-s', f'--max-time', str(timeout),
        '--proxy', f'http://{PROXY_HOST}',
        '--proxy-user', f'{PROXY_USER}:{PROXY_PASS}',
        '-c', COOKIE_JAR,
        '-H', f'User-Agent: {MOBILE_UA}',
    ]
    if not write_only_jar:
        base += ['-b', COOKIE_JAR]

    result = subprocess.run(base + args, capture_output=True, text=True, timeout=timeout + 5)
    return result.stdout, result.returncode


def login():
    """BFF логин через прокси. Возвращает True если успешно."""
    import os
    # Сбрасываем старый jar
    if os.path.exists(COOKIE_JAR):
        try:
            os.remove(COOKIE_JAR)
        except PermissionError:
            try:
                os.chmod(COOKIE_JAR, 0o666)
            except Exception:
                pass

    log.info('BFF login via proxy...')
    body, rc = curl([
        '-X', 'POST',
        'https://www.gumtree.com/bff-api/login/via-form',
        '-H', 'Content-Type: application/x-www-form-urlencoded',
        '-H', 'Accept: application/json',
        '-d', f'username={GT_EMAIL}&password={GT_PASSWORD}',
    ], write_only_jar=True)
    log.info(f'Login response: {body[:80]}')

    # Проверяем успех по redirect URL в теле
    if 'my.gumtree.com/manage/ads' in body or '"location"' in body:
        # GTSELLERSESSIONID должен быть в cookie jar (HttpOnly, сохранён curl)
        jar_content = open(COOKIE_JAR).read() if os.path.exists(COOKIE_JAR) else ''
        if 'GTSELLERSESSIONID' in jar_content:
            log.info('Login OK — GTSELLERSESSIONID in jar')
            return True
        else:
            log.warning('Login response OK but no GTSELLERSESSIONID in jar')
            return True  # Может быть всё равно работает
    log.error(f'Login FAILED: {body[:200]}')
    return False


def get_fresh_reveal_url(listing_url):
    """Загружаем страницу объявления через прокси, возвращаем (reveal_url, seller, is_expired)."""
    body, rc = curl([
        '-H', 'Accept: text/html,application/xhtml+xml',
        listing_url
    ], timeout=20)

    # Листинг удалён/истёк — Gumtree редиректит на /error/404
    if len(body) < 200 or 'error/404' in body or 'Moved Permanently' in body:
        return None, {}, True

    cd = get_client_data(body)
    seller = cd.get('sellerContactDetails', {})

    callback = seller.get('revealPhoneCallbackUrl', '')
    if callback:
        reveal_url = f'https://www.gumtree.com{callback}' if callback.startswith('/') else callback
        return reveal_url, seller, False

    log.debug(f'No revealPhoneCallbackUrl in page: userLoggedIn={seller.get("userLoggedIn")}')
    return None, seller, False


def reveal_phone(reveal_url, listing_url):
    """
    Вызываем reveal URL → 303 → листинг?srn=true → revealNumberUnmasked.
    """
    # Шаг 1: reveal → 303
    body303, rc = curl([
        '--no-location',    # не следуем редиректу автоматически
        '-D', '-',          # заголовки в stdout
        '-H', 'Accept: application/json, text/plain, */*',
        '-H', 'X-Requested-With: XMLHttpRequest',
        '-H', f'Referer: {listing_url}',
        reveal_url
    ], timeout=20)

    # Ищем Location в заголовках
    loc_m = re.search(r'(?i)^location:\s*(.+)$', body303, re.M)
    if not loc_m:
        # Нет редиректа — может прямой JSON?
        try:
            data = json.loads(body303.split('\r\n\r\n', 1)[-1] if '\r\n\r\n' in body303 else body303)
            for k in ('phoneNumber', 'phone', 'telephone', 'revealedNumber', 'number'):
                v = data.get(k, '')
                if v:
                    ph = clean_phone(str(v))
                    if ph:
                        return ph
        except Exception:
            pass
        log.debug(f'No Location header in reveal response: {body303[:200]}')
        return None

    srn_url = loc_m.group(1).strip()
    log.debug(f'Redirect to: {srn_url}')

    # Шаг 2: GET srn=true страница
    if '?' not in srn_url:
        srn_url += '?srn=true'
    elif 'srn=true' not in srn_url:
        srn_url += '&srn=true'

    body_srn, rc2 = curl([
        '-H', 'Accept: text/html,application/xhtml+xml',
        '-H', f'Referer: {listing_url}',
        srn_url
    ], timeout=20)

    cd = get_client_data(body_srn)
    seller = cd.get('sellerContactDetails', {})

    # revealNumberUnmasked — золото!
    raw = seller.get('revealNumberUnmasked', '')
    if raw:
        ph = clean_phone(str(raw))
        if ph:
            return ph

    # Fallback: revealedNumber
    raw2 = seller.get('revealedNumber', '')
    if raw2 and isinstance(raw2, str) and len(raw2) > 5:
        ph = clean_phone(raw2)
        if ph:
            return ph

    # Fallback: поиск в HTML
    for pat in [r'(07\d{9})', r'(01\d{9})', r'(02\d{9})']:
        for p in re.findall(pat, body_srn):
            ph = clean_phone(p)
            if ph:
                return ph

    log.debug(f'No phone in srn page. Seller: {seller}')
    return None


def run():
    log.info('=== Gumtree Phone Reveal (curl + proxy) ===')

    # Логин
    if not login():
        log.error('Login failed. Exiting.')
        sys.exit(1)

    # Лиды из БД
    db = pymysql.connect(**DB)
    cur = db.cursor(pymysql.cursors.DictCursor)
    cur.execute("""
        SELECT id, title, listing_url, reveal_url, phone_masked
        FROM leads
        WHERE phone IS NULL
          AND listing_url IS NOT NULL
          AND phone_masked IS NOT NULL
          AND phone_masked != ''
        ORDER BY id
    """)
    leads = cur.fetchall()
    cur.close()
    log.info(f'Leads to process: {len(leads)}')

    revealed   = 0
    skipped    = 0
    errors_471 = 0
    duplicates = 0
    expired    = 0
    re_login_at = 30   # каждые N лидов — повторный логин (токен живёт 1 час)

    for i, lead in enumerate(leads, 1):
        lid   = lead['id']
        title = (lead['title'] or '')[:45]
        log.info(f'[{i}/{len(leads)}] Lead {lid}: {title}')

        # Периодический повторный логин (сессия = 1 час)
        if i > 1 and i % re_login_at == 1:
            log.info('Re-login (session refresh)...')
            login()
            time.sleep(2)

        # Получаем свежий reveal URL
        reveal_url, seller, is_expired = get_fresh_reveal_url(lead['listing_url'])

        # Листинг удалён на Gumtree — удаляем лид из БД
        if is_expired:
            exp_c = db.cursor()
            exp_c.execute('DELETE FROM leads WHERE id = %s', (lid,))
            db.commit()
            exp_c.close()
            expired += 1
            log.info(f'  ✗ EXPIRED — listing deleted on Gumtree, lead #{lid} removed from DB')
            time.sleep(0.5)
            continue

        if not reveal_url:
            log.info(f'  No reveal URL (userLoggedIn={seller.get("userLoggedIn")})')
            skipped += 1
            time.sleep(1)
            continue

        # Reveal!
        phone = reveal_phone(reveal_url, lead['listing_url'])

        if phone:
            # Проверяем: вдруг этот телефон уже есть в другом лиде
            chk = db.cursor()
            chk.execute('SELECT id FROM leads WHERE phone = %s AND id != %s LIMIT 1', (phone, lid))
            existing = chk.fetchone()
            chk.close()
            if existing:
                # Дубликат — удаляем текущий лид, оставляем тот у кого уже есть телефон
                del_c = db.cursor()
                del_c.execute('DELETE FROM leads WHERE id = %s', (lid,))
                db.commit()
                del_c.close()
                duplicates += 1
                log.info(f'  ✗ DUP phone {phone} already in lead #{existing[0]} — deleted lead #{lid}')
            else:
                upd = db.cursor()
                upd.execute('UPDATE leads SET phone=%s, updated_at=NOW() WHERE id=%s', (phone, lid))
                db.commit()
                upd.close()
                revealed += 1
                log.info(f'  ✓ PHONE: {phone}  (was masked: {lead["phone_masked"]})')
        else:
            log.info(f'  — no phone')
            skipped += 1

        # Пауза между запросами (не спамим)
        time.sleep(1.5)

        # Каждые 25 лидов — большая пауза
        if i % 25 == 0:
            log.info(f'--- Pause 10s [{revealed} revealed so far] ---')
            time.sleep(10)

    db.close()
    log.info('')
    log.info(f'=== DONE: {revealed} phones revealed, {skipped} skipped, {duplicates} dups removed, {expired} expired deleted, {errors_471} 471s ===')
    log.info(f'=== From {len(leads)} total leads ===')


if __name__ == '__main__':
    run()
