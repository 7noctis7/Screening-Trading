"use client";
// Perf/mobile : ne MONTE un composant lourd (WebSocket, 3D) que lorsqu'il approche du
// viewport (IntersectionObserver, marge 250px). Évite d'ouvrir 4 WebSockets dès le
// chargement de /crypto. Skeleton réservant la place (pas de saut de layout).
import { useEffect, useRef, useState } from "react";

export function MountWhenVisible({ children, minHeight = 320 }:
  { children: React.ReactNode; minHeight?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [show, setShow] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (es) => es.forEach((e) => e.isIntersecting && (setShow(true), io.disconnect())),
      { rootMargin: "250px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref}>
      {show ? children
        : <div className="shimmer rounded-xl bg-surfaceAlt" style={{ minHeight }} />}
    </div>
  );
}
