"use client";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import s from "@/app/landing/landing.module.css";

// 3D chargé côté client uniquement (jamais SSR → compatible export statique).
const Scene = dynamic(() => import("./Scene"), { ssr: false });
// Ticker LIVE façon Bloomberg (WebSocket navigateur) — client-only.
const LandingTicker = dynamic(() => import("./LandingTicker"), { ssr: false });
import {
  VizPlacebo, VizDsr, VizPbo, VizSabotage, VizDrawdown, VizScreen, VizRisk, VizPaper,
} from "./LandingViz";

const GATE = [
  ["01", "PLACEBO", "p < 0,05", <VizPlacebo key="p" />],
  ["02", "DSR", "Sharpe déflaté", <VizDsr key="d" />],
  ["03", "PBO", "Zéro surajustement", <VizPbo key="b" />],
  ["04", "SABOTAGE", "Stress-test ×3", <VizSabotage key="s" />],
] as const;

const CARDS = [
  ["SCREENING", "100 % point-in-time. Zéro look-ahead.", <VizScreen key="sc" />],
  ["RISQUE", "Vol-target & kill-switch automatiques.", <VizRisk key="ri" />],
  ["PAPER", "Exécution simulée par défaut. Sans exception.", <VizPaper key="pa" />],
] as const;

// Méthodologie détaillée (clic sur un visuel → modale). Froid, factuel, sans hype.
const DETAILS: Record<string, { title: string; body: string[] }> = {
  PLACEBO: { title: "01 · Placebo (test de permutation)", body: [
    "Tout backtest gagnant est présumé chanceux jusqu'à preuve du contraire.",
    "On rejoue le signal sur des milliers de dates ALÉATOIRES (hypothèse nulle H0). "
    + "Si l'effet réel n'est pas distinguable du hasard (p ≥ 0,05), il est rejeté.",
    "Désamorce les t-stats gonflés par les fenêtres d'événements qui se chevauchent."] },
  DSR: { title: "02 · DSR — Deflated Sharpe Ratio", body: [
    "Bailey & López de Prado. Le Sharpe est déflaté par le NOMBRE d'essais : chaque "
    + "configuration testée relève le seuil de Sharpe attendu sous H0.",
    "Exigence : DSR > 0,5. Punit le data-mining — essayer 100 stratégies en fait "
    + "ressortir une par pur hasard.",
    "Notre cassure de canal a passé le placebo (p=0,039) mais échoué ici (DSR 0)."] },
  PBO: { title: "03 · PBO / CSCV — surajustement", body: [
    "Probability of Backtest Overfitting (Combinatorially Symmetric Cross-Validation).",
    "On découpe l'historique en blocs, on choisit la config championne IN-sample, puis "
    + "on mesure son rang OUT-of-sample sur toutes les combinaisons.",
    "PBO = fréquence où la championne IS finit sous la médiane OOS. < 0,5 = robuste "
    + "(la nôtre : 0,88 → rejetée)."] },
  SABOTAGE: { title: "04 · Sabotage — stress adversarial", body: [
    "On dégrade VOLONTAIREMENT l'exécution : coûts ×3, bruit injecté, latence.",
    "L'edge doit SURVIVRE : Sharpe stressé > 0 et rétention ≥ 50 % du Sharpe propre.",
    "Un alpha brut mangé par les frais est éliminé (rétention −11,7 sur la cassure)."] },
  SCREENING: { title: "Screening — point-in-time", body: [
    "Chaque décision n'utilise QUE l'information connue à l'instant t (vintages, pas de "
    + "révisions futures) → zéro look-ahead, pas de fuite du futur.",
    "Filtres + z-score cross-sectionnel sur l'univers investable (actions, ETF, crypto)."] },
  RISQUE: { title: "Risque — piloté, pas subi", body: [
    "Vol-targeting : la taille s'ajuste à la volatilité prévue (cible de vol constante).",
    "Kill-switch : coupe l'exposition si le drawdown ou le VIX franchit un seuil.",
    "Overlay drawdown + concentration corrélation-aware (HRP / risk-budget)."] },
  PAPER: { title: "Paper — exécution simulée par défaut", body: [
    "Même interface que le live → parité backtest / paper / live (on échange le broker).",
    "Aucun ordre réel sans --live --yes ET clés API. Ordres routés en sandbox broker.",
    "Le risque avant le rendement. Pas un conseil en investissement."] },
};

const BASE = process.env.NEXT_PUBLIC_BASE_PATH || "";

export default function LandingClient() {
  const heroRef = useRef<HTMLDivElement>(null);
  const [detail, setDetail] = useState<{ title: string; body: string[] } | null>(null);

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
        {/* Bandeau terminal LIVE (Bloomberg) */}
        <LandingTicker />

        {/* 1 — HERO (impact Jobs : 3 mots, données, formule maître) */}
        <header ref={heroRef} className={s.hero}>
          <div className={s.spotlight} aria-hidden="true" />
          <p className={s.kicker}>0 € · open source · infrastructure quant</p>
          <h1 className={s.title}>
            L'alpha se vend.<br /><em>La survie se prouve.</em>
          </h1>
          <p className={s.sub}>Gratuit. Il se mérite par la discipline.</p>
          <div className={s.cta}>
            <a className={`${s.btn} ${s.btnPrimary}`} href={`${BASE}/accueil/`}
              aria-label="Entrer dans le terminal">Entrer dans le terminal →</a>
            <a className={s.btn} href={`${BASE}/dashboard/`}
              aria-label="Voir la démo — tableau de bord">Voir la démo</a>
          </div>
          <div className={s.scrollCue} aria-hidden="true">scroll</div>
        </header>

        {/* 2 — THE GATE (pipeline visuel, métrique + schéma par étage) */}
        <section className={`${s.section} ${s.reveal}`} aria-labelledby="ld-gate">
          <div className={s.eyebrow}>The Gate</div>
          <h2 id="ld-gate" className={s.h2}>Quatre portes. Aucun raccourci.</h2>
          <div className={`${s.grid} ${s.grid4}`}>
            {GATE.map(([k, t, m, viz]) => (
              <button key={k as string} className={s.cell} onClick={() => setDetail(DETAILS[t as string])}
                style={{ cursor: "pointer", textAlign: "left", font: "inherit", color: "inherit", border: 0 }}>
                <div className={s.stepK}>{k} · {t} <span style={{ opacity: .5 }}>＋</span></div>
                <div className={s.cellLabel} style={{ margin: ".25rem 0 .6rem" }}>{m}</div>
                {viz}
              </button>
            ))}
          </div>
        </section>

        {/* 3 — MANIFESTE DE L'ÉCHEC (compteurs géants + drawdown comparé) */}
        <section className={`${s.section} ${s.reveal}`} aria-labelledby="ld-proof">
          <div className={s.eyebrow}>Manifeste de l'échec</div>
          <h2 id="ld-proof" className={s.h2}>7 pistes testées. 7 échecs publiés.</h2>
          <div className={`${s.grid} ${s.grid3}`} style={{ alignItems: "center" }}>
            <div className={s.cell}>
              <div className={`${s.cellNum} ${s.teal}`}>−9 %</div>
              <div className={s.cellLabel}>MaxDD — Quant Terminal</div>
            </div>
            <div className={s.cell}>
              <div className={s.cellNum}>−23 %</div>
              <div className={s.cellLabel}>MaxDD — marché équipondéré</div>
            </div>
            <div className={s.cell}><VizDrawdown /></div>
          </div>
          <p className={s.lead} style={{ marginTop: "2rem" }}>
            Un négatif honnête vaut mille faux positifs. <b>Survivre</b> aux régimes que
            les autres n'ont pas vus venir.
          </p>
        </section>

        {/* 4 — ARCHITECTURE (3 cards glassmorphism : titre, ligne tech, visuel) */}
        <section className={`${s.section} ${s.reveal}`} aria-labelledby="ld-archi">
          <div className={s.eyebrow}>Le terminal</div>
          <h2 id="ld-archi" className={s.h2}>Trois modules. Une discipline.</h2>
          <div className={`${s.grid} ${s.grid3}`}>
            {CARDS.map(([t, d, viz]) => (
              <button key={t as string} className={s.cell} onClick={() => setDetail(DETAILS[t as string])}
                style={{ cursor: "pointer", textAlign: "left", font: "inherit", color: "inherit", border: 0 }}>
                <div className={s.stepT}>{t} <span style={{ opacity: .5 }}>＋</span></div>
                <div className={s.cellLabel} style={{ margin: ".4rem 0 .7rem" }}>{d}</div>
                {viz}
              </button>
            ))}
          </div>
        </section>

        {/* 5 — FOOTER (promesse de discipline) */}
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

      {/* Modale méthodologie (clic sur un visuel) */}
      {detail && (
        <div onClick={() => setDetail(null)} role="dialog" aria-modal="true"
          style={{ position: "fixed", inset: 0, zIndex: 60, display: "grid",
            placeItems: "center", padding: "1.5rem", background: "rgba(0,0,0,.6)" }}>
          <div onClick={(e) => e.stopPropagation()} style={{
            maxWidth: 520, width: "100%", borderRadius: 18, padding: "1.6rem 1.8rem",
            background: "rgba(10,17,24,.96)", border: "1px solid rgba(94,234,212,.2)",
            backdropFilter: "blur(14px)", WebkitBackdropFilter: "blur(14px)",
            boxShadow: "0 30px 80px rgba(0,0,0,.6)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
              <h3 style={{ margin: 0, fontSize: "1.15rem", fontWeight: 600,
                color: "#eaf2f4", letterSpacing: "-.01em" }}>{detail.title}</h3>
              <button onClick={() => setDetail(null)} aria-label="Fermer"
                style={{ background: "none", border: 0, color: "#8aa0a9",
                  fontSize: "1.4rem", lineHeight: 1, cursor: "pointer" }}>×</button>
            </div>
            {detail.body.map((p, i) => (
              <p key={i} style={{ color: "#aebfc7", fontSize: ".95rem", lineHeight: 1.6,
                marginTop: ".8rem" }}>{p}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
