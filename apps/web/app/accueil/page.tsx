"use client";
import Link from "next/link";
import dynamic from "next/dynamic";
import { AICommentary } from "@/components/AICommentary";
import { Reveal } from "@/components/Reveal";
import { useDashboard } from "@/lib/api";
import {
  euros, expliqueDrawdown, expliqueSharpe, VERDICT_LABEL, type Verdict,
} from "@/lib/plain";

// ACCUEIL — l'état du système, pas une brochure.
//
// Deux refontes successives. La première (2026-08-21) a sorti le glossaire de la page d'accueil :
// le premier écran affichait GARCH(1,1), Cornish-Fisher, PSR/DSR — une RÉFÉRENCE, qui suppose
// déjà connu ce qu'elle explique.
//
// Celle-ci corrige le défaut restant : la page était entièrement STATIQUE. Un visiteur du mardi
// voyait exactement ce qu'il avait vu lundi. Une porte d'entrée de terminal doit dire où en est
// le système MAINTENANT — sinon elle ne se lit qu'une fois.
//
// Ce qu'on garde du cahier des charges institutionnel : aucun espace mort, chaque élément gagne
// sa place, et chaque chiffre mène à la page qui l'explique. Ce qu'on écarte : la densité type
// terminal. Un terminal Bloomberg n'a pas de page d'accueil, il a une ligne de commande — parce
// que ses utilisateurs sont formés. La densité appartient aux pages de travail.
//
// Règle d'affichage : la couleur ne porte JAMAIS seule une information. Le verdict est écrit en
// toutes lettres ; la pastille n'est qu'un rappel, en contour, jamais en aplat (convention du
// dépôt pour les états, cf. globals.css).

const Scene = dynamic(() => import("@/components/landing/Scene"), { ssr: false });

const TON: Record<Verdict, string> = {
  bon: "var(--pos)", moyen: "var(--accent)", prudence: "var(--warn)", inconnu: "var(--muted2)",
};

/** Une tuile d'état : un chiffre, son verdict EN TOUTES LETTRES, une phrase, une sortie. */
function Etat({ label, valeur, verdict, phrase, href, lien }: {
  label: string; valeur: string; verdict: Verdict; phrase: string; href: string; lien: string;
}) {
  return (
    <Link href={href} className="card p-4 block h-full hover:border-border2 transition-colors">
      <div className="text-muted text-[11px] uppercase tracking-[0.08em]">{label}</div>
      {/* Le chiffre porte un jeton de TEXTE, jamais la couleur d'état : c'est la pastille et le
          mot du verdict qui portent l'information, donc elle reste lisible sans la couleur. */}
      <div className="mono text-2xl mt-1 text-fg">{valeur}</div>
      <div className="flex items-center gap-1.5 mt-1.5">
        <span aria-hidden className="inline-block w-2 h-2 rounded-full shrink-0"
          style={{ border: `1.5px solid ${TON[verdict]}` }} />
        <span className="text-[11px] uppercase tracking-wide" style={{ color: "var(--muted)" }}>
          {VERDICT_LABEL[verdict]}
        </span>
      </div>
      <div className="text-[11.5px] leading-snug mt-1.5" style={{ color: "var(--muted)" }}>{phrase}</div>
      <div className="text-xs mt-2.5" style={{ color: "var(--accent)" }}>{lien} →</div>
    </Link>
  );
}

const PORTES: { href: string; titre: string; question: string; detail: string }[] = [
  { href: "/dashboard", titre: "Est-ce que ça marche ?", question: "Voir les résultats",
    detail: "La courbe de performance, la pire baisse traversée, et ce que cela représente en euros." },
  { href: "/positions", titre: "Qu'est-ce que je détiens ?", question: "Voir le portefeuille",
    detail: "Les positions actuelles, leur poids, et la raison pour laquelle chacune est là." },
  { href: "/screener", titre: "Que faudrait-il regarder ?", question: "Explorer le marché",
    detail: "Les titres qui ressortent aujourd'hui, avec le détail de ce qui les a retenus ou écartés." },
];

/** Régime de marché → verdict. Le VIX pilote l'exposition, donc il pilote la lecture. */
function etatRegime(vix?: number | null, playbook?: any): { v: Verdict; phrase: string } {
  const expo = Number(playbook?.exposure);
  if (!Number.isFinite(Number(vix))) {
    return { v: "inconnu", phrase: "L'indice de nervosité du marché n'est pas disponible." };
  }
  if (expo >= 1.2) return { v: "bon", phrase: "Marché calme : le système accepte de s'exposer davantage que d'ordinaire." };
  if (expo >= 1) return { v: "moyen", phrase: "Nervosité ordinaire : exposition normale, on suit le plan." };
  if (expo >= 0.6) return { v: "prudence", phrase: "Marché tendu : l'exposition est réduite automatiquement." };
  return { v: "prudence", phrase: "Marché en panique : l'exposition est fortement coupée." };
}

/** PSR = probabilité que le gain ne soit pas un coup de chance. */
function etatSolidite(psr?: number | null): { v: Verdict; phrase: string; valeur: string } {
  if (psr == null || !Number.isFinite(psr)) {
    return { v: "inconnu", valeur: "n/d", phrase: "Pas encore assez d'historique pour se prononcer." };
  }
  const p = Math.round(psr * 100);
  if (p >= 95) return { v: "bon", valeur: `${p} %`, phrase: "Il est très probable que ce résultat ne soit pas dû au hasard." };
  if (p >= 80) return { v: "moyen", valeur: `${p} %`, phrase: "Le résultat tient, sans être hors de doute." };
  return { v: "prudence", valeur: `${p} %`, phrase: "Le hasard reste une explication crédible de ce résultat." };
}

export default function Accueil() {
  const { data: d } = useDashboard();
  const m = d?.metrics ?? {};
  const reg = etatRegime(d?.vix, d?.vix_playbook);
  const sol = etatSolidite(d?.honesty?.available ? d.honesty.psr : null);
  const sharpe = expliqueSharpe(m.sharpe);
  const dd = expliqueDrawdown(m.max_drawdown);
  const frais = d?.as_of ? String(d.as_of).slice(0, 10) : null;

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-8">
      <section className="card hero-photo p-8 md:p-10 relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none" aria-hidden="true"
          style={{ opacity: 0.35 }}><Scene /></div>
        <div className="relative z-10">
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight"
            style={{ background: "linear-gradient(100deg,#22d3ee,#5eead4 45%,#22c55e)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
            Quant Terminal
          </h1>
          <p className="mt-3 max-w-2xl text-lg" style={{ color: "var(--fg)" }}>
            Un outil qui trie les marchés à votre place, explique chacun de ses choix,
            et dit franchement ce qu'il ne sait pas.
          </p>
          <p className="mt-3 max-w-2xl text-sm" style={{ color: "var(--muted)" }}>
            Actions, ETF, crypto et devises. Les décisions sont simulées — aucun argent réel
            n'est engagé. <b className="text-fg">Aide à la décision, pas un conseil en investissement.</b>
          </p>
        </div>
      </section>

      <section>
        <div className="flex items-baseline justify-between flex-wrap gap-2 mb-3">
          <h2 className="text-sm uppercase tracking-wide text-muted">Où en est le système aujourd'hui</h2>
          {/* La fraîcheur est une information, pas un détail : un chiffre juste sur des données
              d'il y a trois semaines reste un chiffre faux pour qui décide aujourd'hui. */}
          <span className="text-[11px]" style={{ color: "var(--muted2)" }}>
            {frais ? `données au ${frais}` : "chargement…"}
          </span>
        </div>
        {!d ? (
          <div className="grid gap-3 md:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="card p-4 h-[132px] animate-pulse" aria-hidden />
            ))}
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-4">
            <Etat label="Climat de marché" valeur={d.vix != null ? `VIX ${Number(d.vix).toFixed(0)}` : "n/d"}
              verdict={reg.v} phrase={reg.phrase} href="/macro" lien="Voir le contexte" />
            <Etat label="Gain / risque" valeur={m.sharpe != null ? Number(m.sharpe).toFixed(2) : "n/d"}
              verdict={sharpe.verdict} phrase={sharpe.phrase} href="/dashboard" lien="Voir les résultats" />
            <Etat label="Pire baisse" valeur={m.max_drawdown != null ? `${(m.max_drawdown * 100).toFixed(1)} %` : "n/d"}
              verdict={dd.verdict}
              phrase={euros(m.max_drawdown) ? `Soit ${euros(m.max_drawdown)} sur 10 000 € avant que ça remonte.` : dd.phrase}
              href="/risk" lien="Voir le risque" />
            <Etat label="Le gain est-il réel ?" valeur={sol.valeur} verdict={sol.v}
              phrase={sol.phrase} href="/methode" lien="Voir la méthode" />
          </div>
        )}
      </section>

      <section>
        <Reveal><h2 className="text-sm uppercase tracking-wide text-muted mb-3">Par où commencer</h2></Reveal>
        <div className="grid gap-3 md:grid-cols-3">
          {PORTES.map((p, i) => (
            <Reveal key={p.href} delay={i * 60}>
              <Link href={p.href} className="card p-4 block h-full hover:border-border2 transition-colors">
                <div className="text-base font-semibold">{p.titre}</div>
                <div className="text-sm mt-1.5" style={{ color: "var(--muted)" }}>{p.detail}</div>
                <div className="text-xs mt-3" style={{ color: "var(--accent)" }}>{p.question} →</div>
              </Link>
            </Reveal>
          ))}
        </div>
      </section>

      <Reveal><AICommentary /></Reveal>

      <Reveal>
        <section className="card p-5">
          <h2 className="text-base font-semibold">Comment lire les chiffres</h2>
          <p className="text-sm mt-1.5" style={{ color: "var(--muted)" }}>
            Les quatre tuiles ci-dessus suffisent à comprendre l'essentiel : le climat du marché,
            si le gain a valu les secousses, ce qu'on aurait vu partir au pire moment, et si tout
            cela peut n'être qu'un coup de chance. Ce dernier point est le plus important, et
            c'est celui que la plupart des outils passent sous silence — ce site publie aussi ses
            échecs pour cette raison.
          </p>
          <p className="text-sm mt-3">
            <Link href="/glossaire" className="text-accent">Tous les termes expliqués →</Link>
            <span className="mx-2" style={{ color: "var(--muted2)" }}>·</span>
            <Link href="/echecs" className="text-accent">Ce qui n'a pas marché →</Link>
          </p>
        </section>
      </Reveal>

      <p className="text-muted2 text-xs">
        ⚠️ Outil éducatif, aucune recommandation personnalisée. Les positions sont simulées
        (« paper trading ») par défaut.
      </p>
    </main>
  );
}
