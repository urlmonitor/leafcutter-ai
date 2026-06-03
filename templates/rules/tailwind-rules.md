---
trigger: glob
globs: "**/*.tsx, **/*.jsx, **/*.html"
description: Tailwind CSS rules — modern syntax for arbitrary values and CSS custom properties.
---

# Tailwind Rules

## Modern Arbitrary Value Syntax

Use the parenthesis syntax for CSS custom properties in Tailwind, not the bracket+var syntax.

**Incorrect:**

```tsx
className="z-[var(--z-sidebar-backdrop)]"
className="var(--color-600-roche-blue)"
```

**Correct:**

```tsx
className="z-(--z-sidebar-backdrop)"
className="bg-(--my-custom-color)"
```
