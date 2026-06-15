---
name: elastro-gui-netflix-ux
description: >
  Hawkins-inspired Netflix UX patterns for Elastro's Vue GUI: dark cinematic shell,
  content-forward layouts, skeleton loading, semantic health states, browse-card
  affordances, and operational empty/error flows. Use when designing or reviewing
  Elastro GUI screens, UX uplift, or when the user mentions Netflix, Hawkins, or
  Elastro GUI UX.
---

# Elastro GUI — Netflix/Hawkins UX

Elastro is an **internal ops tool**. Follow Hawkins **Professional** density with selective **Consumer** dark-shell cues. Full research: `references/netflix-hawkins-synthesis.md`.

## 1. Page anatomy (every view)

```
PageHeader (eyebrow?, title, description, actions?)
AlertBanner? (error | warning | success | info)
Main content (grid | table | terminal)
EmptyState? (when list length === 0 and not loading)
```

Import from `packages/gui/src/components/ui/`.

## 2. Visual hierarchy

| Level | Treatment | Example |
|-------|-----------|---------|
| Page title | 2rem, weight 700 | "Dashboard" |
| Section title | 1.125rem, weight 600 | "Alerts (Unstable Indices)" |
| Eyebrow / label | 0.75rem, uppercase, letter-spacing | "TOTAL CLUSTERS" |
| Body | 0.875–1rem, `--muted-foreground` for secondary | Host, descriptions |
| Technical values | `--font-mono`, `--surface-raised` chip | `localhost:9200` |

## 3. Hawkins loading contract

- **Never** show empty layout while fetching — render skeletons with same dimensions as final UI
- Use `.skeleton`, `.skeleton-text`, `.skeleton-jumbo`, `.skeleton-badge` from global CSS
- Shimmer respects `prefers-reduced-motion: reduce` (static muted fill)

## 4. Browse-card pattern (cluster list, settings rows)

- Default: subtle border, `--shadow-sm`
- Hover: `translateY(-2px)`, border tint `--ring`, chevron fades in
- Active/pressed: slight scale down
- Focus-visible: 2px `--ring` outline offset 2px
- Entire card clickable when it navigates (`router-link` wrapper)

## 5. Semantic health (Elasticsearch)

| Health | Color token | Badge behavior |
|--------|-------------|----------------|
| green | `--health-green` | Solid fill |
| yellow | `--health-yellow` | Solid fill |
| red | `--health-red` | Solid + pulse |
| offline | `--health-offline` | Solid + pulse |

**Do not** map ES health to Netflix brand red (`--primary`). Brand accent is for CTAs and nav active accent only.

## 6. Alert and empty flows

| Situation | Component | Tone |
|-----------|-----------|------|
| API 401/5xx | `AlertBanner variant="error"` | Actionable message |
| Config saved | `AlertBanner variant="success"` | Auto-dismiss optional |
| No clusters | `EmptyState` + link to Settings | Primary CTA button |
| Destructive fix confirm | Native `confirm()` until modal component exists | Clear warning copy |

## 7. Sidebar navigation

- Dark glass panel, minimal width (~260px)
- Active item: left 3px `--primary` bar + `--nav-active-bg`, not full primary fill
- Token warning pinned to sidebar bottom
- Icons: prefer `lucide-vue-next` for new work

## 8. Review checklist (PR)

- [ ] Page uses `PageHeader` (not ad-hoc header CSS)
- [ ] Async paths have skeletons
- [ ] Health uses `StatusBadge`, not inline color logic
- [ ] Errors use `AlertBanner`
- [ ] Empty lists use `EmptyState` with CTA
- [ ] Focus-visible works on keyboard tab through nav/cards/buttons
- [ ] No new per-view duplicate of global token values

## 9. Companion skills

- Tokens: `elastro-gui-design-tokens`
- Vue implementation: `elastro-gui-vue`
- Build output: `cd packages/gui && npm run build` → `elastro/gui/`