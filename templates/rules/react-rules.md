---
trigger: glob
globs: "**/*.tsx, **/*.jsx"
description: React component rules — CVA class order, module architecture boundaries.
---

# React Rules

## CVA Class Order

When using `class-variance-authority`, merge variant classes first and append consumer `className` last. This ensures consumer overrides apply predictably.

**Incorrect:**

```tsx
<span className={cn(className, badgeVariants({ theme, size }))} />
```

**Correct:**

```tsx
<span className={cn(badgeVariants({ theme, size }), className)} />
```

## Module Architecture

Organize source code into bounded layers with strict import direction:

- `libs/` — app-agnostic reusable libraries. No domain knowledge.
- `modules/` — domain-sliced feature modules. Each owns its own state, side effects, and integration. Recommended internal slices: `presentation/`, `core/`, `integration/`, `domain/`.
- `shared/` — domain-sliced reusable modules. Consumable by `modules/` and `core/`. Must not depend on any concrete module.
- `core/` — composition root: bootstrapping, routing, guards, and module wiring.

**Import rules:**

- `modules/` → `shared/`, `libs/` only.
- `shared/` → `libs/` only.
- `core/` → `modules/`, `shared/`, `libs/`.
- No direct imports between modules. Cross-module communication goes through events, orchestrators, shared contracts, or core-level composition.

Each module exposes a stable public surface via its `index.ts`. Consumers import only from there.

**Incorrect:**

```ts
// inside modules/billing/
import { UserStore } from '../auth/core/store';
```

**Correct:**

```ts
// inside modules/billing/
import { UserStore } from 'shared/user';
```

This pattern applies only to domain features with owned state, async operations, or backend integration. Pure UI components, generic utilities, and layout shells do not need it.
