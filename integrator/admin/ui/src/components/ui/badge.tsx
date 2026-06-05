import { cn } from "@/lib/utils";
import type { Tone } from "@/types";

const tones: Record<Tone, string> = {
  "": "bg-secondary/40 border-border text-foreground",
  ok: "bg-success/10 border-success/30 text-success",
  warn: "bg-warning/10 border-warning/30 text-warning",
  err: "bg-destructive/10 border-destructive/30 text-destructive",
  info: "bg-primary/10 border-primary/30 text-primary",
};

export function Badge({
  tone = "",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
