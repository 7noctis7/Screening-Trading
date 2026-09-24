"use client";
// Onglet X — ce que disent les comptes suivis, filtrable.
//
// CE QUI EST AFFICHÉ EST UN DIRE, PAS UNE DONNÉE. Le dépôt encode cette distinction
// ailleurs (`packages/intelligence/classify`) parce qu'elle est le mécanisme par lequel
// un pipeline devient dangereux : une opinion entre, traverse quelques couches, et
// ressort en donnée. Rien ici n'alimente une décision — l'étiquette « TRADE_SIGNAL »
// dit qu'un message ANNONCE une position, jamais qu'elle est bonne.
//
// TROIS VIDES, TROIS MESSAGES. « Rien à l'écran » peut vouloir dire que le flux n'est
// pas branché, qu'il est branché mais vide, ou que les filtres ne laissent rien passer.
// Les confondre pousse l'utilisateur à conclure « c'est cassé » alors qu'il vient de
// cocher deux critères exclusifs.
import { useState } from "react";
import { useSocialX } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { Filtres } from "@/components/x/Filtres";
import { appliquer, actif, CRITERES_VIDES, type Criteres, type Publication }
  from "@/components/x/filtrage";

const TON: Record<string, string> = {
  TRADE_SIGNAL: "var(--accent)", CLOSE_POSITION: "#f43f5e",
  MOVE_STOP: "var(--warn)", TAKE_PROFIT_UPDATE: "var(--pos)",
  CANCEL_SIGNAL: "#f43f5e", UNKNOWN: "var(--muted2)",
};

const quand = (iso: string) => {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "date inconnue"
    : d.toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit",
                                 minute: "2-digit" });
};

function Carte({ p }: { p: Publication }) {
  const niveaux = Object.entries(p.extraits ?? {});
  return (
    <article className="card p-3.5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <span className="text-sm font-semibold">@{p.compte}</span>
        <span className="text-[11px] text-muted2">{quand(p.ts)}</span>
      </div>
      <p className="text-sm mt-2 whitespace-pre-wrap">{p.texte}</p>
      <div className="flex flex-wrap items-center gap-2 mt-2.5 text-[11px]">
        <span className="px-2 py-0.5 rounded-md border border-border"
          style={{ color: TON[p.classification] ?? "var(--muted)" }}>
          {p.classification}
        </span>
        {p.symbole && <span className="text-muted mono">{p.symbole}</span>}
        {!p.symbole && p.ticker && <span className="text-muted mono">{p.ticker}</span>}
        {/* Une direction ABSENTE ne s'affiche pas « neutre » : elle ne s'affiche pas. */}
        {p.direction && (
          <span className="mono"
            style={{ color: p.direction === "LONG" ? "var(--pos)" : "#f43f5e" }}>
            {p.direction}
          </span>
        )}
        {niveaux.map(([k, v]) => (
          <span key={k} className="text-muted2 mono">{k} {v}</span>
        ))}
        {p.url && (
          <a href={p.url} target="_blank" rel="noopener noreferrer"
            className="text-muted2 hover:text-accent transition-colors">voir sur X →</a>
        )}
      </div>
    </article>
  );
}

export default function OngletX() {
  const { data } = useSocialX();
  const [c, setC] = useState<Criteres>(CRITERES_VIDES);
  if (!data) return <PageSkeleton />;

  const toutes = (data.publications ?? []) as Publication[];

  // VIDE N° 1 — le flux n'est pas branché. On le DIT, avec la raison rendue par l'API.
  if (!data.disponible) {
    return (
      <main className="max-w-3xl mx-auto p-6 space-y-3">
        <h1 className="text-lg font-semibold">Ce que disent les comptes suivis</h1>
        <EmptyState title="Flux non connecté" />
        <p className="text-xs text-muted2">
          {data.raison ?? "aucune publication ingérée"} — l&apos;onglet reste vide tant
          qu&apos;aucune source ne l&apos;alimente. Rien n&apos;est simulé ici : mieux
          vaut une page vide qu&apos;une page de faux messages.
        </p>
      </main>
    );
  }

  const vues = appliquer(toutes, c);
  return (
    <main className="max-w-3xl mx-auto p-4 md:p-6 space-y-3">
      <header>
        <h1 className="text-lg font-semibold">Ce que disent les comptes suivis</h1>
        <p className="text-xs text-muted2 mt-1">
          Des propos publiés sur X, classés par intention DÉCLARÉE. Un message étiqueté
          « TRADE_SIGNAL » annonce une position — il ne dit pas qu&apos;elle est bonne,
          et rien de cette page n&apos;alimente une décision automatique.
        </p>
      </header>

      <Filtres c={c} setC={setC}
        comptes={data.comptes ?? []} symboles={data.symboles ?? []}
        classifications={data.classifications ?? []} directions={data.directions ?? []}
        n={vues.length} total={toutes.length} />

      {/* VIDE N° 2 — le flux va bien, ce sont les critères qui vident l'écran. */}
      {vues.length === 0 ? (
        <div className="card p-6 text-center space-y-2">
          <p className="text-sm">Aucune publication ne correspond à ces critères.</p>
          <p className="text-xs text-muted2">
            Le flux contient {toutes.length} publication{toutes.length > 1 ? "s" : ""} :
            ce sont les filtres qui ne laissent rien passer.
          </p>
          {actif(c) && (
            <button onClick={() => setC(CRITERES_VIDES)}
              className="text-xs px-3 py-1.5 rounded-lg border border-border
                         hover:border-border2 hover:text-accent transition-colors">
              Effacer tous les filtres
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-2.5">
          {vues.map((p) => <Carte key={p.id} p={p} />)}
        </div>
      )}
    </main>
  );
}
