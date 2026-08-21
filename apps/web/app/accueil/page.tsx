"use client";
import Link from "next/link";
import dynamic from "next/dynamic";
import { AICommentary } from "@/components/AICommentary";
import { Reveal } from "@/components/Reveal";

// ACCUEIL — refonte accessibilité (2026-08-21).
// Avant : la première chose que voyait un visiteur était un glossaire (GARCH(1,1),
// Cornish-Fisher, PSR/DSR, HRP…). C'est une RÉFÉRENCE, pas une porte d'entrée : elle
// suppose déjà connu ce qu'elle explique. Le glossaire vit désormais sur /glossaire.
// Ici on répond à trois questions, dans l'ordre où on se les pose vraiment.

const Scene = dynamic(() => import("@/components/landing/Scene"), { ssr: false });

const PORTES: { href: string; titre: string; question: string; detail: string }[] = [
  {
    href: "/dashboard",
    titre: "Est-ce que ça marche ?",
    question: "Voir les résultats",
    detail: "La courbe de performance, la pire baisse traversée, et ce que cela représente en euros.",
  },
  {
    href: "/positions",
    titre: "Qu'est-ce que je détiens ?",
    question: "Voir le portefeuille",
    detail: "Les positions actuelles, leur poids, et la raison pour laquelle chacune est là.",
  },
  {
    href: "/screener",
    titre: "Que faudrait-il regarder ?",
    question: "Explorer le marché",
    detail: "Les titres qui ressortent aujourd'hui, avec le détail de ce qui les a retenus ou écartés.",
  },
];

export default function Accueil() {
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
        <section className="card p-5 space-y-3">
          <h2 className="text-base font-semibold">Comment lire les chiffres</h2>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            Trois repères suffisent pour comprendre l'essentiel de ce site.
          </p>
          <dl className="space-y-2.5 text-sm">
            <div>
              <dt className="font-medium">La pire baisse</dt>
              <dd style={{ color: "var(--muted)" }}>
                Combien on aurait vu partir, au pire moment, avant que ça remonte. Une baisse de
                15 % sur 10 000 €, c'est voir 1 500 € disparaître temporairement. C'est le chiffre
                qui décide si l'on tient le plan ou si l'on vend au mauvais moment.
              </dd>
            </div>
            <div>
              <dt className="font-medium">Le rapport gain / risque</dt>
              <dd style={{ color: "var(--muted)" }}>
                Est-ce que le gain obtenu valait les secousses traversées ? Au-dessus de 1, oui.
                En dessous de 0,5, on est surtout payé en émotions.
              </dd>
            </div>
            <div>
              <dt className="font-medium">La solidité du résultat</dt>
              <dd style={{ color: "var(--muted)" }}>
                Un bon résultat peut n'être qu'un coup de chance. Ce site calcule la probabilité
                que ce n'en soit pas un, et refuse de mettre en avant ce qui n'atteint pas le seuil.
                C'est pourquoi il publie aussi ses échecs.
              </dd>
            </div>
          </dl>
          <p className="text-sm pt-1">
            <Link href="/glossaire" className="text-accent">Tous les termes expliqués →</Link>
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
