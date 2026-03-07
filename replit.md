# Bazar UI

A static HTML/CSS/JS classified ads marketplace website UI.

## Project Structure

- `index.html` - Main homepage
- `search.html` - Search results page
- `card.html` - Individual listing card
- `real-estate.html` - Real estate category page
- `components.html` - UI components showcase
- `css/` - Stylesheets (main.css, choices.min.css, swiper, etc.)
- `js/` - JavaScript files (script.js, swiper, choices, etc.)
- `img/` - Images
- `icon/` - SVG and PNG icons
- `fonts/` - Poppins font family + icon font
- `video/` - Background video files
- `#source/` - SCSS source files

## Running the Project

The project is served as a static site using Python's built-in HTTP server:

```
python3 -m http.server 5000 --bind 0.0.0.0
```

Workflow: "Start application" on port 5000 (webview)

## Deployment

- Replit dev preview: pike.replit.dev URL
- Published: bazar-ui.replit.app
- Production: www.bazar.uk (AlexHost, deploy via ZIP+FTP from GitHub)
- GitHub: BazarMarket/bazar-ui

## ВАЖНО — Что уже сделано (не откатывать!)

### card.html — шапка (.header-old):
- Логотип: `img/logo.png`, max-height: 60px, padding шапки: 8px 0
- Колокольчик (icon-notification) УБРАН — из шапки и мобильного меню
- Выбор языка EN/EL УБРАН — из шапки и мобильного меню
- Сайт только на английском, переключатель языка не нужен нигде
- 4 ячейки шапки: [+ POST AN AD] | [email + heart] | [£ 3 216] | [ALEXEY аватар]
- Разделители между ячейками через ::after (#e7e7e7, 2px, 40px); последняя ячейка без линии

### card.html — блок продавца (.card-name):
- Структура: 3 ряда через flexbox column, gap 5px
- Ряд 1 (.card-name__top): аватар 75px + звёзды/имя (max-width 170px)
- Ряд 2 (.card-name__bottom): иконки WA/TG/VB (22px, gap 4px) + "2 года на Grant Market"
- Ряд 3 (.card-name__links): "More ads" / "Edit ads"

### css/main.css — цвета:
- Основной оранжевый: #ff9138
- Telegram синий: #2aabee (сохранён)
- Цветовая схема НЕ менялась на синюю — остаётся оранжевой

### ВАЖНО — CSS-ловушка (запомнить для всех страниц!):
- Правило `.card-grid p { margin: 0 }` обнуляет отступы у ВСЕХ `<p>` внутри карточки
- Если меняешь margin/padding у элемента-`<p>` внутри `.card-grid` и изменение не работает — добавь `!important`
- Пример: `.card-head__title { margin: 0 0 15px 0 !important; }`
- Аналогично может быть и на других страницах — всегда проверяй специфичность

## Другие правки css/main.css:
- .container-full: max-width 1600px
- .container: max-width 1354px (footer)
- При max-width 1200px: card-grid__left shrinks 70% → 62%
- Паддинг ячеек таблицы: 10px 4px
- .card-head и .card-nav: margin-right 6% (выровнены по правому краю сайдбара)
- .card-price: align-items flex-end; .card-price__right: margin-right calc(10% - 28px)
- .card-price__right .price-last-old: font-size 22px; position relative; top -10px
- .card-head__edit: margin-right -7px; .header-old__right: margin-right 110px
- Все блоки правого сайдбара (.card-price, .card-btns, .card-options, .card-name): margin-right 20%

## Design Notes

- Color scheme: orange #ff9138 (primary), Telegram #2aabee (preserved)
- Tech stack: HTML/CSS/JS → future migration to Laravel + Blade + PostgreSQL + Filament admin
- Communicate in Russian with user
- Files use Windows line endings (\r\n) — use Python binary read/write for replacements
