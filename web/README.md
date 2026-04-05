# Material Design UI Structure

This folder contains the Material Design 3 based UI system for offline use.

## 📁 Folder Structure

```
web/
├── index.html                  # Main HTML file
├── css/
│   ├── main.css               # Main stylesheet (imports all)
│   ├── material-design.css    # MD3 color system & tokens
│   ├── typography.css         # Typography scale
│   └── components/
│       ├── buttons.css        # Button components
│       ├── cards.css          # Card components
│       ├── forms.css          # Form controls
│       └── chips.css          # Chips & badges
├── js/
│   └── components/
│       └── Ripple.js          # Ripple effect implementation
└── assets/
    └── icons/                 # SVG icons (future)
```

## 🎨 Design System

### Color Tokens
All colors follow Material Design 3 specification:
- Primary, Secondary, Tertiary colors
- Surface & background colors
- Error states
- State layer opacities

### Typography
System font stack for offline compatibility:
- Display, Headline, Title, Body, Label scales
- Proper letter-spacing and line-height

### Elevation
5 levels of shadows for depth:
- Level 0-5 with consistent shadow values

### Components
- **Buttons**: Filled, Tonal, Outlined, Text, FAB, Icon
- **Cards**: Elevated, Filled, Outlined
- **Forms**: Text fields, Select, Slider
- **Chips**: Assist, Filter, Badge

## 🔧 Usage

### In HTML
```html
<!-- Import main CSS -->
<link rel="stylesheet" href="css/main.css">

<!-- Use Material Design buttons -->
<button class="md-btn md-btn-filled">Primary Action</button>
<button class="md-btn md-btn-tonal">Secondary</button>
<button class="md-btn md-btn-outlined">Outlined</button>

<!-- Use cards -->
<div class="md-card md-card-elevated">
  <div class="md-card-header">
    <span class="md-card-header-title">Card Title</span>
  </div>
  <div class="md-card-content">
    Card content here
  </div>
</div>
```

### Ripple Effect
```html
<!-- Import Ripple JS -->
<script src="js/components/Ripple.js"></script>

<!-- Ripple is automatic on .md-btn elements -->
<button class="md-btn md-btn-filled">Click me!</button>
```

## 🌈 Themes

Four themes supported via `data-theme` attribute:
- Default (Purple)
- Warm (Orange/Purple)
- Cool (Cyan)
- Dark

```html
<html data-theme="dark">
```

## 🚀 Future Migration to React/Vue

The component-based structure makes migration easy:

1. Each CSS component → React/Vue component
2. CSS variables → Theme provider
3. Ripple.js → React hook / Vue composable
4. HTML structure → JSX / Template

Example React component:
```jsx
import '../css/components/buttons.css';

function Button({ variant, children, ...props }) {
  return (
    <button className={`md-btn md-btn-${variant}`} {...props}>
      {children}
    </button>
  );
}
```

## 📝 Notes

- **Offline-first**: No CDN dependencies
- **Zero build tools**: Pure CSS/JS
- **Component-based**: Easy to maintain and migrate
- **Accessible**: Follows WCAG guidelines
- **Responsive**: Works on all screen sizes
