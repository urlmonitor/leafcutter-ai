---
trigger: glob
globs: "**/*.ts, **/*.tsx, **/*.mts, **/*.cts"
description: TypeScript coding rules — no enums, exhaustive branching, branded domain types.
---

# TypeScript Rules

## No Enums

Do not use `enum` or `const enum`. Prefer type literals / union literals for type modeling and raw JavaScript objects (`as const`) for value maps.

**Incorrect:**

```ts
enum UserRole {
  Admin = "admin",
  Member = "member",
}

const enum ApiStatus {
  Idle,
  Loading,
  Success,
  Error,
}
```

**Correct:**

```ts
export const USER_ROLE = {
  ADMIN: "admin",
  MEMBER: "member",
} as const;

export type UserRole = (typeof USER_ROLE)[keyof typeof USER_ROLE];

export const API_STATUS = {
  IDLE: "idle",
  LOADING: "loading",
  SUCCESS: "success",
  ERROR: "error",
} as const;

export type ApiStatus = (typeof API_STATUS)[keyof typeof API_STATUS];
```

## Exhaustive Branching

When handling discriminated unions with multiple variants, always make the logic exhaustive.

- Use `switch` with a `never` exhaustive check in `default`.
- For renderer/handler maps, use `Record<UnionType, ...>` so every variant is implemented.
- Use the same rule for discriminated objects (`kind` / `type` / `disc` properties).
- Do not leave branches implicit or rely on a fallback for unknown variants.

**Incorrect:**

```ts
type DrawMethod = "line" | "circle" | "rectangle";

const drawByMethod = (method: DrawMethod) => {
  switch (method) {
    case "line":
      return drawLine();
    case "circle":
      return drawCircle();
    default:
      return drawPlaceholder();
  }
};
```

**Correct:**

```ts
type DrawMethod = "line" | "circle" | "rectangle";

const drawByMethod = (method: DrawMethod) => {
  switch (method) {
    case "line":
      return drawLine();
    case "circle":
      return drawCircle();
    case "rectangle":
      return drawRectangle();
    default: {
      const _exhaustiveCheck: never = method;
      return _exhaustiveCheck;
    }
  }
};

const DRAW_MAP: Record<DrawMethod, () => void> = {
  line: drawLine,
  circle: drawCircle,
  rectangle: drawRectangle,
};
```

## Branded Domain Types

For domain values, prefer branded types over raw primitives. Avoid primitive obsession (`string`, `number`) for domain identifiers, quantities, and units.

**Incorrect:**

```ts
const transfer = (fromAccountId: number, toAccountId: number, amount: number) => {
  return payments.transfer(fromAccountId, toAccountId, amount);
};
```

**Correct:**

```ts
type Brand<TValue, TBrand extends string> = TValue & { readonly __brand: TBrand };

type AccountId = Brand<number, "AccountId">;
type MoneyAmount = Brand<number, "MoneyAmount">;

const toAccountId = (value: number): AccountId => value as AccountId;
const toMoneyAmount = (value: number): MoneyAmount => value as MoneyAmount;

const transfer = (fromAccountId: AccountId, toAccountId: AccountId, amount: MoneyAmount) => {
  return payments.transfer(fromAccountId, toAccountId, amount);
};
```

Keep raw primitives at boundaries (transport, parsing, persistence), then convert once into branded domain types.
