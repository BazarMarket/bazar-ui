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

Сервер: `server.py` — кастомный Python HTTP server с `Cache-Control: no-cache` (чтобы браузер не кешировал старые файлы).

```
python3 server.py
```

Workflow: "Start application" on port 5000 (webview)

## Выравнивание контента на index.html

Подход такой же как в card.html:
- `<div class="index-body container-full">` — обёртка с padding: 0 32px (от container-full)
- Секции внутри (`.search`, `main`, `.menu-mob`) имеют `margin: 0 6%`
- 6% считается от ширины container-full content = (viewport − 64px) — точно так же как у логотипа
- Контейнеры внутри секций: `margin: 0; max-width: none; padding: 0`
- CSS версия: main.css?v=32

## ⚠️ ПОВТОРЯЮЩАЯСЯ ОШИБКА — читать ПЕРВЫМ делом при проблемах с выравниванием

**Проблема:** контент не выровнен с логотипом — блоки левее/правее шапки.

**Причина №1 — неправильная база для 6%:**
- Логотип: `margin-left: 6%` внутри `container-full` → 6% считается от `(viewport − 64px)`
- Если контент не в `container-full`, его 6% считается от полного viewport → всегда будет расхождение ~28px
- **Правило:** любой контент с `margin: 0 6%` ОБЯЗАН быть внутри `container-full` (или в элементе с `padding: 0 32px`)

**Причина №2 — CSS-правило перебивает container-full:**
- Если у обёртки стоит `padding: 0` (или любой другой padding) И на неё же навешен класс `container-full` — собственное правило CSS выиграет по каскаду (позднее в файле = приоритет при равной специфичности)
- Нужно либо убрать свой `padding`, либо не перекрывать `container-full`

**Причина №3 — браузерный кеш скрывает изменения:**
- Сервер теперь `server.py` с `Cache-Control: no-cache` — кеш отключён
- Если вдруг снова видно старую версию → попросить пользователя сделать Ctrl+Shift+R

**Быстрая диагностика:**
1. Сверить позицию блока с позицией логотипа в DevTools (Inspect → computed left)
2. Проверить: блок внутри `container-full`? → если нет, добавить
3. Проверить: нет ли CSS-правила которое перебивает `padding` у `container-full`?
4. Сверить с card.html — там заведомо правильное выравнивание

## Deployment

- Replit dev preview: pike.replit.dev URL
- Published: bazar-ui.replit.app
- Production: www.bazar.uk (AlexHost, deploy via ZIP+FTP from GitHub)
- GitHub: BazarMarket/bazar-ui

## ВАЖНО — Что уже сделано (не откатывать!)

### card.html — шапка (.header-old):
- Логотип: `img/logo.png`, max-height: 70px, padding шапки: 8px 0
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

## Текущие значения отступов (card.html):

### Единая система выравнивания — всё по 6% слева и справа:
- Логотип: `margin-left: 6%` (на .header-old .logo)
- Хлебные крошки (.bread-custom): `margin-left: 6%`
- .card-head, .card-nav: `margin: 0 6% / margin-left: 6%; margin-right: 6%`
- .card-grid__main: `margin: 0 6%`
- Тайлы сайдбара (.card-name, .card-price, .card-btns, .card-options): `margin-right: 0`
- Иконки хедера (.burger-body): `margin-right: 6%` в @media (min-width: 992px)
  - Последняя ячейка (.header-old__cell:last-child) имеет padding-right: 0
  - Значит аватар вплотную к .burger-body краю = точно 6% от правого края

### Прочее:
- .container-full: max-width 1600px, padding: 0 32px
- .container: max-width 1354px (footer)
- При max-width 1200px: card-grid__left shrinks 70% → 62%
- Паддинг ячеек таблицы: 10px 4px
- .btn_mini, .wallet-widget: white-space: nowrap (предотвращает перенос текста)

## Design Notes

- Color scheme: orange #ff9138 (primary), Telegram #2aabee (preserved)
- Tech stack: HTML/CSS/JS → future migration to Laravel + Blade + PostgreSQL + Filament admin
- Communicate in Russian with user
- Files use Windows line endings (\r\n) — use Python binary read/write for replacements
