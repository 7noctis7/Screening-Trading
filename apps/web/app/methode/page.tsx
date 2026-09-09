"use client";
// Page MÉTHODE — l'autorité par la rigueur. Froide, mathématique, citable. Cible : quants
// Chaque étage est dit d'abord en une phrase claire, puis en détail technique : la rigueur
// n'exige pas d'être illisible. Décrit le gate à 4 étages + références López de Prado. Statique.
import Link from "next/link";
import { Reveal } from "@/components/Reveal";
import { useFailures } from "@/lib/api";

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

// LES DEUX CÔTÉS DU REGISTRE.
//
// Le site publiait ses rejets — c'est rare et c'est bien — mais SEULEMENT ses rejets.
// « 6 hypothèses rejetées » se lit alors de deux façons opposées : une rigueur écrasante,
// ou un projet qui ne trouve jamais rien. Aucune n'était vérifiable, et le lecteur n'avait
// aucun moyen de trancher : on ne juge pas un taux de réussite en n'en voyant qu'un côté.
// Le décompte complet est donc affiché, y compris ce qui a passé les quatre épreuves.
const ETIQUETTES: Record<string, [string, string]> = {
  promu: ["Retenues — les quatre épreuves franchies", "var(--pos)"],
  rejete: ["Rejetées", "#f43f5e"],
  en_test: ["Encore à l'épreuve", "#eab308"],
  hypothese: ["Idées notées, pas encore testées", "#9aa1ad"],
};

function Registre() {
  const { data } = useFailures();
  const par = ((data as any)?.par_statut ?? {}) as Record<string, number>;
  const total = Object.values(par).reduce((a, b) => a + b, 0);
  if (!total) return null;
  const ordre = ["promu", "rejete", "en_test", "hypothese"]
    .filter((k) => par[k]).concat(Object.keys(par).filter((k) => !ETIQUETTES[k] && par[k]));
  return (
    <Reveal>
      <section className="card p-5">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-1">
          Tout ce qui a été essayé, pas seulement ce qui a raté
        </h2>
        <p className="text-muted text-sm mb-3">
          {total} idée{total > 1 ? "s" : ""} inscrite{total > 1 ? "s" : ""} au registre à ce
          jour. Le compte est donné en entier : un taux de réussite ne veut rien dire quand on
          n'en montre qu'un côté.
        </p>
        <div className="flex h-2.5 rounded overflow-hidden mb-3" role="img"
          aria-label="répartition des idées du registre par statut">
          {ordre.map((k) => (
            <span key={k} title={`${ETIQUETTES[k]?.[0] ?? k} : ${par[k]}`}
              style={{ width: `${(par[k] / total) * 100}%`,
                       background: ETIQUETTES[k]?.[1] ?? "#9aa1ad" }} />
          ))}
        </div>
        <ul className="text-sm space-y-1">
          {ordre.map((k) => (
            <li key={k} className="flex items-baseline gap-2">
              <span style={{ color: ETIQUETTES[k]?.[1] ?? "#9aa1ad" }}>■</span>
              <span className="text-muted">{ETIQUETTES[k]?.[0] ?? k}</span>
              <b className="mono ml-auto">{par[k]}</b>
            </li>
          ))}
        </ul>
        <p className="text-muted2 text-xs mt-3">
          Le détail des rejets, avec la raison de chacun, est dans le{" "}
          <Link href="/echecs" className="text-accent">registre des idées rejetées</Link>.
          {" "}Une idée « encore à l'épreuve » ne pilote rien sur le site tant qu'elle n'a pas
          franchi les quatre portes.
        </p>
      </section>
    </Reveal>
  );
}

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

      <Registre />

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
