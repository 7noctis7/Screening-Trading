import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: { extend: { colors: {
    bg: "#0a0b0d", surface: "#141619", surfaceAlt: "#1b1e23", border: "#262a31",
    fg: "#e6e8eb", muted: "#9aa1ab", accent: "#3b82f6",
    pos: "#22c55e", neg: "#ef4444",
  }, borderRadius: { md: "12px", lg: "16px" } } },
  plugins: [],
};
export default config;
