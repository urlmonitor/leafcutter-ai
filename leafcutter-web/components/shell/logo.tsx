import * as React from "react";
import { cn } from "@/lib/utils";

/** Leafcutter mark — a cut leaf with a vein, drawn in the brand gradient. */
export function LeafMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      className={cn("h-7 w-7", className)}
      aria-hidden
    >
      <defs>
        <linearGradient id="leaf-g" x1="4" y1="4" x2="28" y2="28" gradientUnits="userSpaceOnUse">
          <stop stopColor="hsl(150 64% 58%)" />
          <stop offset="1" stopColor="hsl(168 60% 42%)" />
        </linearGradient>
      </defs>
      {/* leaf body */}
      <path
        d="M26 6C14 6 6 14 6 26c0 0 0-.2 0 0 12 0 20-8 20-20z"
        fill="url(#leaf-g)"
      />
      {/* cut notch (leafcutter bite) */}
      <path d="M16 16c-2.4 2.4-5.2 3.6-8.4 3.9" stroke="hsl(160 40% 8%)" strokeWidth="1.6" strokeLinecap="round" />
      {/* central vein */}
      <path d="M25 7 8.5 23.5" stroke="hsl(160 40% 8%)" strokeWidth="1.4" strokeLinecap="round" opacity="0.55" />
    </svg>
  );
}
