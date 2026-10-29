import { useSyncExternalStore } from "react";

export type Theme = "light" | "dark";

const KEY = "theme";

// index.html sets data-theme before the page draws, so there's no flash of the wrong colours
let current: Theme = document.documentElement.dataset.theme === "light" ? "light" : "dark";
const listeners = new Set<() => void>();

export function setTheme(theme: Theme) {
  current = theme;
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    // private windows can block storage; the theme just won't be remembered
  }
  listeners.forEach((l) => l());
}

/** The current theme. Components using it redraw when it changes. */
export const useTheme = () =>
  useSyncExternalStore((l) => {
    listeners.add(l);
    return () => listeners.delete(l);
  }, () => current);

/** A colour from style.css, e.g. themeColor("text"), for things drawn outside CSS like the graph. */
export const themeColor = (name: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
