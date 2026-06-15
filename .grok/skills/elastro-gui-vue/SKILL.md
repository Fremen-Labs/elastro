---
name: elastro-gui-vue
description: >
  Vue 3 + Vite patterns for Elastro GUI: shared UI components, composables, lucide
  icons, axios API calls with bearer token, and build-to-elastro/gui workflow. Use
  when implementing or refactoring Elastro GUI views, components, or frontend features.
---

# Elastro GUI — Vue 3 Patterns

Stack: Vue 3.5, TypeScript, Vite 7, vue-router (hash), axios, lucide-vue-next.

## 1. Project layout

```
packages/gui/src/
  App.vue              # Shell: sidebar, router-view, token extraction
  store.ts             # Reactive global state (token, clusters)
  style.css            # Design tokens + global utilities
  components/ui/       # Shared Hawkins primitives
  views/               # Route pages
  utils/               # Pure helpers (health colors, formatters)
```

Build: `npm run build` outputs to `elastro/gui/` (see `vite.config.ts` `outDir`).

## 2. Shared UI components

| Component | Path | Props |
|-----------|------|-------|
| `PageHeader` | `components/ui/PageHeader.vue` | `title`, `description?`, `eyebrow?` + `#actions` slot |
| `StatusBadge` | `components/ui/StatusBadge.vue` | `status`, `variant?: 'solid' \| 'outline'`, `pulse?` |
| `AlertBanner` | `components/ui/AlertBanner.vue` | `variant: 'error' \| 'warning' \| 'success' \| 'info'`, default slot |
| `EmptyState` | `components/ui/EmptyState.vue` | `title`, `description?` + `#icon`, `#actions` slots |

**Rule:** New views must use these instead of copying header/alert/empty markup.

## 3. Health helper

```typescript
// packages/gui/src/utils/health.ts
import { healthColor, healthPulse } from '../utils/health'
```

Use in views only when `StatusBadge` is insufficient (e.g. inline dots). Prefer the component.

## 4. API + auth pattern

```typescript
const apiBase = import.meta.env.VITE_API_URL || ''
await axios.get(`${apiBase}/api/clusters`, {
  headers: { Authorization: `Bearer ${state.token}` }
})
```

- Token injected in `App.vue` from URL `?token=`
- Poll for token in `onMounted` if child mounts before parent finishes
- Map 401 → user-facing "Invalid or missing security token"

## 5. Loading state pattern

```vue
<div v-if="loading"><!-- skeletons --></div>
<div v-else-if="error"><AlertBanner variant="error">{{ error }}</AlertBanner></div>
<div v-else-if="items.length"><!-- content --></div>
<EmptyState v-else ... />
```

## 6. Icons

Prefer lucide-vue-next for new icons:

```vue
<script setup lang="ts">
import { LayoutDashboard } from 'lucide-vue-next'
</script>
<template><LayoutDashboard :size="20" /></template>
```

Keep existing inline SVGs when not touching that file for other reasons.

## 7. Styling rules

- **Global tokens** in `style.css`; **layout-specific** in scoped `<style>`
- No Tailwind — project uses hand-rolled utility classes (`.w-1/2`, `.mt-4`, etc.)
- Transitions: `animate-fade-in` on page root div
- Router: hash mode — paths like `/#/cluster/name`

## 8. TypeScript

- `store.ts` types for `Cluster` shape
- Avoid `any` on new code; legacy views may retain `any` until typed incrementally
- Run `vue-tsc -b` via `npm run build` before shipping

## 9. Companion skills

- UX patterns: `elastro-gui-netflix-ux`
- Tokens: `elastro-gui-design-tokens`