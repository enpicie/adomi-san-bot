# NEST Docs Site

Jekyll-based documentation site for the adomi-san-bot project.
Deployed to GitHub Pages at `https://enpicie.github.io/nest`.

## Structure

```
docs/
├── _config.yml           # Site settings and Jekyll config
├── _data/
│   └── nav.yml           # Navigation items — edit this to add/rename/remove nav links
├── _includes/
│   ├── head.html         # <head> meta tags, CSS imports
│   ├── header.html       # Sticky top nav bar (reads from _data/nav.yml)
│   └── footer.html       # Page footer
├── _layouts/
│   └── default.html      # Base HTML layout used by all pages
├── assets/
│   ├── css/main.css      # Custom prose, table, code, and component styles
│   └── ...               # Images and static files
└── *.md                  # Page content files
```

## Pages

| File | URL | Nav label |
| --- | --- | --- |
| `index.md` | `/nest/` | Home |
| `stream-setup.md` | `/nest/stream-setup` | Stream Setup |
| `commands.md` | `/nest/commands` | Commands |
| `adomin.md` | `/nest/adomin` | Adomin |

## Adding a page

1. Create `docs/your-page.md` with front matter:
   ```yaml
   ---
   layout: default
   title: Your Page Title
   ---
   ```
2. Add an entry to `docs/_data/nav.yml`:
   ```yaml
   - label: Your Page
     url: /your-page
   ```

That's all. The header picks it up automatically.

## Renaming a nav item

Edit the `label` field in `docs/_data/nav.yml`. The page file and URL do not need to change.

## Styling

- Layout and spacing use [Tailwind CSS](https://tailwindcss.com/) (loaded via CDN).
- Prose styles (headings, paragraphs, tables, code blocks, etc.) live in `assets/css/main.css` under the `.prose` selector.
- The GitHub button in the nav is styled separately from the regular nav links. Its URL is set via `github_url` in `_config.yml`.

## Local development

```bash
cd docs
bundle exec jekyll serve
```

The site rebuilds on file changes. `_site/` is the build output and is gitignored.
