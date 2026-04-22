# Bazar UI

A static HTML/CSS/JS classified ads marketplace website UI.

---
## ⛔⛔⛔ АБСОЛЮТНЫЙ ЗАПРЕТ — ЧИТАТЬ ПЕРВЫМ ⛔⛔⛔

**DEV — НЕ ТРОГАТЬ. НИКОГДА. НИ ПРИ КАКИХ ОБСТОЯТЕЛЬСТВАХ.**

Агент работает ТОЛЬКО с продакшеном. Dev обновляет ТОЛЬКО пользователь командой `bash dev.sh`.

Запрещено без каких-либо исключений:
- Копировать, деплоить, менять файлы в `/var/www/bazar-dev/` (это dev Laravel)
- Писать SQL в базу `bazar_prod` (это dev база)
- Запускать `bash dev.sh`
- Делать scp/rsync/ssh-команды, которые затрагивают dev

Продакшен — это:
- Файлы: `/var/www/bazar-prod/` и `/var/www/bazar-prod/public/`
- База данных: `bazar_dev`
- URL: www.bazar.uk, admin.bazar.uk

Dev — это (НЕ ТРОГАТЬ):
- Файлы: `/var/www/bazar-dev/`
- База данных: `bazar_prod`
- URL: dev.bazar.uk, dev.bazar.uk/dev-admin

Если dev сломан — это исправляет пользователь через `bash dev.sh`. Агент не вмешивается.

---

## ⛔ ПРАВИЛА ДЛЯ АГЕНТА — ОБЯЗАТЕЛЬНО К ИСПОЛНЕНИЮ

1. **DEV-САЙТ (dev.bazar.uk) — ТОЛЬКО ПОЛЬЗОВАТЕЛЬ.** Агент НИКОГДА не копирует, не синхронизирует и не деплоит файлы на dev.bazar.uk самостоятельно. Не запускать `bash dev.sh`. Не делать rsync/scp из prod в dev. Не делать rsync/scp из Replit в /var/www/bazar-dev/. Не писать SQL в `bazar_prod`. Синхронизацию prod → dev делает только пользователь вручную командой `bash dev.sh`.

2. **DEPLOY только в PROD.** Агент пишет код и деплоит только в `/var/www/bazar-prod/` (prod). Скрипт деплоя: `bash deploy.sh <файлы>`. server.py деплоится в `/var/www/bazar-prod/server.py` (НЕ в public/).

3. **БАЗЫ ДАННЫХ — ЖЕЛЕЗНАЯ АРХИТЕКТУРА (не менять без явной просьбы):**

   НАПРАВЛЕНИЕ СИНХРОНИЗАЦИИ: ТОЛЬКО прод → dev. НИКОГДА наоборот.

   | Среда | URL | Python | API | Laravel | БД MySQL |
   |---|---|---|---|---|---|
   | **ПРОД** | www.bazar.uk | port 5000 | admin.bazar.uk/api | /var/www/bazar-prod/ | **bazar_dev** |
   | **ПРОД АДМИН** | admin.bazar.uk | — | — | /var/www/bazar-prod/ | **bazar_dev** |
   | **DEV** | dev.bazar.uk | port 5001 | 127.0.0.1:9001/api | /var/www/bazar-dev/ | **bazar_prod** |
   | **DEV АДМИН** | dev.bazar.uk/dev-admin | — | — | /var/www/bazar-dev/ | **bazar_prod** |

   - Прод-база: `bazar_dev` (используется admin.bazar.uk через `/var/www/bazar-prod/.env`)
   - Dev-база: `bazar_prod` (используется dev через FPM pool `/etc/php/8.3/fpm/pool.d/bazar-dev-api.conf`: `env[DB_DATABASE] = bazar_prod`)
   - **bash dev.sh** синхронизирует:
     1. Frontend: rsync `/var/www/bazar-prod/public/` → `/var/www/bazar-dev/public/`
     2. БД: `mysqldump bazar_dev | mysql bazar_prod` (прод → dev)
     3. Перезапускает `bazar-seo-dev`
   - Dev admin путь: `/dev-admin` (на dev.bazar.uk), `/` (на admin.bazar.uk) — AdminPanelProvider.php
   - `/etc/nginx/sites-enabled/bazar-dev` — regex приоритет: dev-admin|login|filament|livewire → PHP-FPM dev
   - **bootstrap/app.php** (`/var/www/bazar-dev/`): trustProxies(at:'*') + validateCsrfTokens(except livewire-*/update) для dev.bazar.uk
   - **ВАЖНО**: НЕ запускать `php artisan config:cache` на dev — ломает FPM pool env vars
   - **АГЕНТ НИКОГДА не трогает /var/www/bazar-prod/.env и не меняет прод-конфиг без явного запроса**
   - **window.BAZAR_API** (с апрель 2026): все JS-файлы используют `window.BAZAR_API` вместо хардкода `admin.bazar.uk/api`.
     Определено в `js/script.js`, `js/firebase-auth.js`, `js/firebase-auth-v2.js`, `js/header-auth.js`:
     - На `www.bazar.uk` / `bazar.uk` → `'https://admin.bazar.uk/api'`
     - На dev.bazar.uk → `'/api'` (→ Python:5001 → 127.0.0.1:9001 → bazar_prod)
     Это обеспечивает полную изоляцию dev от прод-данных.

4. **ВСЕГДА отвечать ТОЛЬКО на русском языке.** Никогда не писать на украинском, английском или другом языке. Только русский.

---

## Project Structure

- `index.html` - Main homepage
- `search.html` - Search results page
- `card.html` - Individual listing card
- `cabinet.html` - Personal account / cabinet page
- `real-estate.html` - Real estate category page
- `components.html` - UI components showcase
- `css/` - Stylesheets (main.css, choices.min.css, swiper, etc.)
- `js/` - JavaScript files (script.js, swiper, choices, etc.)
- `img/` - Images
- `icon/` - SVG and PNG icons (including man.png, man.svg, woman.png)
- `fonts/` - Poppins font family + icon font
- `video/` - Background video files
- `#source/` - SCSS source files

## Running the Project

Сервер: `server.py` — кастомный Python HTTP server с `Cache-Control: no-cache`.

```
python3 server.py
```

Workflow: "Start application" on port 5000 (webview)

## Deployment

- Replit dev preview: pike.replit.dev URL
- Published: bazar-ui.replit.app
- Production: www.bazar.uk
- GitHub: BazarMarket/bazar-ui
- Push: `bash push.sh` — **НЕ пушить автоматически!** Пользователь сам пушит через консоль когда нужно.

### ⚠️ Правильные пути деплоя на сервер (49.13.231.137)

```bash
# server.py — деплой В КОРЕНЬ (НЕ в public/!)
scp -i .local/ssh/bazar_deploy server.py root@49.13.231.137:/var/www/bazar-prod/server.py

# HTML файлы — деплой в public/
scp -i .local/ssh/bazar_deploy card.html root@49.13.231.137:/var/www/bazar-prod/public/card.html
scp -i .local/ssh/bazar_deploy post-ad.html root@49.13.231.137:/var/www/bazar-prod/public/post-ad.html

# Перезапуск SEO сервера
ssh -i .local/ssh/bazar_deploy root@49.13.231.137 "systemctl restart bazar-seo"
```

## SEO URL структура (реализовано)

Формат: `/{id}-{slug}` — ID в начале, slug из title+district+city

| Запрос | Ответ |
|---|---|
| `/39-2-bedroom-house-for-sale-chelsea-london` | 200 — страница объявления |
| `/39` | 301 → `/39-2-bedroom-house-for-sale-chelsea-london` |
| `/listing/39` | 301 → `/39-2-bedroom-house-for-sale-chelsea-london` |
| `/card.html?id=39` | 301 → `/39-2-bedroom-house-for-sale-chelsea-london` |

- Canonical: `https://www.bazar.uk/{id}-{slug}`
- Sitemap: только slug URLs
- Slug-функция: `_make_slug(title, district, city)` в server.py
- Правило роутинга: путь начинается с **цифры** = объявление; с **буквы** = категория/страница

## CSS Versioning

**Текущие версии CSS/JS:**
- index.html: main.css?v=121, header-auth.js?v=12
- search.html: main.css?v=120, header-auth.js?v=12
- card.html: main.css?v=201, header-auth.js?v=12
- cabinet.html: main.css?v=119, header-auth.js?v=12
- icon-style.css?v=2

Обновлять версию в: index.html, card.html, search.html, cabinet.html

## Responsive Breakpoints (search.html)

- **≤1200px** — tablet landscape: smaller card images (320px), grid 3 cols
- **≤992px** — tablet portrait: search full-width, card image 260px, hide description, hide view sidebar, grid 3 cols
- **≤768px** — small tablet: cards stack vertically (image on top), smaller controls (40px), breadcrumb stacks, grid 2 cols, Key features panel 2-column
- **≤576px** — mobile: all filters stack vertically full-width, controls 42px, grid 2 cols, Key features 1-column, compact card styling
- **≤400px** — very small mobile: grid 1 col, hide location select, minimal padding
- Media queries are placed AFTER base card styles to ensure proper cascade with !important
- `toggleMoreFilters()` uses `scrollHeight` for dynamic height (mobile-aware)

## Заголовок (header-old) — порядок ячеек

card.html и index.html (залогиненный, `#header-logged-in`):

```
[логотип] | [.header-old__vsep] | [£ 3 216 кошелёк] | [+ POST AN AD] | [email + heart иконки] | [имя + аватарка]
```

## user-link (имя + аватар в хедере)

Порядок элементов внутри `.user-link`: **аватарка первой**, затем имя.

```css
.user-link__title {
  margin-left: 10px;
  font-size: 18px; font-weight: 700; text-transform: capitalize;
  max-width: 135px; text-align: left;
  display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden;
}
.user-link__photo { width: 60px; height: 60px; }
```

- Аватар по умолчанию: `icon/man.svg`
- Женский аватар: `icon/woman.png`
- id для JS: `id="header-username"` (имя), `id="header-avatar"` (аватар)

## .btn_mini (кнопка POST AN AD в header-old)

```css
.btn_mini { font-size: 15px; padding: 12px; border-radius: 14px; }
```

## Регистрация — 3 шага (index.html)

1. **createAccountModal** — телефон + чекбокс + SMS/WhatsApp
2. **otpModal** — 4 цифры кода (при вводе последней → автоматически открывается шаг 3)
3. **profileModal** — Almost there!
   - Аватарка (меняется при выборе Male/Female)
   - Кнопки Male (по умолчанию активна, оранжевая обводка) / Female
   - Full name (обязательное поле)
   - Get started (серая пока не заполнено имя → оранжевая после заполнения)
   - При завершении: имя → `#header-username`, аватар → `#header-avatar`, вызов `doLogin()`

## Login toggle — логика по средам (ЗАФИКСИРОВАНО, НЕ МЕНЯТЬ)

### Три среды — три разных поведения

| Среда | Hostname | При нажатии "Log in" | При загрузке страницы |
|---|---|---|---|
| **Production** | www.bazar.uk, bazar.uk | Открывает форму (телефон + OTP) | Если есть `bazar_username` в localStorage → `doLogin()` (восстановление сессии) |
| **DEV** | dev.bazar.uk | Автологин без формы | Автологин (Andreas Xenofontos) |
| **Replit** | *.replit.dev, localhost | Автологин без формы | Автологин (Andreas Xenofontos) |

### Автологин / восстановление сессии (DOMContentLoaded в firebase-auth.js)
```js
if (!isProduction) {
    // DEV / Replit — автологин с дефолтными данными
    if (!localStorage.getItem('bazar_username')) {
        localStorage.setItem('bazar_username',     'Andreas Xenofontos');
        localStorage.setItem('bazar_gender',       'male');
        localStorage.setItem('bazar_firebase_uid', 'test_uid_123');
        if (!localStorage.getItem('bazar_plan')) localStorage.setItem('bazar_plan', 'free');
    }
    doLogin();
} else {
    // Production — восстанавливаем сессию если пользователь уже логинился
    if (localStorage.getItem('bazar_username')) {
        doLogin();
    }
}
```
- DEV/Replit: `doLogin()` ВСЕГДА при загрузке, дефолты ставятся только если нет в localStorage
- Production: `doLogin()` только если `bazar_username` уже есть в localStorage (сессия восстанавливается при переходе между страницами)
- Без этого при переходе cabinet → index пользователь видит форму "Log in" вместо своего аккаунта

### ⚠️ cabinet.html — НЕЛЬЗЯ хардкодить имена/данные
- `#header-username` — всегда пустой в HTML, заполняется через `doLogin()` → `localStorage`
- Приветствие, settings форма — заполняются через `populateUserData()` из localStorage
- НЕ писать "Andreas", "Karafouni", "+44 791..." или любые другие данные прямо в HTML

### Повторный вход (Log out → Log in) на Production
После OTP верификации — проверяем API: `GET /api/customers/{firebase_uid}`
- **Аккаунт найден** → данные из БД → `doLogin()` (форма не показывается)
- **Новый пользователь** → `openProfileModal()` (форма "Almost there!" показывается один раз)

### Кнопка "Log in" → `handleLogin()` (js/firebase-auth.js)
```js
if (www.bazar.uk || bazar.uk) → openLoginModal()   // форма телефона
else → doLogin()                                    // DEV/Replit: прямой вход
```

### Кнопка "Create an account" → `openCreateAccountModal()`
Всегда открывает форму с телефоном (одна форма, разный заголовок).

### Ключевые функции:
- `handleLogin()` — роутер по hostname
- `openLoginModal()` — заголовок "Log in" + открывает createAccountModal
- `openCreateAccountModal()` — заголовок "Create an account" + открывает тот же модал
- `doLogin()` — скрывает `#header-guest`, показывает `#header-logged-in`, имя из localStorage
- `doLogout()` — обратно, очищает localStorage: `bazar_username`, `bazar_phone`, `bazar_gender`, `bazar_plan`, `bazar_firebase_uid`

### localStorage ключи пользователя:
- `bazar_username` — полное имя
- `bazar_phone` — телефон
- `bazar_gender` — male / female
- `bazar_plan` — free / pro / vip
- `bazar_firebase_uid` — Firebase UID (test_uid_123 для DEV/Replit)

### ESC закрывает модалы
В firebase-auth.js на `document keydown` — закрывает createAccountModal, otpModal, profileModal.

### ⚠️ НЕЛЬЗЯ добавлять onAuthStateChanged
Вызывает бесконечный цикл на production: null user → doLogout() → auth.signOut() → снова onAuthStateChanged.

### ⚠️ НЕ добавлять иконки/SVG в кнопку "Log in" (.btn_start)
Кнопка должна содержать только текст "Log in". Была ошибка с `addPhoneIcon()` — удалена.

## Выравнивание контента

- `.container-full`: max-width 1600px, padding: 0 32px
- Секции внутри: `margin: 0 6%`
- Любой контент с `margin: 0 6%` ОБЯЗАН быть внутри `container-full` (padding: 0 32px)

## ⚠️ post-ad.html — выравнивание лейблов формы (ЗАФИКСИРОВАНО, НЕ МЕНЯТЬ)

`.pa-field__label` в `post-ad.html` ОБЯЗАН иметь `min-width: 155px; max-width: 155px; white-space: normal`.

**Почему:** при 120px длинные лейблы («Online viewing», «Energy Efficiency», «Registration block», «Registration number», «Air conditioning», «Construction year») не влезают и инпуты съезжают в разные горизонтальные позиции. Это визуальный баг — «ячейки не на одном уровне».

**Что нельзя делать:**
- Менять ширину с 155px на 120px (или любую другую)
- Добавлять `pa-field__label--wide` (162px) отдельным полям — это снова создаст смещение
- Добавлять `pa-field__label--wrap` + `white-space: nowrap` — лейблы перестанут влезать
- Все поля формы должны использовать ОДИН базовый класс `pa-field__label` без модификаторов

## ⚠️ CSS-ловушки

- `.card-grid p { margin: 0 }` обнуляет отступы у ВСЕХ `<p>` внутри карточки — добавляй `!important`
- Файлы с Windows line endings (`\r\n`) — при Python-заменах использовать бинарное чтение/запись
- Браузерный кеш: версии CSS сбрасывают кеш; при проблемах → Ctrl+Shift+R

## Заголовки объявлений недвижимости — правило по умолчанию

Формат: `[кол-во спален] Bedroom [тип] for Sale` (или for Rent)
- Примеры: "2 Bedroom Villa for Sale", "3 Bedroom House for Sale", "4 Bedroom Apartment for Sale"
- Студия: "Studio Apartment for Sale"
- Тип берётся из property_type: Apartment, House, Villa и т.д.
- **НЕ использовать** креативные/маркетинговые названия (не "Elegant Country House", не "Modern Penthouse in Edinburgh")

## Цена (card.html) — правила по умолчанию

- **Одна цена** (нет `old_price`): цвет **чёрный** (`#1d1d1b`), зачёркнутая цена скрыта
- **Две цены** (есть `old_price > 0`): новая цена **красная** (`red`), старая — **чёрная** (`#1d1d1b`) зачёркнутая
- **Формат**: цифры после запятой через `<sup>` (мелкие и выше): `425,<sup>000</sup>£`, как оригинал `814,<sup>99</sup>£`
- Знак `£` всегда в КОНЦЕ, без пробела: `425,000£`
- CSS: `.price-last-new { font-size: 36px }`, `.price-last-old { font-size: 22px }`
- Функция `fmtPrice(n)` в IIFE card.html разбивает число по последней запятой

## Иконки мессенджеров (card.html) — правило по умолчанию

- `.card-name__bottom { margin-top: 10px; }` — фиксированный отступ 10px от аватарки до WhatsApp/Telegram/Viber иконок, НЕ `auto`

## Цвета

- Основной оранжевый: `#ff9138`
- Start Chat зелёный: `#3ecb60`
- Цена: чёрная (одна цена) или красная (две цены) — см. раздел "Цена"
- Telegram синий: `#2aabee`

## Boost to Top — логика и подключение

### Где показывается кнопка
| Страница | Место | Условие показа |
|---|---|---|
| `search.html` List View | Абсолютно сверху-справа карточки | Free plan + `item.s === bazar_username` |
| `search.html` Grid View | В `.card__stikers` (top-left), видна при hover | Free plan + `item.s === bazar_username` |
| `card.html` | Слева от кнопки Edit Ad в navbar | Free plan + `p.seller_name === bazar_username` + `!p.is_vip && !p.is_pro` |
| `cabinet.html` My Ads | В строке действий с объявлением | Всегда (только Free-план пользователи видят свои объявления) |

### Demo-режим (для тестирования)
- URL-параметр `?boost_demo=1` показывает кнопку на объявлениях с `stk:[]` и `cc:''`
- List View: `search.html?cat=sale&type=House&boost_demo=1`
- Grid View: переключиться на Grid после перехода по ссылке выше
- Card page: `card.html?id=10&boost_demo=1`

### CSS классы
- `.card__boost-btn` — Grid View (hover-кнопка в `.card__stikers`)
- `.card-head__boost` — Card page navbar (красная #ff0000, hover #cc0000)

### JS функция bazarBoostPay(returnUrl, listingId)
Определена в `card.html`, `search.html`, `cabinet.html`. Логика:
1. Берёт `bazar_firebase_uid` из localStorage
2. Определяет API URL (prod vs dev/Replit)
3. POST-запрос на сервер → получает Stripe Checkout URL
4. Редиректит на Stripe. Success → `returnUrl?boosted=1`

### API URL по средам
- **www.bazar.uk**: `https://admin.bazar.uk/api/stripe/checkout/boost`
- **Replit/dev**: `/api/boost-checkout` (server.py)

### server.py (Replit dev)
- `do_POST /api/boost-checkout` — создаёт Stripe Checkout Session £1 через `stripe` Python SDK
- `STRIPE_SECRET_KEY` из env vars

## Stripe Integration (Laravel на admin.bazar.uk)

### Архитектура
- `config/stripe.php` — все настройки (ключи, планы, URLs)
- `app/Services/Stripe/StripeConnectService.php` — Connect аккаунты продавцов
- `app/Services/Stripe/StripeCheckoutService.php` — Checkout для PRO/VIP
- `app/Services/Stripe/StripeWebhookService.php` — обработка событий
- Controllers: StripeConnectController, StripeCheckoutController, StripeWebhookController
- Request validation: ConnectAccountRequest, CheckoutPlanRequest

### API endpoints
- `POST /api/stripe/connect/account/create` — создать Connect аккаунт продавца
- `POST /api/stripe/connect/account/onboarding-link` — ссылка на Stripe onboarding
- `GET  /seller/stripe/refresh?uid=` — обновить onboarding ссылку
- `GET  /seller/stripe/return?uid=` — синхронизировать статус аккаунта
- `POST /api/stripe/checkout/plan` — Checkout сессия для PRO/VIP
- `POST /api/stripe/checkout/boost` — Checkout сессия £1 для Boost to Top ← НОВЫЙ
- `POST /api/stripe/webhook` — webhook от Stripe

### Планы (config/stripe.php)
- PRO: £7.00 / 30 дней
- VIP: £14.00 / 30 дней
- Boost to Top: £1.00 / разовый платёж (metadata: source=boost_to_top)

### Таблицы БД
- `customers` — добавлены: stripe_connected_account_id, stripe_onboarding_completed, stripe_details_submitted, stripe_charges_enabled, stripe_payouts_enabled, bazar_plan, bazar_plan_expires_at
- `payments` — все транзакции: customer_id, stripe_checkout_session_id, stripe_payment_intent_id, amount, currency, status, payment_type, metadata, paid_at

### Webhook events
- `checkout.session.completed` → активирует plan в customers
- `account.updated` → обновляет статус Connect аккаунта
- `payment_intent.succeeded` → логирует платёж

### STRIPE_WEBHOOK_SECRET
После регистрации webhook в Stripe Dashboard добавить в .env на сервере.

## Tech Stack

HTML/CSS/JS → future migration to Laravel + Blade + PostgreSQL + Filament admin (Hetzner CX22)

## ⚠️ КРИТИЧНО: DEV vs PRODUCTION — cabinet.html

У нас **один файл `cabinet.html`** для всех сред. Разделение реализовано через `window.location.hostname`.

### Правило при деплое

**НИКОГДА не менять логику ниже при переносе кода DEV → PROD.**
Продакшн-скрипт в конце `cabinet.html` (тег `<script>` перед `</body>`) — **неприкосновенный блок**.

### Что скрывается на www.bazar.uk (и только там)

| Элемент | ID | На DEV/Replit | На prod (www.bazar.uk) |
|---|---|---|---|
| Wallet виджет в шапке | `walletWidgetCell`, `walletSep` | ✅ виден | ❌ скрыт |
| My Payments в меню пользователя | `menuMyPayments` | ✅ виден | ❌ скрыт |
| My Payments в сайдбаре | `navMyPayments` | ✅ виден | ❌ скрыт |
| Deposit/Withdraw формы на Dashboard | `devDashSections` | ✅ видны | ❌ скрыты |
| Recent Transactions на Dashboard | `prodDashRecentTxn` | ❌ скрыт | ✅ виден |
| Deposit/Withdraw в My Payments | `devPayForm` | ✅ видны | ❌ скрыты |
| Transaction History с фильтрами | `prodTxnFull` | ❌ скрыт | ✅ виден |

### Продакшн-скрипт (в конце cabinet.html, НЕ УДАЛЯТЬ)

```javascript
if (window.location.hostname === 'www.bazar.uk') {
    document.addEventListener('DOMContentLoaded', function() {
        // Скрыть wallet + My Payments nav
        ['walletWidgetCell','walletSep','menuMyPayments','navMyPayments'].forEach(function(id) {
            var el = document.getElementById(id); if (el) el.style.display = 'none';
        });
        // Dashboard: скрыть DEV, показать PROD
        var devDash  = document.getElementById('devDashSections');
        var prodDash = document.getElementById('prodDashRecentTxn');
        if (devDash)  devDash.style.display  = 'none';
        if (prodDash) prodDash.style.display = '';
        // Payments: скрыть Deposit/Withdraw, показать Transaction History
        var devPay  = document.getElementById('devPayForm');
        var prodPay = document.getElementById('prodTxnFull');
        if (devPay)  devPay.style.display  = 'none';
        if (prodPay) prodPay.style.display = '';
    });
}
```

### Почему так сделано

Stripe проверяет сайт и не должен видеть Deposit/Withdraw (это не seller flow).
Когда Stripe-проверка пройдёт и карты подключат нормально — удалим продакшн-скрипт и всё вернётся.

### Wallet-виджет скрыт на продакшне через script.js

В конце `js/script.js` добавлен блок:
```javascript
(function() {
    if (window.location.hostname !== 'www.bazar.uk') return;
    function hideWallet() {
        document.querySelectorAll('.wallet-widget').forEach(function(el) {
            var cell = el.closest('.header-old__cell') || el.parentElement;
            if (cell) {
                cell.style.display = 'none';
                var prev = cell.previousElementSibling;
                if (prev && prev.classList.contains('header-old__vsep')) prev.style.display = 'none';
            } else { el.style.display = 'none'; }
        });
        document.querySelectorAll('a.user-menu-item.icon-win-wallet').forEach(function(el) { el.style.display = 'none'; });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hideWallet);
    else hideWallet();
})();
```
`messages.html` не подключает `script.js`, поэтому аналогичный minified-блок добавлен в конце этого файла напрямую.

**При деплое script.js на продакшн** — этот блок должен сохраняться. **НЕ УДАЛЯТЬ**.

### Правило при добавлении нового функционала в cabinet.html

- Если функционал **только для DEV** — оборачивай в `<div id="devXxx">`, скрывай через продакшн-скрипт
- Если функционал **только для PROD** — оборачивай в `<div id="prodXxx" style="display:none">`, показывай через продакшн-скрипт
- Продакшн-скрипт всегда в самом конце перед `</body>`

---

## 📍 РАЙОН (DISTRICT) — логика сохранения и отображения

> **ЗАФИКСИРОВАНО.** Если районы перестали отображаться — читать этот раздел первым.

### Как район попадает в БД

Путь: пользователь выбирает адрес/точку → JS → Google API → hidden inputs → FormData → Laravel → DB

#### Шаг 1 — Основной автокомплит (`initLocationAutocomplete` в `post-ad.html`)

Когда пользователь выбирает адрес из выпадающего списка, срабатывает `place_changed`. Из компонентов адреса (`address_components`) последовательно извлекаются:

1. `postal_town` → `city` (для UK почтовый город)
2. `sublocality_level_1`, `sublocality`, `neighborhood` → `district`
3. `administrative_area_level_3` → `district` (fallback)
4. **Greater London fix**: если `administrative_area_level_2 === "Greater London"` И `city !== "London"` → `district = city`, `city = "London"`. Так Wembley, Croydon, Harrow становятся районами, а не городами.
5. Если `locality !== city` → `locality` становится `district` (e.g. Canary Wharf vs London)
6. **formatted_address fallback**: `extractDistrictFromFormatted(formatted, city)` — парсит район из текста: `"13 Cleveland Sq, Bayswater, London W2 → Bayswater"`

#### Шаг 2 — Карта (`confirmLocationMap` в `post-ad.html`)

Когда пользователь тыкает на карту и нажимает "Use selected location":

1. Координаты пишутся в **ОБА** поля: `locationLat/locationLng` И `exactLat/exactLng`  
   ⚠️ Раньше писалось только в exactLat — и latitude оставалась NULL в DB.

2. Запускается `geocoder.geocode({ location: { lat, lng } })` — возвращает **массив результатов**.

3. **4-проходный алгоритм** по всем результатам:
   - **Pass 1** — из `results[0]`: city, postcode, region, adminL2. Greater London fix.
   - **Pass 2** — перебрать **все** results в поиске `neighborhood`, `sublocality_level_1`, `sublocality`, `sublocality_level_2`, `administrative_area_level_3`. Район часто лежит в `results[3-5]`, а не в `results[0]`!
   - **Pass 3** — перебрать **все** results в поиске `locality !== city && locality !== "London"`.
   - **Pass 4** — `extractDistrictFromFormatted()` применяется к `formatted_address` каждого из всех results по очереди, пока не найдёт непустой результат.

   Пример: для точки в Peckham `results[0]` = "19 Waghorn St, London SE15 4LA" (без района), но `results[4]` = "Peckham, London SE15" → Pass 4 → `extractDistrictFromFormatted("Peckham, London SE15, UK", "London")` → **"Peckham"**.

#### Функция `extractDistrictFromFormatted(formatted, city)`

```javascript
// Алгоритм:
// 1. Split по запятой → parts
// 2. Найти индекс части, начинающейся с city ("London") → cityIdx
// 3. Если cityIdx < 1 → нет что парсить, return ''
// 4. Идти назад от cityIdx-1 до 0:
//    - Пропустить если начинается с цифры (номер дома)
//    - Пропустить если matches /^[A-Z]{1,2}\d/ (UK postcode fragment)
//    - Пропустить если j===0 и содержит слова Street/Road/Lane/... (это улица)
//    - Первое подходящее слово = район
// Примеры:
//   "13 Cleveland Sq, Bayswater, London W2 → Bayswater ✓
//   "Belgravia, London, UK"               → Belgravia ✓
//   "Peckham, London SE15, UK"            → Peckham ✓
//   "Fann St, Barbican, London EC2Y"      → Barbican ✓
//   "19 Waghorn St, London SE15 4LA"      → '' (нет промежуточной части)
//   "London SW1W 9QJ, UK"                 → '' (cityIdx=0)
```

#### Шаг 3 — Map search внутри карты (`lmSearchInput`)

Поиск внутри модалки карты тоже получает `address_components` (добавлено в `fields`). При выборе из дропдауна применяется тот же алгоритм (Greater London fix + locality + extractDistrictFromFormatted) + сразу пишет `locationLat/locationLng`.

### Куда пишутся данные — hidden inputs в post-ad.html

| Поле | ID | FormData key |
|---|---|---|
| Город | `locationCity` | `city` |
| Район | `locationDistrict` | `district` |
| Регион | `locationRegion` | `region` |
| Почтовый индекс | `locationPostcode` | `postal_code` |
| Координаты (общие) | `locationLat` / `locationLng` | `latitude` / `longitude` |
| Координаты (точные) | `exactLat` / `exactLng` | `exact_latitude` / `exact_longitude` |

### Laravel-контроллер (`PropertyApiController.php`)

`store()` принимает и сохраняет `latitude`, `longitude`, `district`, `postal_code` (все в `$validated` и `Property::create()`).  
Раньше latitude/longitude не были в validation → молча игнорировались → NULL в DB.

### Отображение в card.html

- Оранжевый subtitle: `prop-city-link` / `prop-district-link`
- Строка Area в SPECIFICATIONS: `specRow('Area', p.district)`
- Если `p.district` пустой → `<li>` с районом скрывается автоматически

### ⚠️ Что НЕ работает (ограничения Google API)

- Поиск по **только почтовому индексу** (напр. "SW1W 9QJ") → Google не возвращает район ни в компонентах, ни в formatted_address. Для точного района нужно вводить название района ("Belgravia") или конкретную улицу.
- API ключ ограничен по домену (browser only) → сервер-сайд reverse geocoding недоступен.

### Существующие объявления с NULL district

Объявления, созданные **до** этих фиксов (approx. до апреля 2026, ID < 35) имеют `district=NULL`. Исправить можно только пересоздав объявление. Или вручную через MySQL: `UPDATE properties SET district='Peckham' WHERE id=33;`

---

## Коммуникация

Общаться с пользователем на русском языке.

## Production Deployment Notes

### Важно: два разных места для файлов!
- **server.py** → `/var/www/bazar-prod/server.py` (КОРЕНЬ)
- **index.html** → `/var/www/bazar-prod/index.html` ← **Python SITE_ROOT читает отсюда!**
  - Также копировать в `/var/www/bazar-prod/public/index.html` (nginx статика)
- **Остальные HTML** (card.html, search.html, cabinet.html и др.) → `/var/www/bazar-prod/public/`
  - Python для них тоже читает из SITE_ROOT (`/var/www/bazar-prod/`), но туда приходят через `/var/www/bazar-prod/public/` по-другому. Лучше копировать в ОБОИХ местах.
- **JS/CSS** → `/var/www/bazar-prod/public/js/` и `/var/www/bazar-prod/public/css/` (только nginx)
- **Restart**: `ssh root@49.13.231.137 "systemctl restart bazar-seo"`
- **Systemd**: `ExecStart=/usr/bin/python3 /var/www/bazar-prod/server.py`, `WorkingDirectory=/var/www/bazar-prod`
- **SITE_ROOT** = `os.path.dirname(os.path.abspath(__file__))` = `/var/www/bazar-prod/`
  (НЕ `/var/www/bazar-prod/public/`! Это была ошибка в прошлой документации)
