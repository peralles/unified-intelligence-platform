import type { Tone } from "@/types";

let toastHandler: ((msg: string, kind?: Tone, dur?: number) => void) | null = null;

export function registerToast(handler: typeof toastHandler) {
  toastHandler = handler;
}

export function toast(msg: string, kind: Tone = "", dur?: number) {
  toastHandler?.(msg, kind, dur);
}

export async function api<T = Record<string, unknown>>(
  path: string,
  opts: RequestInit = {},
): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    ...opts,
  });
  const data = (await res.json().catch(() => ({}))) as T & {
    ok?: boolean;
    error?: string;
  };
  if (data.ok === false && data.error) {
    throw new Error(data.error);
  }
  if (!res.ok) {
    const msg =
      (data as { error?: string }).error ||
      `Erro HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}
