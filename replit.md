# Bazar UI

A static HTML/CSS/JS classified ads marketplace website UI that will eventually migrate to Laravel.

## Run & Operate

- **Run Server:** `python3 server.py` (custom Python HTTP server with `Cache-Control: no-cache` on port 5000)
- **Deployment to Production:**
  - `scp -i .local/ssh/bazar_deploy server.py root@49.13.231.137:/var/www/bazar-prod/server.py`
  - `scp -i .local/ssh/bazar_deploy <html_file> root@49.13.231.137:/var/www/bazar-prod/public/<html_file>`
  - `ssh -i .local/ssh/bazar_deploy root@49.13.231.137 "systemctl restart bazar-seo"`
- **Environment Variables:**
  - `STRIPE_SECRET_KEY` (for `server.py` in dev)
  - `GEMINI_API_KEY` (for `server.py` and Laravel)
  - `BAZAR_SITE_ROOT` (for Python SEO server, `/var/www/bazar-prod/public/`)
- **Key Files:**
  - `/var/www/bazar-prod/server.py`
  - `/var/www/bazar-prod/public/index.html`
  - `/var/www/bazar-prod/public/css/main.css`
  - `/var/www/bazar-prod/public/js/script.js`
- **Database (Production):** `bazar_dev`
- **Database (Development):** `bazar_prod`
- **DO NOT TOUCH DEV ENVIRONMENT:** Agent works ONLY with production (`/var/www/bazar-prod/`). Development environment (`/var/www/bazar-dev/`, `dev.bazar.uk`, `bazar_prod` DB) is for user manual updates via `bash dev.sh` only.

## Stack

- **Frontend:** HTML, CSS, JavaScript (Vanilla JS, Swiper, Choices.js)
- **Backend (SEO/API Gateway):** Python 3 (`server.py`)
- **Backend (Admin/API):** Laravel + Filament (future migration)
- **Database:** MySQL
- **Build Tool:** N/A (static assets directly deployed)
- **Runtime:** Python 3, PHP 8.3 (for Laravel)

## Where things live

- `index.html`, `search.html`, `card.html`, `cabinet.html`, `real-estate.html`, `components.html`, `post-ad.html` - Core HTML pages
- `css/` - Stylesheets
  - Source-of-truth: `#source/` (SCSS files)
- `js/` - JavaScript files (`script.js`, `firebase-auth.js`, `error-logger.js`, `header-auth.js`)
- `img/` - Images
- `icon/` - SVG and PNG icons
- `fonts/` - Poppins font family + icon font
- `video/` - Background video files
- `server.py` - Custom Python HTTP server
- **Database Schema:** Defined implicitly by Laravel migrations in `bazar-dev/database/migrations/`
- **API Contracts:** Python `server.py` for `/api` endpoints (dev/Replit), Laravel for `admin.bazar.uk/api` (production)
- **Configuration:** `.env` files for Laravel, `config/stripe.php` for Stripe settings

## Architecture decisions

- **Production/Development Environment Isolation:** Strict separation of production and development environments. The agent operates solely on production.
- **Dynamic API Routing:** `window.BAZAR_API` in JavaScript files dynamically points to `admin.bazar.uk/api` in production and `'/api'` (handled by Python server) in dev/Replit, ensuring environment independence.
- **SEO-friendly URLs:** A custom Python SEO server (`server.py`) handles URL rewriting for listings (`/{id}-{slug}` format) and redirects legacy URLs.
- **Unified `cabinet.html`:** A single `cabinet.html` file is used across all environments, with a production-specific JavaScript block at the end to dynamically hide/show elements based on `window.location.hostname`.
- **District Extraction Algorithm:** A multi-pass algorithm in JavaScript for extracting accurate district information from Google Maps API `address_components` and `formatted_address` to populate the `district` field.

## Product

- **Classified Ads Marketplace:** Users can browse, search, and post advertisements.
- **User Accounts:** Registration, login, and session management with Firebase authentication.
- **Admin Panel:** Filament-based admin interface for managing tickets, users, and other data (Laravel).
- **Payment Processing:** Stripe integration for PRO/VIP plans, Boost to Top feature, and seller Connect accounts.
- **Support Ticket System:** Users can create support tickets, with AI-powered initial responses (Gemini 1.5 Flash).
- **Responsive UI:** Adapts to various screen sizes with defined breakpoints.
- **SEO Optimization:** Canonical URLs, sitemap generation, and structured URLs for listings.
- **Error Logging:** Frontend error logging to a `system_errors` table via a public API endpoint.

## User preferences

- **"ШАГ НАЗАД" = ТОЛЬКО ПОСЛЕДНЕЕ ИЗМЕНЕНИЕ.** Если пользователь говорит "верни как было", "шаг назад", "отмени" — это значит отменить ТОЛЬКО последнее сделанное изменение. ЗАПРЕЩЕНО восстанавливать файлы из бекапов за несколько часов если пользователь об этом явно не просил. Не создавать бекапы самостоятельно без просьбы. Отмена = точечный revert конкретного изменения, а не откат всей сессии.
- **ВСЕГДА отвечать ТОЛЬКО на русском языке.** Никогда не писать на украинском, английском или другом языке. Только русский.
- **SMS рассылка — НИКОГДА не запускать самостоятельно.** Никаких `php artisan sms:send-property` и никаких других команд отправки без явного подтверждения пользователя. Только показывать команду и ждать команды "запускай" или "подтверждаю". Рассылка запускается батчами по 50, не всё сразу.
- **При деплое script.js на продакшн** — блок скрытия Wallet виджета в `js/script.js` должен сохраняться. **НЕ УДАЛЯТЬ**.
- **НИКОГДА не писать "Проверьте (Ctrl+Shift+R)"** в конце сообщений.

## SMS Рассылка (Twilio)

- **Файлы SMS:** `/var/www/bazar-dev/app/Filament/Resources/Leads/LeadResource.php` и `/var/www/bazar-dev/app/Console/Commands/SendSmsLeads.php`
- **ТОЧНЫЙ текст SMS (НЕ МЕНЯТЬ без явной просьбы пользователя):**
  `"Hi {$greeting}, saw your property listing. You can also post it on Bazar.uk for free if helpful: https://bazar.uk/post-ad"`
  *(1 сегмент при любом имени, ~113-131 символов)*
- **КРИТИЧНО — запрет на спецсимволы в тексте SMS:** НИКОГДА не использовать длинное тире `—`, умные кавычки `"` `"`, или любые не-ASCII символы. Только обычный дефис `-`, прямой апостроф `'`. Причина: спецсимволы переключают SMS в Unicode-режим (70 символов/сегмент вместо 160), что утраивает стоимость ($0.065 → $0.20 за SMS).
- **Имя:** если имя продавца ≥ 3 букв — используется имя, иначе "there". НЕ МЕНЯТЬ этот порог.
- **Отправка:** через Artisan-команду `php artisan sms:send-property` в фоне (nohup). НЕ отправлять синхронно — будет 504 Gateway Timeout.
- **Категория:** рассылка только по `category='property'`. НЕ смешивать с phone-лидами.

## Gotchas

- **Dev Environment:** NEVER copy, deploy, modify, or sync anything to `dev.bazar.uk`. The agent works ONLY on production.
- **Database Sync:** Database synchronization (`prod` → `dev`) is ONLY initiated by the user via `bash dev.sh`. Agent never interferes.
- **Laravel Config Cache:** Do NOT run `php artisan config:cache` on dev, as it breaks FPM pool environment variables.
- **Production `.env`:** Agent should NEVER touch `/var/www/bazar-prod/.env` or change production configuration without an explicit request.
- **`cabinet.html` Logic:** Do not change the production-specific JavaScript block in `cabinet.html` that hides/shows elements for `www.bazar.uk`.
- **Stripe Integration for `cabinet.html`:** Do not remove the JavaScript block in `js/script.js` (and `messages.html`) that hides the wallet widget on `www.bazar.uk`.
- **CSS `!important`:** `.card-grid p { margin: 0 }` overrides all `<p>` margins within cards; use `!important` if needed to maintain specific paragraph spacing.
- **Windows Line Endings:** When performing Python string replacements on files with Windows line endings (`\r\n`), use binary read/write.
- **CSS Versioning:** Increment version numbers in HTML files (e.g., `main.css?v=121`) to bust browser cache after CSS changes.
- **`post-ad.html` Label Alignment:** `.pa-field__label` must have `min-width: 155px; max-width: 155px; white-space: normal`. Do not alter this for specific fields, as it causes visual misalignment.
- **Property Titles:** Real estate titles follow a strict format (e.g., "2 Bedroom Villa for Sale"). Do not use creative or marketing names.
- **Price Formatting:** Follow the specified price formatting (e.g., `425,<sup>000</sup>£`) and color rules.
- **Free Plan Sorting:** Free plan listings are NOT boosted to the top for the owner; they are sorted only by activity date. This logic has been restored twice and should not be altered.
- **`search.html` List-view Spacing:** Do not increase `padding-bottom` for `.product` elements in list view; the user explicitly requested a tight layout.
- **Portrait Image Detection (`window._checkImgPortrait`):** Функция в `js/script.js` (перед блоком Wallet widget). Срабатывает ТОЛЬКО для портретных фото (высота > ширина × 1.05) — ставит `object-fit:contain` + серый фон `#888888` на родительский контейнер. Горизонтальные фото НЕ затрагиваются. Применяется в: `index.html` (Latest Updates grid + API block), `search.html` (grid + list view), `card.html` (big gallery + mini thumbnails). НЕ УДАЛЯТЬ и не менять логику без явной просьбы.
- **`post-ad.html` и `search.html` — `window.BAZAR_API` в `<head>`:** В самом начале `<head>` обоих файлов есть inline `<script>`, который определяет `window.BAZAR_API` и сразу вызывает `/is-admin` для показа admin-only категорий (Motors, Phones и т.д. с атрибутом `data-admin-only`). Этот inline-блок ОБЯЗАТЕЛЕН — без него `window.BAZAR_API` будет `undefined` в момент вызова (т.к. `script.js` загружается позже, в теле страницы). НЕ УДАЛЯТЬ и не переносить этот блок. На продакшне `/is-admin` требует активной сессии на `admin.bazar.uk`; в dev (`server.py`) эндпоинт `/api/is-admin` всегда возвращает `{"admin":true}`. В `index.html` вызов `/is-admin` идёт после `script.js` — там проблемы нет.

## Pointers

- **Google AI Studio:** For Gemini API key generation: [https://aistudio.google.com/](https://aistudio.google.com/)
- **Stripe Dashboard:** For webhook registration and testing.
- **GitHub Repository:** BazarMarket/bazar-ui (for source code)
- **Replit Deployment:** bazar-ui.replit.app (public URL)
- **Production URL:** www.bazar.uk
- **Production Admin URL:** admin.bazar.uk
- **Systemd Service:** `/etc/systemd/system/bazar-seo.service` (for Python server)
- **Nginx Configuration:** `/etc/nginx/sites-enabled/bazar-dev` (for dev environment routing)