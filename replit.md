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

Configured as a static deployment with `publicDir: "."`.

## Design Notes

- Color scheme: orange `#ff9138` (primary), Telegram `#2aabee` (preserved)
- `container-full`: max-width 1600px, padding 0 32px
- `container`: max-width 1354px (footer)
- At max-width 1200px: `card-grid__left` shrinks from 70% to 62%
- Table cell padding: `10px 4px` (reduced horizontal)

### card.html — seller block (`.card-name`) layout:
- Row 1 (`.card-name__top`): avatar 75px + stars/name (max-width 170px) side by side
- Row 2 (`.card-name__bottom`): small icons WA/TG/VB (22px, 4px gap) + "2 года на Grant Market"
- Row 3 (`.card-name__links`): "More ads" + "Edit ads"
