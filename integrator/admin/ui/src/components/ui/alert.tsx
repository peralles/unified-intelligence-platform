import { cn } from "@/lib/utils";
import type { Tone } from "@/types";

const tones: Record<Tone, string> = {
  "": "border-border bg-secondary/30",
  ok: "border-success/30 bg-success/10 text-success",
  warn: "border-warning/30 bg-warning/10 text-warning",
  err: "border-destructive/30 bg-destructive/10 text-destructive",
  info: "border-primary/30 bg-primary/10 text-primary",
};

export function Alert({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: Tone;
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border px-4 py-3 text-sm",
        tones[tone],
        className,
      )}
      role="status"
    >
      {title ? <p className="mb-1 font-semibold">{title}</p> : null}
      <div className="text-foreground/90">{children}</div>
    </div>
  );
}

export function StatusBanner({
  tone,
  children,
}: {
  tone: Tone;
  children: React.ReactNode;
}) {
  return (
    <Alert tone={tone} className="mb-4">
      {children}
    </Alert>
  );
}
