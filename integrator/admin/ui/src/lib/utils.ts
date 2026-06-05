import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export async function withLoading<T>(
  setLoading: (v: boolean) => void,
  fn: () => Promise<T>,
): Promise<T | undefined> {
  setLoading(true);
  try {
    return await fn();
  } finally {
    setLoading(false);
  }
}
