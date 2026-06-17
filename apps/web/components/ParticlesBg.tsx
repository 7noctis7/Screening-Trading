"use client";
import { useEffect, useRef } from "react";

/* Réseau de points animés (style « blockchain / data-mesh ») en arrière-plan.
   Canvas plein écran, fixe, sous le contenu, n'intercepte aucun clic. Très discret,
   couleurs de la charte (cyan/teal). Respecte prefers-reduced-motion (rendu figé). */
export function ParticlesBg() {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
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
      // densité proportionnelle à la surface (plafonnée pour rester léger)
      const n = Math.min(90, Math.round((w * h) / 22000));
      pts = Array.from({ length: n }, () => ({
        x: Math.random() * w, y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.28, vy: (Math.random() - 0.5) * 0.28,
        r: 1 + Math.random() * 1.6,
      }));
    }

    function frame() {
      c.clearRect(0, 0, w, h);
      const c1 = accent(), c2 = accent2();
      const LINK = 140;
      // liens entre points proches (le « mesh »)
      for (let i = 0; i < pts.length; i++) {
        const a = pts[i];
        for (let j = i + 1; j < pts.length; j++) {
          const b = pts[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const d = Math.hypot(dx, dy);
          if (d < LINK) {
            c.strokeStyle = c1;
            c.globalAlpha = (1 - d / LINK) * 0.16;
            c.lineWidth = 0.7;
            c.beginPath(); c.moveTo(a.x, a.y); c.lineTo(b.x, b.y); c.stroke();
          }
        }
      }
      // nœuds
      for (const p of pts) {
        if (!reduced) {
          p.x += p.vx; p.y += p.vy;
          if (p.x < 0 || p.x > w) p.vx *= -1;
          if (p.y < 0 || p.y > h) p.vy *= -1;
        }
        c.globalAlpha = 0.5;
        c.fillStyle = Math.random() > 0.985 ? c2 : c1; // scintillement rare
        c.beginPath(); c.arc(p.x, p.y, p.r, 0, Math.PI * 2); c.fill();
      }
      c.globalAlpha = 1;
      if (!reduced) raf = requestAnimationFrame(frame);
    }

    resize();
    frame();
    window.addEventListener("resize", resize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      style={{ position: "fixed", inset: 0, zIndex: -1, pointerEvents: "none", opacity: 0.55 }}
    />
  );
}
