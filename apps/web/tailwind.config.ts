import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: { extend: { colors: {
    // référencent les variables CSS (cf. globals.css) → suivent le thème clair/sombre
    bg: "var(--bg)", surface: "var(--surface)", surfaceAlt: "var(--surface2)",
    border: "var(--border)", border2: "var(--border2)",
    fg: "var(--fg)", muted: "var(--muted)", accent: "var(--accent)", accent2: "var(--accent2)",
    pos: "var(--pos)", neg: "var(--neg)",
  }, borderRadius: { md: "12px", lg: "16px" },
  boxShadow: { DEFAULT: "var(--shadow)" } } },
  plugins: [],
};
export default config;
