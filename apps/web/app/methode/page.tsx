"use client";
// Page MÉTHODE — l'autorité par la rigueur. Froide, mathématique, citable. Cible : quants
// Chaque étage est dit d'abord en une phrase claire, puis en détail technique : la rigueur
// n'exige pas d'être illisible. Décrit le gate à 4 étages + références López de Prado. Statique.
import Link from "next/link";
import { Reveal } from "@/components/Reveal";

const GATE = [
  ["01 · PLACEBO", "p < 0,05",
    "La question : et si ce signal ne marchait que par chance ?",
    "On rejoue le signal sur des milliers de dates tirées au hasard. Si ce qu'il "
    + "obtient aux vraies dates n'est pas meilleur que ce qu'il obtient au hasard, "
    + "il est rejeté. C'est ce qu'on appelle une permutation des dates d'événements "
    + "(H0 = hasard) ; ça désamorce les t-stats gonflés par les fenêtres qui se "
    + "chevauchent."],
  ["02 · DSR", "Deflated Sharpe Ratio > 0,5",
    "La question : combien d'idées a-t-il fallu essayer avant de tomber sur celle-là ?",
    "Essayez cent stratégies au hasard, la meilleure aura l'air excellente — sans "
    + "rien valoir. On corrige donc la note de performance (le Sharpe) par le NOMBRE "
    + "d'essais du programme entier : SR* = σ_SR·[(1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(Ne))]. "
    + "C'est le Deflated Sharpe Ratio (Bailey & López de Prado, 2014)."],
  ["03 · PBO / CSCV", "Probability of Backtest Overfitting < 0,5",
    "La question : le réglage gagnant sur le passé tient-il sur des données qu'il n'a jamais vues ?",
    "On coupe l'historique en morceaux, on choisit le meilleur réglage sur les uns, "
    + "on le teste sur les autres, et on recommence dans tous les sens (Combinatorially "
    + "Symmetric Cross-Validation). Si le champion finit régulièrement sous la moyenne "
    + "hors échantillon, il était optimisé sur le passé, pas généralisable. "
    + "PBO = P(logit(rang OOS) ≤ 0) (López de Prado, 2016)."],
  ["04 · SABOTAGE", "rétention de Sharpe ≥ 0,5",
    "La question : reste-t-il quelque chose une fois les frais et la réalité payés ?",
    "On sabote volontairement le signal : frais ×3 (spread Roll + impact Almgren "
    + "η·σ·√(Q/ADV)), bruit ajouté, exécution retardée. Un gain sur le papier que "
    + "les frais mangent entièrement est éliminé."],
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
            Un résultat de test qui gagne est supposé chanceux jusqu'à preuve du
            contraire. Avant qu'une idée serve à quoi que ce soit, elle passe quatre
            épreuves, toujours les mêmes, dans le même ordre — ou elle est rejetée
            <b> et publiée quand même</b> dans le{" "}
            <Link href="/echecs" className="text-accent">registre des idées rejetées</Link>.
            Aucun raccourci. (Formellement : un signal candidat <span className="mono">s</span>
            {" "}sous la filtration <span className="mono">𝓕ₜ</span>.)
          </p>
        </header>
      </Reveal>

      {GATE.map(([k, m, clair, d], i) => (
        <Reveal key={k} delay={(i % 2) * 80}>
          <section className="card p-5">
            <div className="flex items-baseline justify-between gap-3 flex-wrap">
              <h2 className="font-semibold mono">{k}</h2>
              <span className="text-[11px] px-2 py-0.5 rounded-full mono"
                style={{ background: "var(--surface2)", color: "var(--accent2)" }}>{m}</span>
            </div>
            <p className="text-sm mt-2" style={{ lineHeight: 1.6 }}>{clair}</p>
            <p className="text-muted text-sm mt-1.5" style={{ lineHeight: 1.6 }}>{d}</p>
          </section>
        </Reveal>
      ))}

      <Reveal>
        <section className="card p-5">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Garanties</h2>
          <ul className="text-sm text-muted space-y-1.5">
            <li>• <b>Pas de triche sur le passé</b> : chaque test ne voit que ce qui était connu à la date du test, jamais un chiffre révisé après coup (données point-in-time, <span className="mono">realtime_start ≤ t</span>). Réécrire l'histoire est impossible ici.</li>
            <li>• <b>Rejouable par n'importe qui</b> : chaque verdict se recalcule d'une commande (<span className="mono">make &lt;facteur&gt;-study</span>), et le registre ne s'efface pas — on n'y ajoute que des lignes.</li>
            <li>• <b>Le compte des essais est global</b> : la correction du DSR compte toutes les idées <i>différentes</i> essayées sur le projet entier, pas seulement celles d'une étude.</li>
            <li>• <b>Simulation par défaut</b> : aucun euro réel engagé sans qu'un humain le décide.</li>
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
