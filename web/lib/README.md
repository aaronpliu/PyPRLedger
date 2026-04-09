# Frontend Libraries

This directory contains third-party JavaScript/CSS libraries used by the web interface.

## diff2html

- **Version**: 3.4.48
- **Source**: https://cdn.jsdelivr.net/npm/diff2html@3.4.48/
- **License**: MIT
- **Purpose**: Professional Git diff rendering (GitHub/GitLab style)

### Files
- `diff2html.min.css` - Stylesheet for diff display
- `diff2html-ui.min.js` - JavaScript library for rendering diffs

### Update Instructions
To update to a newer version:
```bash
cd web/lib
curl -o diff2html.min.css https://cdn.jsdelivr.net/npm/diff2html@<VERSION>/bundles/css/diff2html.min.css
curl -o diff2html-ui.min.js https://cdn.jsdelivr.net/npm/diff2html@<VERSION>/bundles/js/diff2html-ui.min.js
```

Or use the automated script:
```bash
./scripts/update_diff2html.sh <VERSION>
```

### Why Local?
These libraries are stored locally to support offline environments where CDN access is not available.
