"use client";
// Perf/mobile : ne MONTE un composant lourd (WebSocket, 3D) que lorsqu'il approche du
// viewport (IntersectionObserver, marge 250px). Évite d'ouvrir 4 WebSockets dès le
// chargement de /crypto. Skeleton réservant la place (pas de saut de layout).
import { useEffect, useRef, useState } from "react";

export function MountWhenVisible({ children, minHeight = 320, label = "le live" }:
  { children: React.ReactNode; minHeight?: number; label?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [show, setShow] = useState(false);
  const [touch, setTouch] = useState(false);
  useEffect(() => {
    // Mobile (pointeur grossier) : on N'OUVRE PAS les WebSockets tout seuls → tap requis
    // (économie batterie + données mobiles). Desktop : auto-montage près du viewport.
    const isTouch = window.matchMedia("(hover: none)").matches;
    setTouch(isTouch);
    if (isTouch) return;
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (es) => es.forEach((e) => e.isIntersecting && (setShow(true), io.disconnect())),
      { rootMargin: "250px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  if (show) return <div ref={ref}>{children}</div>;
  if (touch) {
    return (
      <button ref={ref as any} onClick={() => setShow(true)}
        className="w-full card grid place-items-center text-sm text-muted hover:text-fg transition-colors"
        style={{ minHeight: Math.min(minHeight, 160) }}>
        ▶ Activer {label} <span className="text-muted2 text-xs">(économie batterie/data)</span>
      </button>
    );
  }
  return <div ref={ref}><div className="shimmer rounded-xl bg-surfaceAlt" style={{ minHeight }} /></div>;
}
