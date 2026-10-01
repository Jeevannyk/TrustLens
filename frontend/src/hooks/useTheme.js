import { useCallback, useEffect, useState } from "react";

const KEY = "trustlens-theme";

function storedTheme() {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

function systemTheme() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// The inline script in index.html sets data-theme before first paint; this hook
// adopts that value, persists user choice, and follows the OS until the user chooses.
export default function useTheme() {
  const [theme, setTheme] = useState(
    () => document.documentElement.dataset.theme || storedTheme() || systemTheme(),
  );

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    const meta = document.querySelector('meta[name="theme-color"]');
    const bg = getComputedStyle(root).getPropertyValue("--bg").trim();
    if (meta && bg) meta.setAttribute("content", bg);
  }, [theme]);

  useEffect(() => {
    const mql = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!mql) return undefined;
    const onChange = (e) => {
      if (!storedTheme()) setTheme(e.matches ? "dark" : "light");
    };
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  const toggle = useCallback(() => {
    const next = theme === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // Storage unavailable (private mode); the choice just won't persist.
    }
    // Enable color transitions only for this change, never at load.
    const root = document.documentElement;
    root.classList.add("theme-anim");
    window.setTimeout(() => root.classList.remove("theme-anim"), 350);
    setTheme(next);
  }, [theme]);

  return [theme, toggle];
}
