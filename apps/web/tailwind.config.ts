import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: { extend: { colors: {
    bg: "#08090c", surface: "#141619", surfaceAlt: "#1b1e23", border: "#23272f", border2: "#2d323c",
    fg: "#eef0f3", muted: "#9aa1ab", accent: "#3b82f6", accent2: "#60a5fa",
    pos: "#22c55e", neg: "#f43f5e",
  }, borderRadius: { md: "12px", lg: "16px" },
  boxShadow: { DEFAULT: "0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.25)" } } },
  plugins: [],
};
export default config;
