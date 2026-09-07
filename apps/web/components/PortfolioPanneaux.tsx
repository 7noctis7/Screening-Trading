"use client";
/** Panneaux explicatifs de l'étape 4 — extraits de `PortfolioScenarios.tsx`, qui dépassait
 *  les 400 lignes fixées par CLAUDE.md.
 *
 *  Ils partagent une règle : chacun rend visible une DÉCISION du calcul et sa raison
 *  chiffrée. Un scénario absent dit pourquoi la mesure l'a refusé ; un candidat écarté dit
 *  sa date de dernière barre ; une exposition réduite dit le budget de perte qui l'impose.
 *  Une contrainte qu'on ne voit pas est une contrainte qu'on croit absente. */

export const money = (value: number | null) => value == null ? "—"
  : new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(value);
export const pct = (value: number) => `${(value * 100).toFixed(1)}%`;

export function Metrique({ titre, valeur }: { titre: string; valeur: string }) {
  return <div className="rounded-xl bg-surface3 p-3">
    <div className="text-xs text-muted">{titre}</div><b className="mono">{valeur}</b>
  </div>;
}

export /** Ce que la STRUCTURE de l'allocation implique — quatre constats, aucune prévision.
 *
 *  Le ratio de diversification est le plus utile et le moins connu : (Σ wᵢσᵢ)/σₚ vaut 1,0
 *  quand tout bouge ensemble — dix lignes n'y valent alors pas mieux qu'une. Les positions
 *  effectives corrigent le nombre de lignes de leur concentration : quatorze lignes dont
 *  une à 38 % n'en valent que six.
 *
 *  Le Sharpe est RÉALISÉ, sur la fenêtre qui a servi à choisir l'allocation : biaisé vers
 *  le haut par construction, il ne se lit qu'en comparaison entre profils. */
function Structure({ c }: { c: any }) {
  if (!c) return null;
  const n = (x: any, d = 2) => x == null ? "—" : Number(x).toFixed(d);
  return <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
    <Metrique titre="Volatilité annualisée" valeur={c.vol_annuelle == null ? "—" : `${(c.vol_annuelle * 100).toFixed(1)}%`} />
    <Metrique titre="Ratio de diversification" valeur={n(c.ratio_diversification)} />
    <Metrique titre="Positions effectives" valeur={n(c.positions_effectives, 1)} />
    <Metrique titre="Corrélation moyenne" valeur={n(c.correlation_moyenne, 3)} />
    <Metrique titre="Sharpe RÉALISÉ" valeur={n(c.sharpe_realise)} />
  </div>;
}

export /** Position dans la bande 52 semaines. La DISTANCE AU PLUS HAUT est le chiffre qui se lit
 *  sans contexte : −40 % exige +67 % pour revenir, asymétrie que le pourcentage de baisse
 *  masque. Ce n'est pas un objectif de cours — l'IC mesuré du score dit qu'aucune
 *  anticipation n'est démontrée ici — mais un constat sur le passé récent. */
function Bande({ m }: { m: any }) {
  if (!m || m.dernier == null || m.haut_52s == null) return <span className="text-muted">—</span>;
  const dans = Number(m.position_dans_bande ?? 0);
  return <span className="mono text-[10px]">
    <span className={m.distance_haut < -0.2 ? "text-amber-500" : ""}>
      {(m.distance_haut * 100).toFixed(0)}% du haut
    </span>
    <span className="block text-muted2">
      {Number(m.bas_52s).toFixed(2)} ─ {Number(m.haut_52s).toFixed(2)} · {(dans * 100).toFixed(0)}%
    </span>
  </span>;
}

export /** IDENTIFIER l'instrument, pas seulement le nommer.
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

export /** Ce que vaut la SÉLECTION, chiffré. Sans cette ligne, l'utilisateur ne peut pas
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

export /** Résultats imminents : un risque DATÉ et binaire, que la covariance ne mesure pas.
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
    <Perimes s={s} />
  </div>;
}

export /** Séries arrêtées. Une donnée morte n'est pas seulement inutile : figée, elle n'a plus de
 *  variance récente, un min-variance la prend pour l'actif le moins risqué de l'univers et
 *  la surpondère. Et comme l'alignement se fait par intersection, elle tronque la fenêtre
 *  de calcul de tout le portefeuille. Ce qui a été écarté doit donc se voir. */
function Perimes({ s }: { s: any }) {
  const arretees: any[] = s?.stale ?? [];
  if (!arretees.length) return null;
  return <div className="mt-1 text-amber-500">
    <b>{arretees.length} série(s) arrêtée(s) écartée(s)</b> (plus de barre depuis plus de
    {" "}{s?.stale_window ?? 10} j) : {arretees.map((d) => `${d.symbol} (${d.last})`).join(", ")}.
    Figées, elles paraîtraient sans risque et tronqueraient la fenêtre commune.
  </div>;
}

export /** Le régime macro module l'EXPOSITION, jamais le choix des titres, et seulement vers le
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

export /** « Voici la cible » n'est pas actionnable à 100 % de turnover : le coût est certain et
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

export /** Le profil déclaré BORNE le résultat au lieu de le commenter.
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

export /** « Nombre de lignes » est un nombre DEMANDÉ, pas garanti. Un candidat sans historique
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


/** Ce que la préférence sectorielle COÛTE. Une contrainte détourne du poids d'une
 *  allocation qui minimisait le risque ; ne pas afficher ce prix la ferait passer pour un
 *  choix sans conséquence. Le signe est rendu tel quel — exclure un actif très volatil FAIT
 *  BAISSER la volatilité, et présenter cela comme un « surcoût » serait faux. */
export function Preferences({ p }: { p: any }) {
  if (!p) return null;
  const pc = (x: any, d = 1) => x == null ? "—" : `${(Number(x) * 100).toFixed(d)} %`;
  const nb = (x: any, d = 2) => x == null ? "—" : Number(x).toFixed(d);
  const pire = Number(p.ecart_vol ?? 0) > 0;
  return <div className="rounded-xl p-3 text-xs" style={{ background: "color-mix(in srgb,var(--accent) 8%,transparent)" }}>
    <b>Vos préférences sectorielles s'appliquent.</b>
    {p.exclus?.length ? <> Exclu : {p.exclus.map((e: any) => `${e.secteur} (${pc(e.poids_retire)} redistribués)`).join(", ")}.</> : null}
    {p.planchers?.length ? <> Plancher : {p.planchers.map((e: any) => `${e.secteur} ${pc(e.avant)} → ${pc(e.apres)}`).join(", ")}.</> : null}
    {p.plafonds?.length ? <> Plafond : {p.plafonds.map((e: any) => `${e.secteur} ${pc(e.avant)} → ${pc(e.apres)}`).join(", ")}.</> : null}
    <div className="mt-1">
      Effet mesuré : volatilité {pc(p.vol_avant)} → <b className={pire ? "text-amber-500" : ""}>{pc(p.vol_apres)}</b>
      {" "}({Number(p.ecart_vol) >= 0 ? "+" : ""}{pc(p.ecart_vol, 2)}) · diversification {nb(p.diversification_avant)} → {nb(p.diversification_apres)}
      {" "}· positions effectives {nb(p.positions_effectives_avant, 1)} → {nb(p.positions_effectives_apres, 1)}.
      {pire ? " Votre contrainte a un prix : elle éloigne l'allocation de son optimum de risque."
            : " Ici la contrainte ne dégrade pas le risque mesuré."}
    </div>
    {p.non_satisfaits?.length ? <div className="mt-1 text-amber-500">
      <b>Non satisfait</b> : {p.non_satisfaits.map((e: any) => `${e.secteur} (${e.raison})`).join(" · ")}.
    </div> : null}
  </div>;
}


/** Volatilité de CHAQUE ligne détenue — ce qui explique la concentration d'un min-variance.
 *
 *  Un min-variance concentre sur l'actif de plus faible variance : c'est sa définition, pas
 *  un défaut. Mais sans les volatilités individuelles sous les yeux, un poids de 99 % sur
 *  une ligne est indistinguable d'un bug, et surtout d'une SÉRIE ARRÊTÉE — qui n'a plus de
 *  variance récente et que l'optimiseur prend alors pour l'actif le plus sûr du panier.
 *
 *  On n'écarte rien ici, contrairement à la recommandation : ces lignes sont DÉTENUES. On
 *  avertit, l'utilisateur décide. */
export function ParActif({ lignes }: { lignes: Map<string, any> }) {
  const rows = [...lignes.values()].filter((r) => r.vol_annuelle != null);
  if (rows.length < 2) return null;
  const tri = [...rows].sort((a, b) => a.vol_annuelle - b.vol_annuelle);
  const arretees = rows.filter((r) => r.arretee);
  const calme = tri[0], agite = tri[tri.length - 1];
  const ecart = calme.vol_annuelle > 0 ? agite.vol_annuelle / calme.vol_annuelle : null;
  return <div className="rounded-xl bg-surface3 p-3 text-xs text-muted space-y-1">
    <div>
      <b>Volatilité par ligne</b> — la plus calme : <b className="mono">{calme.symbol}</b>{" "}
      {pct(calme.vol_annuelle)} · la plus agitée : <b className="mono">{agite.symbol}</b>{" "}
      {pct(agite.vol_annuelle)}
      {ecart && ecart > 3 ? <> — un facteur <b>{ecart.toFixed(1)}×</b>. Un minimum de variance
        concentrera mécaniquement sur la plus calme : c'est sa définition. Le champ « poids
        maximal » est le garde-fou prévu pour ça.</> : null}
    </div>
    <div className="mono text-[10px]">
      {tri.map((r) => `${r.symbol} ${pct(r.vol_annuelle)}`).join("  ·  ")}
    </div>
    {arretees.length ? <div className="text-amber-500">
      ⚠️ <b>{arretees.length} série(s) arrêtée(s)</b> : {arretees.map((r) => `${r.symbol} (dernière barre ${r.derniere_barre})`).join(", ")}.
      Figée, une série n'a plus de variance récente et paraît donc SANS RISQUE : elle attire
      le capital de l'optimiseur. Ces lignes étant détenues, elles ne sont pas retirées —
      à vous de décider.
    </div> : null}
  </div>;
}
