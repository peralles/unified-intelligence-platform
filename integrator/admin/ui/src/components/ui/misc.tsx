import { cn } from "@/lib/utils";

export function Spinner({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "h-5 w-5 animate-spin rounded-full border-2 border-muted border-t-primary",
        className,
      )}
      role="status"
      aria-label="Carregando"
    />
  );
}

export function EmptyState({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border px-6 py-12 text-center">
      <p className="font-medium text-foreground">{title}</p>
      {description ? (
        <p className="mt-1 max-w-md text-sm text-muted">{description}</p>
      ) : null}
    </div>
  );
}

export function Checklist({ items }: { items: { label: string; status: string; detail?: string; hint?: string }[] }) {
  if (!items.length) return null;
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li
          key={item.label}
          className="flex items-start gap-3 rounded-md border border-border bg-background/50 px-3 py-2"
        >
          <StatusDot status={item.status} />
          <div className="min-w-0 flex-1">
            <p className="font-medium">{item.label}</p>
            {item.detail ? (
              <p className="text-xs text-muted">{item.detail}</p>
            ) : null}
            {item.hint ? (
              <p className="mt-1 text-xs text-muted-foreground">{item.hint}</p>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

function StatusDot({ status }: { status: string }) {
  const s = status.toLowerCase();
  const color =
    s === "ok" || s === "pass"
      ? "bg-success"
      : s === "warn" || s === "warning"
        ? "bg-warning"
        : s === "fail" || s === "error"
          ? "bg-destructive"
          : "bg-muted";
  return <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", color)} />;
}
