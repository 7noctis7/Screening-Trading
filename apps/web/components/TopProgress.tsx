"use client";
import { useIsFetching } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

// Barre de chargement haute (style Apple/NProgress) : progresse pendant que les données arrivent,
// se remplit puis disparaît en douceur. Couleurs de la charte (cyan→teal→vert). Aucune dépendance.
export function TopProgress() {
  const fetching = useIsFetching();
  const [width, setWidth] = useState(0);
  const [visible, setVisible] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (fetching > 0) {
      setVisible(true);
      setWidth((w) => (w < 12 ? 12 : w));
      if (!timer.current) {
        timer.current = setInterval(() => {
          setWidth((w) => (w >= 90 ? 90 : w + (90 - w) * 0.12 + 0.6)); // approche 90 % asymptotiquement
        }, 200);
      }
    } else {
      if (timer.current) { clearInterval(timer.current); timer.current = null; }
      setWidth(100);                                   // remplit puis cache
      const t = setTimeout(() => { setVisible(false); setWidth(0); }, 450);
      return () => clearTimeout(t);
    }
    return () => { if (timer.current) { clearInterval(timer.current); timer.current = null; } };
  }, [fetching]);

  return (
    <div aria-hidden="true" style={{
      position: "fixed", top: 0, left: 0, right: 0, height: 2.5, zIndex: 60,
      pointerEvents: "none", opacity: visible ? 1 : 0, transition: "opacity .35s ease",
    }}>
      <div style={{
        height: "100%", width: `${width}%`,
        background: "linear-gradient(90deg,#22d3ee,#5eead4 55%,#22c55e)",
        boxShadow: "0 0 10px rgba(34,211,238,.7)",
        transition: "width .25s cubic-bezier(.2,.8,.2,1)",
      }} />
    </div>
  );
}
