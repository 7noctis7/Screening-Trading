"use client";
// Apparition fluide au scroll (fade + translate), premium, 0 dépendance.
// Respecte prefers-reduced-motion (affichage immédiat). `delay` ms pour l'effet en cascade.
import { useEffect, useRef, useState } from "react";

export function Reveal({ children, delay = 0, className = "" }:
  { children: React.ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [show, setShow] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setShow(true); return; }
    const io = new IntersectionObserver(
      (es) => es.forEach((e) => e.isIntersecting && (setShow(true), io.disconnect())),
      { threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} className={className} style={{
      opacity: show ? 1 : 0,
      transform: show ? "none" : "translateY(28px)",
      transition: `opacity .7s cubic-bezier(.16,1,.3,1) ${delay}ms, `
        + `transform .7s cubic-bezier(.16,1,.3,1) ${delay}ms`,
      willChange: "opacity, transform",
    }}>{children}</div>
  );
}
