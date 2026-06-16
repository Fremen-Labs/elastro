# Netflix Hawkins → Elastro GUI Synthesis

Research distilled from Netflix Tech Blog (Hawkins), public Hawkins documentation, and Netflix consumer/professional UI patterns. Elastro adapts the **Professional** track with selective **Consumer** cinematic cues.

## Hawkins core philosophy

| Principle | Hawkins intent | Elastro adaptation |
|-----------|----------------|-------------------|
| Tokens first | Single source of truth for color, type, space | HSL CSS variables in `packages/gui/src/style.css` |
| Components over pages | Reusable primitives in Storybook/Figma | `packages/gui/src/components/ui/` |
| Dual tracks | Consumer (TV/web) vs Professional (internal) | **Professional** density + **Consumer** dark shell |
| Guidance over governance | Patterns, not rigid enforcement | Skills document defaults; PRs may diverge with reason |
| Loading honesty | Skeleton shimmer, no blank flashes | `.skeleton` classes on all async surfaces |
| Content-forward | UI chrome recedes; content is hero | Metrics, cluster cards, terminal dominate viewport |

## Consumer track cues (restrained for ops)

- **Dark canvas**: near-black backgrounds (`#141414`–`#181818` family), not pure `#000`
- **Typography hierarchy**: large page titles, uppercase eyebrow labels, mono for technical values
- **Browse-card affordance**: hover lift, focus ring, chevron reveal on row cards
- **Cinematic depth**: subtle radial vignette on main canvas, soft elevation shadows
- **Brand accent**: Netflix red `#E50914` for primary CTAs only — not for ES health semantics

## Professional track cues (primary for Elastro)

- **Information density**: tables, stat grids, inline badges without decorative chrome
- **Semantic status colors**: green/yellow/red map to cluster health, independent of brand red
- **Operational clarity**: errors surface in `AlertBanner`; empty states include next-step CTA
- **Keyboard/focus**: `focus-visible` rings on all interactive elements
- **Reduced motion**: respect `prefers-reduced-motion` for shimmer and page transitions

## UX patterns checklist

### Page structure
1. `PageHeader` — optional eyebrow, `h1` title, muted description, optional actions slot
2. `AlertBanner` — error/warning/success/info above main content
3. Content region — cards, grids, or tables
4. `EmptyState` — icon, headline, body, primary CTA when list is empty

### Cluster health
- Use `StatusBadge` with `variant="health"` and ES health string (`green`, `yellow`, `red`, `offline`)
- Pulse animation only on `red` and `offline`
- Never use brand red for healthy/green states

### Loading
- Show skeleton placeholders matching final layout geometry
- Keep prior data visible during refresh when possible (stale-while-revalidate)

### Navigation
- Sidebar: icon + label, active state with left accent bar (not full fill)
- Page transitions: short fade + 10px Y translate (disable under reduced motion)

## Anti-patterns

- Light-first theme for ops dashboard (fatigue on long sessions)
- Gradient text on body copy or table cells
- Brand red on warning/yellow health states
- Inline SVG duplication when `lucide-vue-next` icon exists
- Per-view duplicate `.page-header` / `.error-banner` CSS — use shared components + tokens

## References

- Netflix Tech Blog: Hawkins design system reasoning
- Hawkins: Figma + Storybook component library (internal/professional tracks)
- Netflix brand: `#E50914`, dark UI backgrounds on tv.netflix.com