---
trigger: glob
globs: "**/*.ts, **/*.tsx, **/*.js, **/*.jsx, **/*.mts, **/*.cts, **/*.mjs, **/*.cjs"
description: JavaScript/TypeScript style rules — arrow functions, object params, slim returns.
---

# JavaScript Style Rules

## Arrow Functions Only

Always use arrow functions. Never use `function` declarations or `function` expressions — this applies to top-level utilities, React components, event handlers, callbacks, and registry streams.

Arrow functions must always be assigned to a `const`.

**Incorrect:**

```ts
function calculateTotal(items) {
  return items.reduce((sum, item) => sum + item.price, 0);
}

array.map(function (item) {
  return transform(item);
});
```

**Correct:**

```ts
const calculateTotal = (items) =>
  items.reduce((sum, item) => sum + item.price, 0);

array.map((item) => transform(item));
```

## Object Parameters

When a function takes 3 or more inputs, pass a single object parameter instead of positional arguments. Named properties make call sites self-documenting and resilient to argument-order bugs.

**Incorrect:**

```ts
const createChart = (
  width: number,
  height: number,
  color: string,
  showLegend: boolean,
) => {
  return renderChart(width, height, color, showLegend);
};

createChart(1200, 600, "#1f8fff", true);
```

**Correct:**

```ts
const createChart = ({
  width,
  height,
  color,
  showLegend,
}: {
  width: number;
  height: number;
  color: string;
  showLegend: boolean;
}) => {
  return renderChart(width, height, color, showLegend);
};

createChart({
  width: 1200,
  height: 600,
  color: "#1f8fff",
  showLegend: true,
});
```

For 1-2 simple arguments, positional parameters are still acceptable.

## Slim Returns

Use the shortest syntax possible. Omit `return` and braces when the body is a single expression.

**Incorrect:**

```tsx
const fn = () => {
  return result;
};

const Component = () => {
  return <div></div>;
};
```

**Correct:**

```tsx
const fn = () => result;

const Component = () => <div></div>;
```
