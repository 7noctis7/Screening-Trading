"use client";
import Link from "next/link";

// Pipeline du raisonnement : de la donnée brute au portefeuille. Sert à rendre le process clair.
export const STEPS: { n: number; key: string; page: string; title: string; desc: string }[] = [
  { n: 1, key: "data", page: "/data", title: "Données", desc: "Prix réels (YAHOO.db), contrôle qualité & couverture." },
  { n: 2, key: "universe", page: "/universe", title: "Univers", desc: "Les ~929 actifs investissables (actions, ETF, crypto, forex, commodités)." },
  { n: 3, key: "screener", page: "/", title: "Screening", desc: "Classement multi-facteur (momentum, tendance, faible vol…) — des idées." },
  { n: 4, key: "ml", page: "/ml", title: "Signaux ML", desc: "Probabilité de hausse à ~1 mois (modèle validé sans fuite)." },
  { n: 5, key: "fundamentals", page: "/fundamentals", title: "Fondamentaux", desc: "Valeur, qualité, DCF, Piotroski, Altman — pour les actions/ETF." },
  { n: 6, key: "sentiment", page: "/sentiment", title: "Sentiment", desc: "Humeur & news par actif (FinBERT/lexique/momentum)." },
  { n: 7, key: "portfolio", page: "/positions", title: "Sélection & portefeuille", desc: "La STRATÉGIE swing (suivi de tendance, backtestée) décide des positions + sizing vol-target." },
  { n: 8, key: "risk", page: "/risk", title: "Risque", desc: "VaR/EVT/GARCH, limites, stress-tests, allocation optimale." },
  { n: 9, key: "live", page: "/live", title: "Exécution", desc: "Réplication chez le broker (Alpaca/Bitmart), réconciliation, coûts." },
];

// Bandeau compact « tu es ici » en haut d'une fenêtre.
export function StepBanner({ active }: { active: string }) {
  const cur = STEPS.find((s) => s.key === active);
  if (!cur) return null;
  return (
    <div className="card p-3 flex items-center gap-3 text-sm">
      <span className="shrink-0 inline-flex items-center justify-center w-7 h-7 rounded-full mono text-xs font-semibold"
        style={{ background: "color-mix(in srgb, var(--accent) 18%, transparent)", color: "var(--accent2)" }}>{cur.n}</span>
      <div className="flex-1">
        <b>Étape {cur.n}/9 — {cur.title}</b>
        <span className="text-muted"> · {cur.desc}</span>
      </div>
      <Link href="/accueil" className="text-xs text-accent shrink-0 hidden sm:inline">voir le process →</Link>
    </div>
  );
}

// Schéma complet (page Accueil).
export function PipelineFull() {
  return (
    <section className="space-y-3">
      <h2 className="text-sm uppercase tracking-wide text-muted">Le raisonnement, étape par étape</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {STEPS.map((s) => (
          <Link key={s.key} href={s.page} className="card p-4 hover:bg-surfaceAlt transition-colors">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full mono text-xs font-semibold"
                style={{ background: "color-mix(in srgb, var(--accent) 18%, transparent)", color: "var(--accent2)" }}>{s.n}</span>
              <b className="text-sm">{s.title}</b>
            </div>
            <div className="text-muted text-xs mt-1.5">{s.desc}</div>
          </Link>
        ))}
      </div>
      <div className="card p-4 text-sm" style={{ borderColor: "color-mix(in srgb, var(--warn) 40%, transparent)" }}>
        <b>💡 Pourquoi les actifs détenus ≠ le top du screener / ML ?</b>
        <p className="text-muted mt-1.5">
          C'est normal et voulu. Le <b>portefeuille</b> (Positions/Trades) est constitué par <b>une seule stratégie : le
          swing trend-following backtesté</b> — c'est le <b>décideur final</b> (elle entre quand une tendance se confirme,
          dimensionne selon la volatilité et coupe avec un stop). Le <b>Screening</b>, les <b>Signaux ML</b>, les
          <b> Fondamentaux</b> et le <b>Sentiment</b> sont des <b>lentilles d'analyse complémentaires</b> : elles éclairent
          le contexte et fournissent des idées, mais ne dictent pas 1:1 la sélection. Deux outils différents → deux listes
          différentes, c'est attendu.
        </p>
      </div>
    </section>
  );
}
