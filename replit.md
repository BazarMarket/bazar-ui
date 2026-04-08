# Bazar UI

A static HTML/CSS/JS classified ads marketplace website UI.

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

## CSS Versioning

**Текущая версия: main.css?v=95** (обновлять при каждом изменении CSS)
icon-style.css?v=2

Обновлять версию в: dev-index.html, card.html, search.html, cabinet.html

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
- `POST /api/stripe/webhook` — webhook от Stripe

### Планы (config/stripe.php)
- PRO: £7.00 / 30 дней
- VIP: £14.00 / 30 дней

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

### Правило при добавлении нового функционала

- Если функционал **только для DEV** — оборачивай в `<div id="devXxx">`, скрывай через продакшн-скрипт
- Если функционал **только для PROD** — оборачивай в `<div id="prodXxx" style="display:none">`, показывай через продакшн-скрипт
- Продакшн-скрипт всегда в самом конце перед `</body>`

## Коммуникация

Общаться с пользователем на русском языке.
