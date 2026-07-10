import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes with conflict resolution. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format an integer with locale grouping (e.g. 2022 -> "2,022"). */
export function fmt(n: number): string {
  return new Intl.NumberFormat("en-US").format(n);
}

/** Percentage 0-100 with no decimals, guarding divide-by-zero. */
export function pct(part: number, whole: number): number {
  if (!whole) return 0;
  return Math.round((part / whole) * 100);
}

/** Title-case a kebab/snake identifier: "build_pipeline" -> "Build Pipeline". */
export function humanize(id: string): string {
  return id
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
