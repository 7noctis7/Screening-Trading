"use client";
// Page MÉTHODE — l'autorité par la rigueur. Froide, mathématique, citable. Cible : quants
// sérieux (pas le retail). Décrit le gate à 4 étages + références López de Prado. Statique.
import Link from "next/link";
import { Reveal } from "@/components/Reveal";

const GATE = [
  ["01 · PLACEBO", "p < 0,05",
    "Permutation des dates d'événements (H0 = hasard). On rejoue le signal sur des "
    + "milliers de dates aléatoires ; si l'effet réel n'est pas distinguable du bruit, "
    + "il est rejeté. Désamorce les t-stats gonflés par les fenêtres qui se chevauchent."],
  ["02 · DSR", "Deflated Sharpe Ratio > 0,5",
    "Le Sharpe est déflaté par le NOMBRE d'essais (toutes les hypothèses du ledger) : "
    + "SR* = σ_SR·[(1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(Ne))]. Punit le data-mining (Bailey & "
    + "López de Prado, 2014)."],
  ["03 · PBO / CSCV", "Probability of Backtest Overfitting < 0,5",
    "Combinatorially Symmetric Cross-Validation : la config championne in-sample finit-"
    + "elle sous la médiane out-of-sample ? PBO = P(logit(rang OOS) ≤ 0). Mesure le "
    + "surajustement (López de Prado, 2016)."],
  ["04 · SABOTAGE", "rétention de Sharpe ≥ 0,5",
    "Stress adversarial : coûts ×3 (spread Roll + impact Almgren η·σ·√(Q/ADV)), bruit, "
    + "latence. L'edge doit SURVIVRE net de frais. Un alpha brut mangé par l'exécution "
    + "est éliminé."],
];

export default function Methode() {
  return (
    <main className="max-w-3xl mx-auto p-6 space-y-6">
      <Reveal>
        <header>
          <div className="text-[11px] font-semibold tracking-[0.18em] uppercase"
            style={{ color: "var(--accent2)" }}>Méthode · protocole de validation</div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight mt-1">
            On essaie d'abord de le casser.</h1>
          <p className="text-muted text-sm mt-2">
            Tout backtest gagnant est présumé chanceux. Avant le moindre ordre, un signal
            candidat <span className="mono">s</span> sous la filtration <span className="mono">𝓕ₜ</span>
            {" "}franchit quatre portes déterministes — ou il est rejeté <b>et publié</b>
            {" "}dans le <Link href="/echecs" className="text-accent">registre des négatifs</Link>.
            Aucun raccourci.
          </p>
        </header>
      </Reveal>

      {GATE.map(([k, m, d], i) => (
        <Reveal key={k} delay={(i % 2) * 80}>
          <section className="card p-5">
            <div className="flex items-baseline justify-between gap-3 flex-wrap">
              <h2 className="font-semibold mono">{k}</h2>
              <span className="text-[11px] px-2 py-0.5 rounded-full mono"
                style={{ background: "var(--surface2)", color: "var(--accent2)" }}>{m}</span>
            </div>
            <p className="text-muted text-sm mt-2" style={{ lineHeight: 1.6 }}>{d}</p>
          </section>
        </Reveal>
      ))}

      <Reveal>
        <section className="card p-5">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Garanties</h2>
          <ul className="text-sm text-muted space-y-1.5">
            <li>• <b>Anti-fuite</b> : données point-in-time (vintages, <span className="mono">realtime_start ≤ t</span>) ; un recalcul du passé ne change jamais le passé.</li>
            <li>• <b>Reproductible</b> : chaque verdict est rejouable (<span className="mono">make &lt;facteur&gt;-study</span>) ; ledger append-only.</li>
            <li>• <b>N global</b> : le DSR déflate par les hypothèses <i>distinctes</i> de tout le programme, pas une grille locale.</li>
            <li>• <b>Paper par défaut</b> : aucun euro réel sans validation humaine.</li>
          </ul>
        </section>
      </Reveal>

      <p className="text-muted2 text-xs">
        Références : Bailey & López de Prado, « The Deflated Sharpe Ratio » (2014) ; « The
        Probability of Backtest Overfitting » (2016) ; <i>Advances in Financial Machine
        Learning</i> (2018). Outil éducatif · pas un conseil financier · 100 % open-source.
      </p>
    </main>
  );
}
