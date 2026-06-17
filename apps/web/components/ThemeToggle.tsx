"use client";
import { useEffect, useState } from "react";

// Bascule thème clair/sombre — persistée en localStorage, sans flash (cf. script dans layout).
export function ThemeToggle() {
  const [dark, setDark] = useState(true);
  useEffect(() => { setDark(document.documentElement.classList.contains("dark")); }, []);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try { localStorage.setItem("theme", next ? "dark" : "light"); } catch {}
  };
  return (
    <button onClick={toggle} aria-label="Basculer le thème"
      className="ml-auto px-2.5 py-1.5 rounded-[10px] text-sm text-muted hover:text-fg hover:bg-surfaceAlt border border-transparent transition-all">
      {dark ? "☀️" : "🌙"}
    </button>
  );
}
