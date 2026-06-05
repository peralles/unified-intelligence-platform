import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

function inlineFormat(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const token = m[0];
    if (token.startsWith("`")) {
      parts.push(
        <code
          key={key++}
          className="rounded bg-secondary/60 px-1 py-0.5 font-mono text-[0.85em]"
        >
          {token.slice(1, -1)}
        </code>,
      );
    } else if (token.startsWith("**")) {
      parts.push(<strong key={key++}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith("[")) {
      const link = /\[([^\]]+)\]\(([^)]+)\)/.exec(token);
      if (link) {
        parts.push(
          <a
            key={key++}
            href={link[2]}
            className="text-primary underline-offset-2 hover:underline"
            target="_blank"
            rel="noreferrer"
          >
            {link[1]}
          </a>,
        );
      }
    }
    last = m.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function MarkdownDoc({ source }: { source: string }) {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const nodes: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith("```")) {
      const code: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith("```")) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1;
      nodes.push(
        <pre
          key={key++}
          className="scrollbar-thin overflow-x-auto rounded-md border border-border bg-background p-4 font-mono text-xs leading-relaxed"
        >
          {code.join("\n")}
        </pre>,
      );
      continue;
    }

    if (/^#{1,3}\s/.test(line)) {
      const level = line.match(/^#+/)?.[0].length ?? 1;
      const text = line.replace(/^#+\s*/, "");
      const Tag = level === 1 ? "h1" : level === 2 ? "h2" : "h3";
      nodes.push(
        <Tag
          key={key++}
          className={cn(
            "font-semibold tracking-tight",
            level === 1 && "text-2xl",
            level === 2 && "mt-6 text-lg",
            level === 3 && "mt-4 text-base",
          )}
        >
          {inlineFormat(text)}
        </Tag>,
      );
      i += 1;
      continue;
    }

    if (/^\|.+\|$/.test(line.trim())) {
      const rows: string[][] = [];
      while (i < lines.length && /^\|.+\|$/.test(lines[i].trim())) {
        const row = lines[i]
          .trim()
          .slice(1, -1)
          .split("|")
          .map((c) => c.trim());
        if (!row.every((c) => /^[-:]+$/.test(c))) rows.push(row);
        i += 1;
      }
      if (rows.length) {
        const [head, ...body] = rows;
        nodes.push(
          <div key={key++} className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-secondary/30 text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  {head.map((h) => (
                    <th key={h} className="px-3 py-2 font-medium">
                      {inlineFormat(h)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {body.map((row) => (
                  <tr key={row.join("|")} className="border-b border-border/60 last:border-0">
                    {row.map((cell, ci) => (
                      <td key={ci} className="px-3 py-2 align-top">
                        {inlineFormat(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>,
        );
      }
      continue;
    }

    if (/^[-*]\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*]\s/, ""));
        i += 1;
      }
      nodes.push(
        <ul key={key++} className="list-disc space-y-1 pl-5 text-sm leading-relaxed">
          {items.map((item) => (
            <li key={item}>{inlineFormat(item)}</li>
          ))}
        </ul>,
      );
      continue;
    }

    if (/^\d+\.\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s/, ""));
        i += 1;
      }
      nodes.push(
        <ol key={key++} className="list-decimal space-y-1 pl-5 text-sm leading-relaxed">
          {items.map((item) => (
            <li key={item}>{inlineFormat(item)}</li>
          ))}
        </ol>,
      );
      continue;
    }

    if (!line.trim()) {
      i += 1;
      continue;
    }

    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^#/.test(lines[i]) && !/^```/.test(lines[i])) {
      if (/^[-*]\s/.test(lines[i]) || /^\d+\.\s/.test(lines[i]) || /^\|/.test(lines[i].trim()))
        break;
      para.push(lines[i]);
      i += 1;
    }
    nodes.push(
      <p key={key++} className="text-sm leading-relaxed text-foreground/90">
        {inlineFormat(para.join(" "))}
      </p>,
    );
  }

  return <article className="prose-invert max-w-3xl space-y-3">{nodes}</article>;
}
