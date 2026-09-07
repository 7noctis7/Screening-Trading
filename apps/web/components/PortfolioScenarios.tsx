"use client";
import { useEffect, useMemo, useState } from "react";
import { recommendUniverse, usePortfolio } from "@/lib/api";
import { PortfolioSnapshot } from "@/lib/portfolio-import";
import { buildScenario, ScenarioKind, ScenarioSource } from "@/lib/portfolio-scenarios";
import {
  Bande, Bilan, Chemin, IC, Identite, Metrique, money, pct, Perimes, Profil, Regime,
  ParActif, Preferences, Resultats, Structure,
} from "@/components/PortfolioPanneaux";

const SOURCES: { key: ScenarioSource; label: string; aide: string }[] = [
  { key: "portefeuille", label: "Mon portefeuille", aide: "Mieux répartir les lignes que vous détenez déjà." },
  { key: "recommandation", label: "Recommandation du robot", aide: "Ce qu'il faudrait détenir — sélection du screening du jour, y compris des actifs que vous n'avez pas." },
];

function Champ({ label, value, onChange, min, max }: {
  label: string; value: number; onChange: (v: number) => void; min?: string; max?: string;
}) {
  return <label className="text-xs text-muted">{label}
    <input type="number" min={min} max={max} value={value} onChange={(event) => onChange(Number(event.target.value))}
      className="block w-full mt-1 rounded-lg border border-border bg-surface p-2 mono text-fg" />
  </label>;
}





/** Tableau des poids. En mode recommandation, la ligne porte aussi le nom et le secteur :
 *  un ticker seul n'est pas une recommandation lisible. Une ligne détenue et non retenue
 *  apparaît à 0 % — c'est la moitié de la décision, elle ne doit pas être masquée. */
function Tableau({ lignes, meta, valeur }: { lignes: any[]; meta: Map<string, any>; valeur: number }) {
  const detaille = meta.size > 0;
  return <div className="overflow-x-auto"><table><thead><tr>
    <th>Actif</th>{detaille ? <th>Nom</th> : null}{detaille ? <th>Secteur</th> : null}
    <th>Actuel</th><th>Proposé</th><th>Écart</th><th>Montant indicatif</th>
    {detaille ? <th>52 sem.</th> : null}
  </tr></thead><tbody>
    {lignes.map((row) => <tr key={row.symbol}>
      <td className="mono">{row.symbol}</td>
      {detaille ? <td className="text-xs"><Identite m={meta.get(row.symbol)} /></td> : null}
      {detaille ? <td className="text-xs text-muted">{meta.get(row.symbol)?.sector || "—"}</td> : null}
      <td className="text-right mono">{pct(row.current)}</td>
      <td className="text-right mono">{pct(row.proposed)}</td>
      <td className={`text-right mono ${row.delta >= 0 ? "" : "text-amber-500"}`}>
        {row.delta >= 0 ? "+" : ""}{(row.delta * 100).toFixed(1)} pt</td>
      <td className="text-right mono">{money(valeur > 0 ? row.proposed * valeur : null)}</td>
      {detaille ? <td className="text-right"><Bande m={meta.get(row.symbol)} /></td> : null}
    </tr>)}
  </tbody></table></div>;
}








export function PortfolioScenarios({ snapshot, analysis, loading }: {
  snapshot: PortfolioSnapshot | null; analysis?: any; loading?: boolean;
}) {
  const { data: portfolio } = usePortfolio();
  const [selected, setSelected] = useState<ScenarioKind>("prudent");
  const [source, setSource] = useState<ScenarioSource>("portefeuille");
  const [value, setValue] = useState(100000);
  const [costBps, setCostBps] = useState(15);
  const [maxPct, setMaxPct] = useState(20);
  const [lignes, setLignes] = useState(15);
  const [reco, setReco] = useState<any>(null);
  const [recoLoading, setRecoLoading] = useState(false);

  useEffect(() => {
    if (source !== "recommandation") return;
    let actif = true;
    setRecoLoading(true);
    recommendUniverse(lignes, maxPct / 100, snapshot?.positions ?? [])
      .then((resultat) => actif && setReco(resultat))
      .catch((erreur) => actif && setReco({ available: false, reason: String(erreur) }))
      .finally(() => actif && setRecoLoading(false));
    return () => { actif = false; };
  }, [source, lignes, maxPct, snapshot]);

  const enCours = Boolean(loading) || (source === "recommandation" && recoLoading);
  const amont = useMemo(() => {
    const origine = source === "recommandation" ? reco : analysis;
    return origine && origine.available === false ? String(origine.reason ?? "") : "";
  }, [source, reco, analysis]);

  const scenarios = useMemo(() => {
    // Les deux sources publient les mêmes trois profils : seule la LISTE d'actifs change.
    // Une seule fonction de construction, donc pas de divergence possible entre elles.
    const depuisReco = reco?.available
      ? { symbols: reco.symbols, min_variance: reco.scenarios?.prudent,
          risk_parity: reco.scenarios?.neutre, hrp: reco.scenarios?.dynamique,
          conviction: reco.scenarios?.conviction }
      : null;
    const depuisAnalyse = analysis?.available
      ? { symbols: analysis.symbols, min_variance: analysis.scenarios?.prudent,
          risk_parity: analysis.scenarios?.neutre, hrp: analysis.scenarios?.dynamique }
      : portfolio?.analysis?.optimal_allocation;
    const calcule = source === "recommandation" ? depuisReco : depuisAnalyse;
    // « Conviction » n'est proposé QUE sur l'univers recommandé : c'est le score de
    // sélection qui l'alimente, et un portefeuille importé n'en a pas.
    const profils: ScenarioKind[] = source === "recommandation"
      ? ["prudent", "neutre", "dynamique", "conviction"] : ["prudent", "neutre", "dynamique"];
    const construits = snapshot
      ? profils.map((kind) =>
          buildScenario(snapshot, calcule, kind, value > 0 ? value : null, costBps, maxPct / 100,
            source, reco?.contraintes?.[kind]))
      : [];
    // Une panne amont connaît DÉJÀ sa cause exacte : on la relaie au lieu de laisser
    // chaque carte réinventer un motif générique.
    if (amont) return construits.map((scenario) => ({ ...scenario, reason: amont }));
    // « Conviction » absent n'est pas un accident technique : c'est la MESURE qui l'a
    // refusé, et le back en donne la raison chiffrée. Afficher « clé absente » à sa place
    // masquerait précisément l'information qui justifie le refus.
    const motifConviction = reco?.conviction_reason;
    return motifConviction
      ? construits.map((s) => s.kind === "conviction" && !s.available ? { ...s, reason: motifConviction } : s)
      : construits;
  }, [snapshot, analysis, portfolio, reco, source, value, costBps, maxPct, amont]);

  const meta = useMemo(() => new Map<string, any>(
    source === "recommandation" && reco?.available ? (reco.rows ?? []).map((r: any) => [r.symbol, r]) : []),
    [source, reco]);
  // Volatilité par actif du portefeuille IMPORTÉ : sans elle, un min-variance à 99 % sur
  // une ligne ne se distingue ni d'un bug ni d'une série arrêtée.
  const parActif = useMemo(() => new Map<string, any>(
    (analysis?.par_actif ?? []).map((r: any) => [r.symbol, r])), [analysis]);

  if (!snapshot) return null;
  const active = scenarios.find((scenario) => scenario.kind === selected)!;
  const selection = reco?.selection;

  return <section id="portfolio-scenarios" className="card space-y-5 scroll-mt-24">
    <div className="flex flex-wrap justify-between gap-3">
      <div>
        <div className="eyebrow">Étape 4 · Améliorer</div>
        <h2 className="text-lg font-semibold mt-1">Scénarios sous contraintes</h2>
        <p className="text-xs text-muted mt-1">Exploratoires, calculés par les moteurs existants. Aucun rendement attendu n'entre dans ces poids.</p>
      </div>
      <span className="text-[10px] mono rounded-full border border-border px-3 py-1 h-fit">AUCUN ORDRE</span>
    </div>

    <div className="grid md:grid-cols-2 gap-2">{SOURCES.map((item) =>
      <button key={item.key} onClick={() => setSource(item.key)}
        className={`text-left rounded-xl border p-3 ${source === item.key ? "border-cyan-500 bg-surface3" : "border-border"}`}>
        <b>{item.label}</b><p className="text-xs text-muted mt-1">{item.aide}</p>
      </button>)}
    </div>

    <div className="grid md:grid-cols-4 gap-3">
      <Champ label="Valeur indicative (€)" value={value} onChange={setValue} min="0" />
      <Champ label="Coûts aller simple (bps)" value={costBps} onChange={setCostBps} min="0" />
      <Champ label="Poids maximal (%)" value={maxPct} onChange={setMaxPct} min="1" max="100" />
      {source === "recommandation"
        ? <Champ label="Nombre de lignes" value={lignes} onChange={setLignes} min="3" max="30" />
        : <div />}
    </div>

    <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-2">{scenarios.map((scenario) =>
      <button key={scenario.kind} onClick={() => setSelected(scenario.kind)}
        className={`text-left rounded-xl border p-3 ${selected === scenario.kind ? "border-cyan-500 bg-surface3" : "border-border"}`}>
        <div className="flex justify-between"><b>{scenario.label}</b><span>{scenario.available ? "✓" : "—"}</span></div>
        <p className="text-xs text-muted mt-1">{scenario.method}</p>
      </button>)}
    </div>

    {enCours
      ? <div className="rounded-xl bg-surface3 p-4 text-sm text-muted">Chargement des historiques, alignement des calendriers et calcul de la covariance…</div>
      : !active.available
        ? <div className="rounded-xl p-4 text-sm text-amber-500" style={{ background: "color-mix(in srgb,var(--warn) 10%,transparent)" }}>⚠️ {active.reason}</div>
        : <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <Metrique titre="Turnover" valeur={pct(active.turnover)} />
            <Metrique titre="Coûts estimés" valeur={money(active.estimatedCost)} />
            <Metrique titre="Plafonds appliqués" valeur={String(active.breaches)} />
            <Metrique titre="Effet moyen plafond" valeur={`${(active.averageCapEffect * 100).toFixed(2)} pt`} />
          </div>
          {source === "recommandation" ? <Structure c={reco?.contraintes?.[selected]} /> : null}
          {source === "recommandation" && reco?.available ? <Bilan reco={reco} /> : null}
          {source === "recommandation" && reco?.profil_applique
            ? <Profil contrainte={reco.contraintes?.[selected]} /> : null}
          {source === "recommandation" ? <Preferences p={reco?.preferences?.[selected]} /> : null}
          {source === "recommandation" ? <Regime r={reco?.regime} /> : null}
          {source === "recommandation" ? <Chemin etapes={reco?.chemin?.[selected]} /> : null}
          {source === "portefeuille" ? <ParActif lignes={parActif} /> : null}
          <Tableau lignes={active.weights} meta={meta} valeur={value} />
        </>}

    {source === "recommandation" && reco?.available ? <div className="rounded-xl border border-border p-3 text-xs text-muted space-y-1">
      <p className="text-amber-500">⚠️ {reco.caveat}</p>
      <p>Sélection : {selection?.source}. {selection?.kept}/{selection?.asked} lignes retenues
        {selection?.universe_size ? ` sur un univers investable de ${selection.universe_size}` : ""}.
        Historique commun du {reco.start} au {reco.as_of} ({reco.n_observations} observations, T/N = {reco.t_sur_n}).</p>
      {selection?.filters?.length ? <p>Filtres durs appliqués : {selection.filters.join(" · ")}.</p> : null}
      {selection?.dropped?.length ? <p>Écartés faute d'historique commun : {selection.dropped.map((d: any) => `${d.symbol} (depuis ${d.start})`).join(", ")}.</p> : null}
      {selection?.missing_history?.length ? <p>Sans historique exploitable : {selection.missing_history.join(", ")}.</p> : null}
    </div> : null}

    <details className="rounded-xl border border-border p-3 text-xs text-muted">
      <summary className="cursor-pointer text-fg">Méthodologie et limites</summary>
      <p className="mt-2">Les trois profils répartissent le RISQUE mesuré : « Prudent » minimise la variance,
        « Neutre » égalise les contributions au risque, « Dynamique » est un Hierarchical Risk Parity sur les
        grappes de corrélation. Aucun n'utilise de rendement attendu — « idéal » signifie ici « bien réparti »,
        jamais « le plus rentable ». Les séries sont alignées par intersection de dates, sans remplissage.
        Les coûts sont une hypothèse linéaire en points de base appliquée au turnover : spread dynamique,
        fiscalité, impact racine carrée et borrow ne sont pas modélisés. Un scénario qui viole le plafond est
        refusé, jamais corrigé silencieusement.</p>
    </details>
  </section>;
}
