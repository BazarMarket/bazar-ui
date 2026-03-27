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

## Login toggle (index.html)

- `doLogin()` — скрывает `#header-guest`, показывает `#header-logged-in`
- `doLogout()` — обратно

## Выравнивание контента

- `.container-full`: max-width 1600px, padding: 0 32px
- Секции внутри: `margin: 0 6%`
- Любой контент с `margin: 0 6%` ОБЯЗАН быть внутри `container-full` (padding: 0 32px)

## ⚠️ CSS-ловушки

- `.card-grid p { margin: 0 }` обнуляет отступы у ВСЕХ `<p>` внутри карточки — добавляй `!important`
- Файлы с Windows line endings (`\r\n`) — при Python-заменах использовать бинарное чтение/запись
- Браузерный кеш: версии CSS сбрасывают кеш; при проблемах → Ctrl+Shift+R

## Цвета

- Основной оранжевый: `#ff9138`
- Start Chat зелёный: `#3ecb60`
- Цена красная: CSS `red`
- Telegram синий: `#2aabee`

## Tech Stack

HTML/CSS/JS → future migration to Laravel + Blade + PostgreSQL + Filament admin (Hetzner CX22)

## Коммуникация

Общаться с пользователем на русском языке.
