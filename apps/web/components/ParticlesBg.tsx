"use client";
import { useEffect, useRef, useState } from "react";

/* Réseau de points animés (« data-mesh ») en arrière-plan. DÉFÉRENCE (vision Apple) : très discret,
   DESKTOP uniquement (≥ 1024px) et coupé sous prefers-reduced-motion → la donnée reste la star,
   60 fps préservés, batterie mobile épargnée. N'intercepte aucun clic. */
export function ParticlesBg() {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setShow(!reduced && window.innerWidth >= 1024);   // jamais en mobile/tablette ni reduce-motion
  }, []);

  useEffect(() => {
    if (!show) return;
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const cv = canvas, c = ctx; // alias non-null pour les closures internes

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0, h = 0, dpr = Math.min(window.devicePixelRatio || 1, 2);
    type P = { x: number; y: number; vx: number; vy: number; r: number };
    let pts: P[] = [];
    let raf = 0;

    const accent = () =>
      getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#22d3ee";
    const accent2 = () =>
      getComputedStyle(document.documentElement).getPropertyValue("--accent2").trim() || "#5eead4";

    function resize() {
      w = window.innerWidth; h = window.innerHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      cv.width = w * dpr; cv.height = h * dpr;
      cv.style.width = w + "px"; cv.style.height = h + "px";
      c.setTransform(dpr, 0, 0, dpr, 0, 0);
      // densité ALLÉGÉE (déférence + perf) : moins de nœuds qu'avant
      const n = Math.min(60, Math.round((w * h) / 34000));
      pts = Array.from({ length: n }, () => ({
        x: Math.random() * w, y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.22, vy: (Math.random() - 0.5) * 0.22,
        r: 1 + Math.random() * 1.4,
      }));
    }

    function frame() {
      c.clearRect(0, 0, w, h);
      const c1 = accent(), c2 = accent2();
      const LINK = 130;
      for (let i = 0; i < pts.length; i++) {
        const a = pts[i];
        for (let j = i + 1; j < pts.length; j++) {
          const b = pts[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const d = Math.hypot(dx, dy);
          if (d < LINK) {
            c.strokeStyle = c1;
            c.globalAlpha = (1 - d / LINK) * 0.10;          // liens plus discrets
            c.lineWidth = 0.7;
            c.beginPath(); c.moveTo(a.x, a.y); c.lineTo(b.x, b.y); c.stroke();
          }
        }
      }
      for (const p of pts) {
        if (!reduced) {
          p.x += p.vx; p.y += p.vy;
          if (p.x < 0 || p.x > w) p.vx *= -1;
          if (p.y < 0 || p.y > h) p.vy *= -1;
        }
        c.globalAlpha = 0.4;
        c.fillStyle = Math.random() > 0.985 ? c2 : c1; // scintillement rare
        c.beginPath(); c.arc(p.x, p.y, p.r, 0, Math.PI * 2); c.fill();
      }
      c.globalAlpha = 1;
      if (!reduced) raf = requestAnimationFrame(frame);
    }

    const onVis = () => {
      if (document.hidden) { cancelAnimationFrame(raf); raf = 0; }
      else if (!reduced && !raf) { raf = requestAnimationFrame(frame); }
    };

    resize();
    frame();
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", onVis);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [show]);

  if (!show) return null;
  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      style={{ position: "fixed", inset: 0, zIndex: -1, pointerEvents: "none", opacity: 0.35 }}
    />
  );
}

