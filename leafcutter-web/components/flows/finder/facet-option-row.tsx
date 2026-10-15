import { cn } from "@/lib/utils";

/**
 * One facet option: a checkbox, its label and the number of flows choosing it
 * alone would list. A zero option stays listed but disabled (so the panel never
 * reflows) unless it is ticked, which must stay possible to untick.
 */
export function FacetOptionRow({
  label,
  count,
  checked,
  onToggle,
}: {
  label: string;
  count: number;
  checked: boolean;
  onToggle: () => void;
}) {
  const disabled = count === 0 && !checked;
  return (
    <label
      className={cn(
        "flex cursor-pointer items-center justify-between gap-2 rounded px-1 py-0.5 text-[13px] transition-colors hover:bg-secondary/60 focus-within:bg-secondary/60",
        checked && "font-semibold text-primary",
        disabled && "cursor-not-allowed text-muted-foreground/70 hover:bg-transparent",
      )}
    >
      <span className="flex min-w-0 items-center gap-2">
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={onToggle}
          className="h-3.5 w-3.5 shrink-0 accent-[hsl(var(--primary))] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        />
        <span className="truncate">{label}</span>
      </span>
      <span className="font-mono text-xs text-muted-foreground">{count}</span>
    </label>
  );
}
