"use client";
import { useEffect, useMemo, useState } from "react";
import { recommendUniverse, usePortfolio } from "@/lib/api";
import { PortfolioSnapshot } from "@/lib/portfolio-import";
import { buildScenario, ScenarioKind, ScenarioSource } from "@/lib/portfolio-scenarios";

const money = (value: number | null) => value == null ? "—"
  : new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(value);
const pct = (value: number) => `${(value * 100).toFixed(1)}%`;

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

function Metrique({ titre, valeur }: { titre: string; valeur: string }) {
  return <div className="rounded-xl bg-surface3 p-3">
    <div className="text-xs text-muted">{titre}</div><b className="mono">{valeur}</b>
  </div>;
}

/** IDENTIFIER l'instrument, pas seulement le nommer.
 *
 *  Un nom manquant s'affiche comme manquant. Écrire le ticker à la place du nom donnerait
 *  au lecteur l'impression d'avoir vérifié quelque chose alors qu'il a relu le ticker.
 *
 *  Le lien pointe vers la fiche du FOURNISSEUR de nos prix, indexée par le symbole
 *  exactement utilisé — pas vers un site « relations investisseurs » qu'il faudrait
 *  déduire d'un nom, au risque d'ouvrir la page d'une autre société. L'alias est affiché
 *  quand il diffère : c'est lui qui dit quelle série a réellement servi au calcul. */
function Identite({ m }: { m: any }) {
  if (!m) return <span className="text-muted">—</span>;
  const alias = m.alias && m.alias !== m.symbol ? m.alias : null;
  return <span>
    {m.name
      ? <b className="font-normal">{m.name}</b>
      : <i className="text-muted">nom non renseigné</i>}
    <span className="block text-muted2 text-[10px] mono">
      {[m.venue, m.currency, m.asset_class].filter(Boolean).join(" · ") || "—"}
      {alias ? ` · coté ${alias}` : ""}
      {m.lien ? <> · <a href={m.lien} target="_blank" rel="noopener noreferrer"
        className="underline" style={{ color: "var(--accent)" }}>vérifier</a></> : null}
    </span>
  </span>;
}

/** Tableau des poids. En mode recommandation, la ligne porte aussi le nom et le secteur :
 *  un ticker seul n'est pas une recommandation lisible. Une ligne détenue et non retenue
 *  apparaît à 0 % — c'est la moitié de la décision, elle ne doit pas être masquée. */
function Tableau({ lignes, meta, valeur }: { lignes: any[]; meta: Map<string, any>; valeur: number }) {
  const detaille = meta.size > 0;
  return <div className="overflow-x-auto"><table><thead><tr>
    <th>Actif</th>{detaille ? <th>Nom</th> : null}{detaille ? <th>Secteur</th> : null}
    <th>Actuel</th><th>Proposé</th><th>Écart</th><th>Montant indicatif</th>
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
    </tr>)}
  </tbody></table></div>;
}

/** Le régime macro module l'EXPOSITION, jamais le choix des titres, et seulement vers le
 *  bas : se tromper en étant prudent coûte un rendement manqué, se tromper en étant
 *  agressif peut coûter la capacité à rester investi. */
function Regime({ r }: { r: any }) {
  if (!r) return null;
  return <div className="rounded-xl bg-surface3 p-3 text-xs text-muted">
    <b>Régime macro</b> — {r.cycle || "n/d"} · {r.risk_mode || "n/d"}.{" "}
    {r.reduction > 0
      ? <>Exposition réduite de <b className="mono">{(r.reduction * 100).toFixed(1)} pt</b> : {r.motif}</>
      : <>Aucune réduction appliquée : {r.motif}. L'amplitude suit la force de la PREUVE, jamais celle du signal.</>}
  </div>;
}

/** « Voici la cible » n'est pas actionnable à 100 % de turnover : le coût est certain et
 *  immédiat, le bénéfice diffus. On publie donc l'ordre des mouvements par risque évité
 *  par point de turnover — la part du gain peut dépasser 100 % en cours de route quand
 *  sortir du marché est momentanément moins risqué que la cible elle-même. */
function Chemin({ etapes }: { etapes: any[] | undefined }) {
  if (!etapes?.length) return null;
  const utiles = etapes.filter((e) => e.part_du_gain >= 0.8);
  const seuil = utiles.length ? etapes.indexOf(utiles[0]) + 1 : etapes.length;
  return <details className="rounded-xl border border-border p-3 text-xs text-muted">
    <summary className="cursor-pointer text-fg">
      Chemin de moindre effort — {seuil} mouvement(s) capturent 80 % du risque évité
      {etapes[seuil - 1] ? ` pour ${(etapes[seuil - 1].turnover_cumule * 100).toFixed(0)} % de turnover` : ""}
    </summary>
    <div className="overflow-x-auto mt-2"><table><thead><tr>
      <th>#</th><th>Actif</th><th>De</th><th>Vers</th><th>Turnover cumulé</th><th>Vol atteinte</th><th>Part du gain</th>
    </tr></thead><tbody>
      {etapes.map((e, i) => <tr key={e.symbol}>
        <td className="mono">{i + 1}</td><td className="mono">{e.symbol}</td>
        <td className="text-right mono">{(e.de * 100).toFixed(1)}%</td>
        <td className="text-right mono">{(e.vers * 100).toFixed(1)}%</td>
        <td className="text-right mono">{(e.turnover_cumule * 100).toFixed(0)}%</td>
        <td className="text-right mono">{(e.vol_atteinte * 100).toFixed(1)}%</td>
        <td className="text-right mono">{(e.part_du_gain * 100).toFixed(0)}%</td>
      </tr>)}
    </tbody></table></div>
  </details>;
}

/** Résultats imminents : un risque DATÉ et binaire, que la covariance ne mesure pas.
 *  Une annonce peut ouvrir à −25 % sans que rien dans l'historique ne l'ait annoncé, et
 *  sans compensation par les autres lignes. Le filtre est donc une exclusion d'entrée,
 *  pas une pondération. Ce qu'il n'a PAS pu vérifier est dit aussi : une date inconnue
 *  n'est pas une absence de résultats. */
function Resultats({ s }: { s: any }) {
  const fenetre = s?.earnings_window ?? 0;
  const ecartes: any[] = s?.earnings_blackout ?? [];
  const inconnus: string[] = s?.earnings_unknown ?? [];
  if (!fenetre) return <div className="mt-1">
    Filtre « résultats imminents » <b>inactif</b> (QUANT_EARNINGS non activé) : un candidat
    peut publier ses résultats demain sans que rien ne l'indique ici.
  </div>;
  return <div className="mt-1">
    Résultats imminents (&le; {fenetre} j) :{" "}
    {ecartes.length
      ? <><b>{ecartes.length} candidat(s) écarté(s)</b> — {ecartes.map((e) => `${e.symbol} (${e.days} j)`).join(", ")}</>
      : <>aucun candidat concerné</>}.
    {inconnus.length ? <> Date introuvable pour {inconnus.join(", ")} — non couverts par ce filtre.</> : null}
  </div>;
}

/** Le profil déclaré BORNE le résultat au lieu de le commenter.
 *
 *  La conversion `maxDD ≈ 2.5 × vol` est celle du dimensionnement de production
 *  (`vol_target_from_drawdown`), pas une seconde formule pour le même objet. Ce qui reste
 *  hors du marché est affiché comme une LIGNE du portefeuille : une somme de poids
 *  inférieure à 100 % sans ligne de liquidités se lit comme une erreur d'arrondi. */
function Profil({ contrainte }: { contrainte: any }) {
  if (!contrainte || contrainte.budget_perte == null) return null;
  const { budget_perte, vol_cible, vol_annuelle, exposition, cash } = contrainte;
  const p = (x: number) => `${(x * 100).toFixed(1)} %`;
  return <div className="rounded-xl p-3 text-xs" style={{ background: "color-mix(in srgb,var(--accent) 8%,transparent)" }}>
    <b>Votre profil borne cette allocation.</b> Budget de perte déclaré {p(budget_perte)} →
    volatilité cible {p(vol_cible)} (maxDD ≈ 2,5 × vol). Les actifs retenus portent {p(vol_annuelle)}
    {" "}de volatilité annualisée : l'exposition est donc ramenée à <b className="mono">{p(exposition)}</b>,
    {" "}le reste — <b className="mono">{p(cash)}</b> — restant en liquidités.
    {exposition >= 0.999 ? " Aucune réduction n'a été nécessaire." : ""}
  </div>;
}

/** Ce que vaut la SÉLECTION, chiffré. Sans cette ligne, l'utilisateur ne peut pas
 *  distinguer « le robot a choisi » de « ces actifs vont surperformer » — deux
 *  affirmations très différentes, et une seule est étayée. */
function IC({ ic }: { ic: any }) {
  if (!ic) return null;
  if (!ic.available) return <div className="mt-1">
    Pouvoir prédictif du score : <b>non mesuré</b>. {ic.reason} Tant qu'il ne l'est pas, la
    sélection est un classement, pas une prévision.
  </div>;
  const signe = ic.ic_moyen >= 0 ? "+" : "";
  return <div className="mt-1">
    Pouvoir prédictif du score, <b>mesuré</b> : IC <b className="mono">{signe}{Number(ic.ic_moyen).toFixed(4)}</b>
    {" "}sur {ic.n_dates} fenêtres disjointes de {ic.horizon} jours
    {ic.t_stat != null ? <> (t = {Number(ic.t_stat).toFixed(2)})</> : null}.
    {" "}1<sup>re</sup> moitié {Number(ic.ic_premiere_moitie).toFixed(4)} · 2<sup>e</sup> moitié {Number(ic.ic_seconde_moitie).toFixed(4)} →{" "}
    <b>{ic.robuste ? "tient hors échantillon" : "ne tient pas hors échantillon"}</b>.
    {" "}Mesuré le {String(ic.mesure_le ?? "").slice(0, 10)}.
  </div>;
}

/** « Nombre de lignes » est un nombre DEMANDÉ, pas garanti. Un candidat sans historique
 *  exploitable, ou dont l'introduction récente écraserait la fenêtre commune, est retiré.
 *  Cet écart était publié SOUS le tableau : trop loin pour être vu, donc inexistant en
 *  pratique — on lisait « 3 lignes » sans savoir pourquoi (07/09). Il est désormais lu
 *  avant le tableau qu'il explique. */
function Bilan({ reco }: { reco: any }) {
  const s = reco.selection ?? {};
  const absents: string[] = s.missing_history ?? [];
  const ecartes: any[] = s.dropped ?? [];
  const complet = s.kept === s.asked;
  return <div className={`rounded-xl p-3 text-xs ${complet ? "bg-surface3 text-muted" : "text-amber-500"}`}
    style={complet ? undefined : { background: "color-mix(in srgb,var(--warn) 10%,transparent)" }}>
    <b className="mono">{s.kept}/{s.asked}</b> ligne(s) retenue(s) sur les {s.asked} demandées au screening du jour.
    {absents.length ? <> <b>{absents.length} sans historique exploitable</b> ({absents.join(", ")}) — la base locale ne les couvre pas.</> : null}
    {ecartes.length ? <> <b>{ecartes.length} écartée(s)</b> pour fenêtre commune trop courte : {ecartes.map((d) => `${d.symbol} (depuis ${d.start})`).join(", ")}.</> : null}
    {!absents.length && !ecartes.length && !complet ? <> Le screening n'a pas publié davantage de candidats aujourd'hui.</> : null}
    {" "}Fenêtre commune : {reco.n_observations} observations, T/N = {reco.t_sur_n}.
    <Resultats s={s} />
    <IC ic={reco.ic} />
  </div>;
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
          {source === "recommandation" && reco?.available ? <Bilan reco={reco} /> : null}
          {source === "recommandation" && reco?.profil_applique
            ? <Profil contrainte={reco.contraintes?.[selected]} /> : null}
          {source === "recommandation" ? <Regime r={reco?.regime} /> : null}
          {source === "recommandation" ? <Chemin etapes={reco?.chemin?.[selected]} /> : null}
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
