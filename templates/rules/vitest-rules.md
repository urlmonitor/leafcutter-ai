---
trigger: glob
globs: "**/*.test.ts, **/*.test.tsx, **/*.spec.ts, **/*.spec.tsx, **/*.test.js, **/*.test.jsx, **/*.spec.js, **/*.spec.jsx"
description: Vitest/Testing Library rules — await promises, specific matchers, type narrowing, type testing, implicit assertions.
---

# Vitest Rules

## Await Promises

Always `await` promise resolutions before asserting. Missing `await` causes assertions to run against a `Promise` object instead of the resolved value, leading to false positives.

**Incorrect:**

```ts
it("fetches data", () => {
  const result = fetchData();
  expect(result).toEqual({ name: "Alice" }); // asserts against Promise object
});
```

**Correct:**

```ts
it("fetches data", async () => {
  const result = await fetchData();
  expect(result).toEqual({ name: "Alice" });
});
```

## Specific Matchers

Always use the most specific `expect` matcher available. Specific matchers provide better error messages and make test intent clearer.

**Incorrect:**

```ts
expect(ofType !== undefined).toBe(true);       // use toBeDefined()
expect($user.get()).toBe({ name: "Alice" });    // use toEqual() for objects
expect(typeof result.id === "string").toBe(true); // use typeof + toBe
```

**Correct:**

```ts
expect(ofType).toBeDefined();
expect($user.get()).toEqual({ name: "Alice" });
expect(typeof result.id).toBe("string");
```

## Type Narrowing in Tests

When asserting on discriminated union or conditional types, narrow the type with a guard before accessing type-specific properties. Do not use `as any` or `@ts-expect-error` to silence errors on property access.

**Incorrect:**

```ts
act(() => { result.current.on("test"); });
expect((result.current as any).data).toBe("test");
```

**Correct:**

```ts
act(() => { result.current.on("test"); });
expect(result.current.isOn).toBe(true);
if (result.current.isOn) {
  expect(result.current.data).toBe("test");
}
```

## Type Testing

Use Vitest's `expectTypeOf` for compile-time type assertions and `@ts-expect-error` for negative type tests. Do not use runtime checks to validate type behavior.

**Incorrect:**

```ts
it("requires value prop", () => {
  expect(typeof UserProvider).toBe("function");
});
```

**Correct:**

```ts
it("requires value prop in provider", () => {
  type ProviderProps = Parameters<typeof UserProvider>[0];
  expectTypeOf<ProviderProps>().toHaveProperty("children");
  expectTypeOf<ProviderProps>().toHaveProperty("value");
});
```

## Implicit Assertions (Testing Library)

When using Testing Library `getBy*` queries, do not wrap them in `expect(...).toBeInTheDocument()`. The `getBy*` queries already throw if the element is not found.

**Incorrect:**

```ts
expect(screen.getByText("Key Findings")).toBeInTheDocument();
```

**Correct:**

```ts
screen.getByText("Key Findings");
```

Use `expect` with `getBy*` only when checking properties beyond existence (e.g. `.toBeDisabled()`). Use `queryBy*` with `expect` for absence checks.
