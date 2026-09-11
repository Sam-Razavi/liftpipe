import { useEffect, useState } from "react";

const TOKENS = [
  "series-1",
  "series-2",
  "series-1-soft",
  "grid",
  "text-secondary",
  "text-muted",
  "surface-1",
  "surface-2",
  "seq-1",
  "seq-2",
  "seq-3",
  "seq-4",
  "seq-5",
] as const;
export type ThemeColors = Record<(typeof TOKENS)[number], string>;

function read(): ThemeColors {
  const style = getComputedStyle(document.documentElement);
  return Object.fromEntries(
    TOKENS.map((t) => [t, style.getPropertyValue(`--${t}`).trim()]),
  ) as ThemeColors;
}

/** SVG chart libraries need concrete colours; re-read the CSS tokens on theme change. */
export function useThemeColors(): ThemeColors {
  const [colors, setColors] = useState(read);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setColors(read());
    media.addEventListener("change", update);
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => {
      media.removeEventListener("change", update);
      observer.disconnect();
    };
  }, []);
  return colors;
}
