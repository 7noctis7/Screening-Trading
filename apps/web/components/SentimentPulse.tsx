"use client";
/** « Pouls du portefeuille » — sentiment & actualités du portefeuille IMPORTÉ.
 *
 *  Ce panneau ne duplique pas l'onglet `sentiment` du robot : celui-ci moyenne ses lignes
 *  à POIDS ÉGAL (c'est le sentiment de l'univers détenu), alors qu'ici les poids sont
 *  connus. Les DEUX humeurs sont affichées, et c'est leur ÉCART qui informe : un
 *  pessimisme concentré sur les grosses lignes ne se traite pas comme un pessimisme
 *  éparpillé sur les miettes.
 *
 *  Trois refus délibérés :
 *  — une ligne non mesurée n'affiche pas 0,0 (qui se lit « neutre ») mais « non mesuré » ;
 *  — le poids non couvert est affiché : une humeur calculée sur 40 % du capital le dit ;
 *  — aucun titre n'est reproduit, seulement lié à sa source.
 */

import { useEffect, useMemo, useState } from "react";
import { BarreSignee, FLECHE, Jauge, LIBELLE, Segments, TEINTE, Titres } from "@/components/SentimentJauge";
import { portfolioSentiment } from "@/lib/api";
import type { PortfolioSnapshot } from "@/lib/portfolio-import";

const pc = (x: number | null | undefined, d = 1) => x == null ? "—" : `${(x * 100).toFixed(d)}%`;
const sc = (x: number | null | undefined) => x == null ? "—" : `${x > 0 ? "+" : ""}${x.toFixed(2)}`;

function Metrique({ titre, valeur, teinte, aide }: {
  titre: string; valeur: string; teinte?: string; aide?: string;
}) {
  return <div className="rounded-xl bg-surface3 p-2.5" title={aide}>
    <div className="text-[10px] text-muted uppercase tracking-wide">{titre}</div>
    <b className="mono text-sm" style={teinte ? { color: teinte } : undefined}>{valeur}</b>
  </div>;
}

/** Ce qui TIRE l'humeur pondérée. Une humeur à −0,30 portée par une seule ligne à 35 %
 *  se règle en vendant une ligne ; la même à −0,30 partagée par douze lignes décrit le
 *  marché. Le tableau des lignes ne montre pas cette différence. */
function Contributions({ items }: { items: any[] }) {
  if (!items?.length) return null;
  const max = Math.max(...items.map((c) => Math.abs(c.contribution))) || 1;
  return <div className="space-y-1.5">
    <div className="text-[10px] text-muted uppercase tracking-wide">Qui tire l&apos;humeur (poids × score)</div>
    {items.slice(0, 5).map((c) => <div key={c.symbol} className="flex items-center gap-2 text-xs">
      <span className="mono w-16 shrink-0 truncate">{c.symbol}</span>
      <span className="mono text-muted2 w-10 shrink-0 text-right">{pc(c.poids, 0)}</span>
      <div className="flex-1"><BarreSignee score={c.contribution / max} hauteur={5} /></div>
      <span className="mono w-12 shrink-0 text-right" style={{ color: TEINTE(c.contribution) }}>
        {sc(c.contribution)}</span>
    </div>)}
  </div>;
}

/** Carte d'un actif. Repliée elle tient sur deux lignes ; dépliée elle montre les titres
 *  qui ont produit le score — sans quoi le score est un nombre qu'on ne peut pas vérifier. */
function Carte({ r, ouvert, onToggle }: { r: any; ouvert: boolean; onToggle: () => void }) {
  const mesure = r.disponible;
  return <div className="rounded-xl border p-2.5 transition"
    style={{
      borderColor: ouvert ? "var(--accent)" : "var(--border)",
      background: ouvert ? "color-mix(in srgb, var(--accent) 7%, transparent)" : "transparent",
    }}>
    <button type="button" onClick={onToggle} className="w-full text-left" aria-expanded={ouvert}>
      <div className="flex items-baseline gap-2">
        <span className="mono text-sm font-semibold truncate">{r.symbol}</span>
        <span className="mono text-[10px] text-muted2">{pc(r.poids, 1)}</span>
        <span className="ml-auto mono text-sm" style={{ color: TEINTE(r.score) }}>
          {FLECHE(r.score)} {mesure ? sc(r.score) : "n.m."}</span>
      </div>
      <div className="mt-1.5"><BarreSignee score={mesure ? r.score : null} /></div>
      <div className="flex items-center gap-2 mt-1.5 text-[10px] text-muted">
        <span>{LIBELLE[r.label] ?? r.label}</span>
        {r.origine === "momentum" && <span title="aucune actualité trouvée : repli sur la tendance 3 mois">
          · tendance 3 m</span>}
        {r.origine === "indisponible" && <span>· ni actualité ni historique</span>}
        {r.n_news > 0 && <span>· {r.n_news} titre{r.n_news > 1 ? "s" : ""}</span>}
        {r.score_change != null && r.score_change !== 0 && <span className="ml-auto mono"
          style={{ color: TEINTE(r.score_change) }} title="révision vs moyenne des 20 derniers jours">
          Δ {sc(r.score_change)}</span>}
      </div>
    </button>
    {ouvert && <div className="mt-2 pt-2 border-t border-border"><Titres items={r.headlines ?? []} /></div>}
  </div>;
}

const FILTRES: [string, string, (r: any) => boolean][] = [
  ["tout", "Tout", () => true],
  ["bullish", "Haussier", (r) => r.disponible && r.label === "bullish"],
  ["neutral", "Neutre", (r) => r.disponible && r.label === "neutral"],
  ["bearish", "Baissier", (r) => r.disponible && r.label === "bearish"],
  ["nm", "Non mesuré", (r) => !r.disponible],
];

function Fil({ titre, items }: { titre: string; items: any[] }) {
  if (!items?.length) return null;
  return <div className="rounded-xl border border-border p-3">
    <div className="text-[10px] text-muted uppercase tracking-wide mb-2">{titre}</div>
    <Titres items={items} max={6} />
  </div>;
}

export function SentimentPulse({ snapshot }: { snapshot: PortfolioSnapshot | null }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [filtre, setFiltre] = useState("tout");
  const [ouvert, setOuvert] = useState<string | null>(null);

  useEffect(() => {
    if (!snapshot) { setData(null); return; }
    let actif = true;
    setLoading(true);
    portfolioSentiment(snapshot.positions)
      .then((r) => actif && setData(r))
      .catch((e) => actif && setData({ available: false, reason: String(e) }))
      .finally(() => actif && setLoading(false));
    return () => { actif = false; };
  }, [snapshot]);

  const rows: any[] = data?.rows ?? [];
  const segments = useMemo(
    () => FILTRES.map(([cle, texte, test]) => [cle, texte, rows.filter(test).length] as [string, string, number]),
    [rows]);
  const visibles = useMemo(
    () => rows.filter(FILTRES.find(([c]) => c === filtre)?.[2] ?? (() => true)), [rows, filtre]);

  if (!snapshot) return null;

  const entete = <div>
    <div className="eyebrow">Pouls du portefeuille</div>
    <h2 className="text-lg font-semibold mt-1">Sentiment &amp; actualités, pondérés par vos poids</h2>
  </div>;

  if (loading && !data)
    return <section className="card space-y-3">{entete}
      <p className="text-xs text-muted">Lecture des flux…</p></section>;

  if (!data?.available)
    return <section className="card space-y-3">{entete}
      <p className="text-xs text-muted">{data?.reason ?? "Sentiment indisponible pour ce portefeuille."}</p>
    </section>;

  const ecart = data.mood_pondere != null && data.mood != null ? data.mood_pondere - data.mood : null;
  return <section className="card space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      {entete}
      <div className="text-[10px] text-muted text-right">
        moteur <b className="text-fg">{data.engine}</b><br />{data.source}
      </div>
    </div>

    <div className="grid md:grid-cols-[auto,1fr] gap-4 items-center">
      <div className="flex flex-col items-center">
        <Jauge score={data.mood_pondere ?? data.mood} />
        <div className="text-xs font-semibold" style={{ color: TEINTE(data.mood_pondere ?? data.mood) }}>
          {LIBELLE[data.mood_pondere_label] ?? data.mood_pondere_label}
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        <Metrique titre="Humeur pondérée" valeur={sc(data.mood_pondere)} teinte={TEINTE(data.mood_pondere)}
          aide="Moyenne des scores pondérée par vos poids, renormalisée sur les lignes mesurées." />
        <Metrique titre="À poids égal" valeur={sc(data.mood)}
          aide="Ce qu'affiche l'onglet du robot : chaque ligne compte pareil." />
        <Metrique titre="Écart pondéré − égal" valeur={sc(ecart)} teinte={TEINTE(ecart)}
          aide="Positif : le pessimisme est sur les petites lignes. Négatif : il est sur les grosses." />
        <Metrique titre="Δ révision" valeur={data.mood_change == null ? "—" : sc(data.mood_change)}
          teinte={TEINTE(data.mood_change)}
          aide={data.mood_change == null
            ? "Aucune ligne n'a d'historique de sentiment : la révision est inconnue, pas nulle."
            : `Moyenne pondérée des révisions par actif, chacun comparé à SON propre passé — `
              + `${data.n_revisions} ligne(s) comparable(s) sur ${data.historique_jours} jour(s) `
              + `d'historique. Les lignes sans passé sont exclues, pas comptées à zéro.`} />
        <Metrique titre="Capital mesuré" valeur={pc(data.poids_mesure)}
          teinte={data.poids_non_mesure > 0.15 ? "var(--warn)" : undefined}
          aide="Part du portefeuille pour laquelle un score a pu être calculé." />
        <Metrique titre="Couvert par des news" valeur={pc(data.couverture_news)}
          aide="Le reste vient du repli tendance 3 mois — ce n'est pas du sentiment de presse." />
      </div>
    </div>

    {data.poids_non_mesure > 0.0001 && <p className="text-[11px]" style={{ color: "var(--warn)" }}>
      {pc(data.poids_non_mesure)} du portefeuille n&apos;a pu être mesuré (ni actualité, ni historique
      suffisant) et n&apos;entre pas dans l&apos;humeur ci-dessus.
    </p>}

    <Contributions items={data.contributions ?? []} />

    <div className="space-y-2">
      <Segments options={segments} actif={filtre} onChange={(v) => { setFiltre(v); setOuvert(null); }} />
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {visibles.map((r) => <Carte key={r.symbol} r={r} ouvert={ouvert === r.symbol}
          onToggle={() => setOuvert(ouvert === r.symbol ? null : r.symbol)} />)}
      </div>
      {visibles.length === 0 && <p className="text-xs text-muted">Aucune ligne dans ce filtre.</p>}
    </div>

    <div className="grid md:grid-cols-2 gap-2">
      <Fil titre="Macro & banques centrales" items={data.macro_news ?? []} />
      <Fil titre="Actualité marché" items={data.market_news ?? []} />
    </div>

    <p className="text-[11px] text-muted">
      Le ton des actualités récentes sur chaque ligne, agrégé au poids de la ligne dans votre
      portefeuille. Sans actualité disponible pour un actif, la case retombe sur sa tendance
      3 mois — et l&apos;indique. Pour les vraies actualités par actif&nbsp;: lancer l&apos;API avec
      <code className="mono"> QUANT_NEWS=1</code>. Aucune donnée n&apos;est conservée&nbsp;: ce
      portefeuille n&apos;alimente pas l&apos;historique de sentiment du robot.
    </p>
  </section>;
}
