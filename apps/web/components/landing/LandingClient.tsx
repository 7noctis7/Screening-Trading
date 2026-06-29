"use client";
import dynamic from "next/dynamic";
import { useEffect, useRef } from "react";
import s from "@/app/landing/landing.module.css";

// 3D chargé côté client uniquement (jamais SSR → compatible export statique).
const Scene = dynamic(() => import("./Scene"), { ssr: false });

const BASE = process.env.NEXT_PUBLIC_BASE_PATH || "";

export default function LandingClient() {
  const heroRef = useRef<HTMLDivElement>(null);

  // Lenis : scroll inertiel soyeux (sync avec le 3D piloté par window.scrollY).
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let lenis: { raf: (t: number) => void; destroy: () => void } | null = null;
    if (!reduce) {
      import("lenis").then(({ default: Lenis }) => {
        lenis = new Lenis({ lerp: 0.09, wheelMultiplier: 1 });
        const loop = (t: number) => {
          lenis!.raf(t);
          raf = requestAnimationFrame(loop);
        };
        raf = requestAnimationFrame(loop);
      });
    }
    return () => {
      cancelAnimationFrame(raf);
      lenis?.destroy();
    };
  }, []);

  // Spotlight curseur (adaptation du "flashlight") sur le hero.
  useEffect(() => {
    const el = heroRef.current;
    if (!el) return;
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${e.clientX - r.left}px`);
      el.style.setProperty("--my", `${e.clientY - r.top}px`);
    };
    el.addEventListener("pointermove", move);
    return () => el.removeEventListener("pointermove", move);
  }, []);

  // Reveal au scroll (IntersectionObserver, 0 dépendance).
  useEffect(() => {
    const io = new IntersectionObserver(
      (es) => es.forEach((e) => e.isIntersecting && e.target.classList.add(s.show)),
      { threshold: 0.18 },
    );
    document.querySelectorAll(`.${s.reveal}`).forEach((n) => io.observe(n));
    return () => io.disconnect();
  }, []);

  return (
    <div className={s.root}>
      <div className={s.canvas} aria-hidden="true"><Scene /></div>

      <main className={s.content}>
        {/* HERO — hybride : manifeste + accroche produit */}
        <header ref={heroRef} className={s.hero}>
          <div className={s.spotlight} aria-hidden="true" />
          <p className={s.kicker}>Quant Terminal · open-source · paper-first · 0 €</p>
          <h1 className={s.title}>
            L'alpha se vend.<br /><em>La survie se prouve.</em>
          </h1>
          <p className={s.sub}>
            Screening multi-actifs, risque de niveau institutionnel, IA tenue en laisse.
            Aucun oracle promis : on prouve la <b>discipline</b> et on publie ce qui
            échoue. Le seul terminal quant assez honnête pour afficher ses limites.
          </p>
          <div className={s.cta}>
            <a className={`${s.btn} ${s.btnPrimary}`} href={`${BASE}/accueil/`}
              aria-label="Ouvrir le terminal — page Accueil">Ouvrir le terminal →</a>
            <a className={s.btn} href={`${BASE}/dashboard/`}
              aria-label="Voir la démo — tableau de bord">Voir la démo</a>
          </div>
          <div className={s.scrollCue} aria-hidden="true">scroll</div>
        </header>

        {/* SECTION — le pipeline de validation (gate à 4 étages) */}
        <section className={`${s.section} ${s.reveal}`} aria-labelledby="ld-method">
          <div className={s.eyebrow}>Méthode</div>
          <h2 id="ld-method" className={s.h2}>On essaie d'abord de le casser.</h2>
          <p className={s.lead}>
            Tout backtest gagnant est présumé chanceux. Avant le moindre ordre, le signal
            affronte un gate déterministe — hasard, data-mining, surapprentissage,
            exécution dégradée. Quatre étages. Aucun raccourci.
          </p>
          <div className={s.flow}>
            {[
              ["01", "Placebo", "Bat le hasard, ou rien. (p < 0,05)"],
              ["02", "DSR", "Sharpe déflaté du data-mining (López de Prado)"],
              ["03", "PBO / CSCV", "Zéro surajustement, prouvé hors-échantillon"],
              ["04", "Sabotage", "Survit à coût ×3, bruit et latence ?"],
            ].map(([k, t, d]) => (
              <div key={k} className={s.step}>
                <div className={s.stepK}>{k}</div>
                <div className={s.stepT}>{t}</div>
                <div className={s.stepD}>{d}</div>
              </div>
            ))}
          </div>
        </section>

        {/* SECTION — preuves chiffrées (démo) */}
        <section className={`${s.section} ${s.reveal}`} aria-labelledby="ld-proof">
          <div className={s.eyebrow}>Preuves</div>
          <h2 id="ld-proof" className={s.h2}>Cinq pistes. Cinq échecs. Tous publiés.</h2>
          <div className={`${s.grid} ${s.grid4}`}>
            {[
              ["83/100", "score audit (3 rounds)", true],
              ["5/5", "hypothèses d'alpha rejetées", false],
              ["0 €", "coût d'infra", true],
              ["−9 %", "MaxDD preset vs −23 % équipondéré", false],
            ].map(([n, l, teal]) => (
              <div key={l as string} className={s.cell}>
                <div className={`${s.cellNum} ${teal ? s.teal : ""}`}>{n}</div>
                <div className={s.cellLabel}>{l}</div>
              </div>
            ))}
          </div>
          <p className={s.lead} style={{ marginTop: "2rem" }}>
            Cinq pistes d'alpha — actions, insiders, funding, on-chain — testées, cinq
            négatifs propres et documentés. Un négatif honnête vaut mille faux positifs.
            La performance, ici, c'est de <b>survivre</b> aux régimes que les autres
            n'ont pas vus venir.
          </p>
        </section>

        {/* SECTION — démo produit */}
        <section className={`${s.section} ${s.reveal}`} aria-labelledby="ld-product">
          <div className={s.eyebrow}>Le terminal</div>
          <h2 id="ld-product" className={s.h2}>Du screening au paper, rien sous le tapis.</h2>
          <div className={`${s.grid} ${s.grid3}`}>
            {[
              ["Screening", "Actions, ETF, crypto. Filtres + z-score, univers investable, "
                + "100 % point-in-time — zéro look-ahead."],
              ["Risque", "Vol-target, kill-switch, overlay drawdown, concentration "
                + "corrélation-aware. L'edge réel, mesuré."],
              ["Paper", "Exécution simulée par défaut. Aucun euro réel sans validation "
                + "humaine. Le risque avant le rendement."],
            ].map(([t, d]) => (
              <div key={t} className={s.cell}>
                <div className={s.stepT}>{t}</div>
                <div className={s.cellLabel} style={{ marginTop: ".6rem" }}>{d}</div>
              </div>
            ))}
          </div>
        </section>

        <footer className={s.footer}>
          <h2 className={s.h2}>La discipline est le seul alpha.</h2>
          <div className={s.cta} style={{ justifyContent: "center" }}>
            <a className={`${s.btn} ${s.btnPrimary}`} href={`${BASE}/accueil/`}>Entrer dans le terminal →</a>
          </div>
          <div className={s.footNote}>
            Paper par défaut · pas un conseil financier · 100 % open-source.
          </div>
        </footer>
      </main>
    </div>
  );
}
