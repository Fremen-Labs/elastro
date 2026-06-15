---
name: elastro-gui-design-tokens
description: >
  Elastro GUI design tokens: dark-first Hawkins-inspired HSL variables, typography
  scale, spacing, shadows, health semantics, and motion. Use when theming Elastro
  GUI, adding CSS variables, or aligning components to Netflix/Hawkins visual
  standards.
---

# Elastro GUI Design Tokens

Source of truth: `packages/gui/src/style.css` (`:root` block). Tokens use **HSL without wrapper** so consumers write `hsl(var(--token))`.

## 1. Theme default

**Dark-first** for operator sessions. Light theme via `@media (prefers-color-scheme: light)` override — not the default `:root`.

## 2. Color tokens

### Canvas & surfaces
| Token | Dark default | Role |
|-------|--------------|------|
| `--background` | `0 0% 8%` (~#141414) | Main canvas |
| `--foreground` | `0 0% 96%` | Primary text |
| `--card` | `0 0% 11%` (~#1c1c1c) | Card surface |
| `--muted` | `0 0% 14%` | Subtle fills, chips |
| `--muted-foreground` | `0 0% 63%` | Secondary text |
| `--border` | `0 0% 18%` | Dividers |
| `--surface-raised` | `0 0% 16%` | Mono value chips |

### Brand & interactive
| Token | Value | Role |
|-------|-------|------|
| `--primary` | `0 89% 47%` (#E50914) | CTAs, nav accent |
| `--primary-foreground` | `0 0% 100%` | Text on primary |
| `--ring` | `0 89% 47%` | Focus rings |
| `--nav-active-bg` | `0 89% 47% / 0.12` | Sidebar active fill |

### Elasticsearch health (semantic)
| Token | HSL | ES mapping |
|-------|-----|------------|
| `--health-green` | `152 69% 40%` | green |
| `--health-yellow` | `45 93% 47%` | yellow |
| `--health-red` | `0 72% 51%` | red |
| `--health-offline` | `0 0% 45%` | offline, unknown |

### Feedback
| Token | Role |
|-------|------|
| `--destructive` | Errors (may match `--health-red`) |
| `--success` | Positive confirmations |
| `--warning` | Non-fatal cautions |
| `--info` | Neutral informational |

## 3. Typography

```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
```

| Class / element | Size | Weight |
|-----------------|------|--------|
| Page `h1` | 2rem | 700 |
| Card `h2` | 1.25rem | 600 |
| Eyebrow `.label-caps` | 0.75rem | 500, uppercase, 0.08em tracking |
| Body | 0.875rem | 400 |
| Stat value | 2.5rem | 700 |

## 4. Spacing & radius

| Token | Value |
|-------|-------|
| `--radius` | `0.5rem` (8px — tighter than prior 12px, Hawkins pro density) |
| `--radius-lg` | `0.75rem` |
| Page padding | `2.5rem` horizontal |
| Card padding | `1.5rem` |
| Grid gap | `1.5rem` |

## 5. Elevation & glass

| Token | Usage |
|-------|-------|
| `--shadow-sm` | Resting cards |
| `--shadow-md` | Hover cards |
| `--shadow-lg` | Modals, dropdowns |
| `--glass-bg` | Sidebar: `hsl(var(--card) / 0.85)` + `backdrop-filter: blur(16px)` |
| `--gradient-hero` | Subtle radial vignette on `.main-content` |

## 6. Motion

| Pattern | Duration | Easing |
|---------|----------|--------|
| Hover lift | 200ms | ease |
| Page fade | 200ms | ease |
| Skeleton shimmer | 2s | linear infinite |
| Health pulse | 2s | infinite (red/offline only) |

```css
@media (prefers-reduced-motion: reduce) {
  /* disable shimmer animation, shorten transitions */
}
```

## 7. Global utility classes (style.css)

Reuse these — do not redefine in scoped Vue CSS:

- `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-outline`
- `.card`, `.glass-panel`
- `.skeleton*`
- `.label-caps`
- `.text-destructive`, `.text-success`, `.text-muted`
- `.focus-ring` (for custom interactive elements)

## 8. Adding new tokens

1. Add to `:root` (dark default)
2. Mirror in `prefers-color-scheme: light` if contrast needs adjustment
3. Document in this skill if semantic (not one-off)
4. Never hardcode hex in Vue scoped styles — reference `hsl(var(--token))`