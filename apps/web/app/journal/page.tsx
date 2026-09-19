"use client";
// Journal des round-trips RÉELS (paper) — le « proof of work » du RDV 2026-08-06 :
// chaque aller-retour avec prix de décision, fill, PnL, MFE/MAE. Expectancy GATÉE
// (UNCALIBRATED sous 20 trades fermés) — on n'affiche jamais une stat inventée.
import { useJournal } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import { SortableTable, type Col } from "@/components/SortableTable";
import { PageSkeleton, EmptyState } from "@/components/ui";

const usd = (x?: number | null) => (x == null ? "—" : `$${x.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}`);
const pct = (x?: number | null) => (x == null ? "—" : `${x >= 0 ? "+" : ""}${(x * 100).toFixed(2)}%`);

export default function Journal() {
  const { data } = useJournal();
  if (!data) return <PageSkeleton />;
  // CE QUE CETTE TABLE CONTIENT, ET C'EST UNE DÉFINITION, PAS UN FILTRE. Les
  // aller-retours que le ROBOT a pris et qui ont été réellement OUVERTS PUIS CLÔTURÉS.
  // `/api/journal` les sélectionne sur l'ORIGINE de l'enregistrement, et NON PLUS sur le
  // drapeau `legacy` : un ordre du robot journalisé après coup depuis le fill réel
  // porte `legacy=1` et reste un trade du robot. Le tri par `legacy` affichait
  // +139,75 $ sur 62 trades quand le robot avait fait −23,15 $ sur 112.
  //
  // Les lots ENCORE OUVERTS ne sont pas dans la table — ce ne sont pas des trades,
  // ce sont des positions. Ils ne disparaissent pas pour autant : leur nombre et leur
  // latent sont affichés en tête, parce que les masquer SANS LE DIRE ferait de cette
  // page le palmarès de trades soldés que son propre avertissement dénonce.
  //
  // LES TRANCHES D'UN MÊME LOT NE SONT PAS DES DOUBLONS. Une vente partielle crée une
  // ligne par tranche (`split_id` + `qty` dans `live_roundtrip`) : QQQ acheté le 07/07
  // à 716,69 $ apparaît plusieurs fois, une par sortie. Sans marque, ça se lit comme
  // une duplication, et c'est de là que vient l'essentiel du sentiment de « trop de
  // lignes ».
  const brut = (data.rows ?? []) as any[];
  const compte = new Map<string, number>();
  for (const r of brut) {
    const cle = `${r.symbol}|${r.venue}|${r.entry_ts}|${r.entry_price}`;
    compte.set(cle, (compte.get(cle) ?? 0) + 1);
  }
  const rows = brut.map((r: any) => ({
    ...r,
    fractionne: (compte.get(`${r.symbol}|${r.venue}|${r.entry_ts}|${r.entry_price}`) ?? 1) > 1,
  }));
  const ouverts = (data.ouverts ?? []) as any[];
  const st = data.stats ?? {};
  const sl = data.slippage ?? {};

  const cols: Col[] = [
    { key: "symbol", label: "Actif", render: (v, r) => (
        <span className="mono">{v} <span className="text-muted2 text-[10px] font-sans">{r.venue}</span>
          {r.fractionne && (
            <span className="text-muted2 text-[10px] font-sans ml-1"
              title="Ce lot d'entrée a été soldé en PLUSIEURS tranches : une ligne par tranche, plus le reliquat s'il reste ouvert. Ce ne sont pas des doublons.">
              ⧉ fractionné</span>)}
        </span>) },
    { key: "entry_ts", label: "Entrée", render: (v, r) => (
        <span className="mono text-xs">{v?.slice(0, 10)} · {usd(r.entry_price)}</span>) },
    { key: "exit_ts", label: "Sortie", render: (v, r) => v ? (
        <span className="mono text-xs">{v.slice(0, 10)} · {usd(r.exit_price)}</span>)
        : <span className="text-muted2 text-xs">—</span> },
    { key: "pnl_net", label: "PnL", num: true, align: "right", render: (v, r) => v == null
        ? <span className="text-muted2">—</span>
        : <span className="mono" style={{ color: v >= 0 ? "var(--pos)" : "#ef4444" }}>{usd(v)} <span className="text-[10px] text-muted2">{pct(r.pnl_pct)}</span></span>,
      csv: (v) => v == null ? "" : +v.toFixed(2) },
    { key: "mfe", label: "MFE / MAE", align: "right", render: (v, r) => v == null && r.mae == null
        ? <span className="text-muted2 text-xs">n/d</span>
        : <span className="mono text-xs"><span style={{ color: "var(--pos)" }}>{pct(v)}</span> / <span style={{ color: "#ef4444" }}>{pct(r.mae)}</span></span> },
    { key: "duration_d", label: "Durée", num: true, align: "right",
      render: (v) => <span className="mono text-xs">{v == null ? "—" : `${v} j`}</span> },
    { key: "regime", label: "Régime", render: (v) => <span className="text-xs text-muted font-sans">{v ?? "—"}</span> },
  ];

  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Journal des round-trips
        <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full align-middle"
          style={{ background: "color-mix(in srgb, #22c55e 16%, transparent)", color: "#22c55e" }}>RÉEL · paper</span></h1>
      {/* CE QUE CETTE PAGE N'EST PAS, dit AVANT les chiffres et en une ligne (18/09).
          Trois paragraphes d'avertissement précédaient les cartes : personne ne les
          lisait, et la question « 331 trades à +0,23 $, comment j'arrive à +1 129 $ ? »
          est revenue. L'essentiel tient en une phrase et un renvoi. */}
      <section className="card p-3 text-xs space-y-1" style={{ borderColor: "#f59e0b" }}>
        <p className="text-fg"><b>Ces trades ne sont pas la performance du compte.</b>{" "}
          {/* QUAND LES DEUX PÉRIMÈTRES COÏNCIDENT, LA PHRASE D'OPPOSITION MENT (19/09).
              Depuis la reconstruction depuis les fills, tout le registre vient du
              courtier : la page annonçait « ils pèsent $1 196,63 quand le compte en a
              subi $1 196,63 », deux fois le même chiffre présentés comme un écart. La
              formulation doit suivre ce que les chiffres disent, pas l'inverse. */}
          {st.perimetre?.affiche?.pnl_realise != null && st.perimetre?.compte?.pnl_realise != null
            && Math.abs(st.perimetre.affiche.pnl_realise - st.perimetre.compte.pnl_realise) > 0.005 ? (
            <>Ils pèsent <b className="mono">{usd(st.perimetre.affiche.pnl_realise)}</b> de réalisé,
              quand le compte en a subi <b className="mono">{usd(st.perimetre.compte.pnl_realise)}</b>{" "}
              (import historique compris)
              {st.honnete?.pnl_latent != null && <> et porte <b className="mono">{usd(st.honnete.pnl_latent)}</b> de latent</>}.</>
          ) : st.perimetre?.compte?.pnl_realise != null ? (
            <>Ils pèsent <b className="mono">{usd(st.perimetre.compte.pnl_realise)}</b> de réalisé
              — tout le registre vient des fills du courtier, donc il n&apos;y a plus d&apos;écart
              entre ce que montre cette page et ce que le compte a subi.
              {st.honnete?.pnl_latent != null && <> Les positions encore ouvertes portent{" "}
                <b className="mono">{usd(st.honnete.pnl_latent)}</b> de latent, qui ne figure pas ici.</>}
              {" "}Ce réalisé est <b>BRUT de frais</b> : les frais sont des activités séparées
              chez le courtier, absentes du flux d&apos;ordres.</>
          ) : (
            <>Une page de trades soldés ne peut pas valoir un compte : les positions perdantes
              encore ouvertes n&apos;y figurent pas.</>
          )}
          {" "}Le résultat réel — <b>capital initial → capital actuel</b> — est sur{" "}
          <a href="/positions" className="underline">Mes positions</a>.</p>
        <p className="text-muted2">Le rebalancement ferme ce qui a monté et conserve ce qui a baissé :
          le taux de réussite affiché ici est <b>biaisé à la hausse par construction</b> et ne se
          compare pas à celui d&apos;un backtest.</p>
      </section>
      <p className="text-muted text-xs">Chaque achat suivi de sa revente, en paper. Pour chacun : ce que le robot
        voyait <b>au moment de décider</b>, le prix obtenu, le gain ou la perte, et jusqu&apos;où le trade est monté
        puis descendu avant d&apos;être soldé. Les aller-retours du ROBOT, réellement ouverts puis clôturés —
        décision journalisée ou ordre reconstitué depuis le fill réel. Tout est publié, les pertes comprises.</p>

      {!data.available || rows.length === 0 ? (
        <EmptyState title="Journal vide (pour l'instant)"
          hint={data.available
            ? "Le cron paper (16h05 / cloud 14h35 UTC) journalise chaque ordre envoyé. Les premiers round-trips apparaîtront après la première VENTE de rebalancement."
            : "Le journal vit en local / sur le dataset HF privé — le build public n'y a pas accès (c'est voulu). Lance make start sur le Mac pour le voir."} />
      ) : (
        <>
          <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Lots ouverts" value={String(st.n_open ?? 0)} />
            <MetricCard label="Round-trips fermés" value={String(st.n_closed ?? 0)} />
            <MetricCard label="Win rate" value={st.win_rate != null ? `${(st.win_rate * 100).toFixed(0)}%` : "UNCALIBRATED"} />
            <MetricCard label="Expectancy / trade" value={st.expectancy != null ? usd(st.expectancy) : "UNCALIBRATED"} />
          </section>
          {st.status && <p className="text-muted2 text-xs">⚠️ {st.status} — les stats agrégées n'apparaissent qu'avec un échantillon suffisant (jamais de chiffre inventé).</p>}
          {st.honnete && (st.honnete.n_ouverts ?? 0) > 0 && (
            <section className="card p-3 text-xs space-y-1">
              <p className="text-muted"><b>Ce que la table ne montre pas.</b> Elle porte
                les aller-retours CLÔTURÉS. {st.honnete.n_ouverts} lot(s) restent ouverts
                et pèsent <b className="mono" style={{ color: (st.honnete.pnl_latent ?? 0) >= 0 ? "var(--pos)" : "#ef4444" }}>
                {usd(st.honnete.pnl_latent)}</b> de latent. Le rééquilibrage ferme ce qui a monté et
                conserve ce qui a baissé : lire les deux colonnes, pas la première seule.</p>
              <p className="text-muted2 mono">
                fermés : {st.honnete.n_fermes} · réalisé {usd(st.honnete.pnl_realise)}
                {st.honnete.expectancy_ferme != null && ` · ${usd(st.honnete.expectancy_ferme)}/trade`}
                {st.honnete.win_rate_ferme != null && ` · ${(st.honnete.win_rate_ferme * 100).toFixed(0)}% de réussite`}
                {"  —  "}
                toutes positions : {(st.honnete.n_fermes ?? 0) + (st.honnete.n_ouverts ?? 0)} · {usd(st.honnete.pnl_total)}
                {st.honnete.expectancy_toutes_positions != null && ` · ${usd(st.honnete.expectancy_toutes_positions)}/position`}
                {st.honnete.win_rate_toutes_positions != null && ` · ${(st.honnete.win_rate_toutes_positions * 100).toFixed(0)}% de réussite`}
              </p>
              {/* COMBIEN DE CES LIGNES SONT DES POUSSIÈRES (19/09). Le rejeu FIFO
                  produit une tranche par consommation de lot ; une tranche de
                  0,000001 action pèse autant qu'un aller-retour de 5 000 $ dans le
                  taux de réussite et l'espérance. On mesure et on publie les DEUX
                  lectures — filtrer en silence changerait les chiffres sans le dire. */}
              {(st.poussieres?.n ?? 0) > 0 && (
                <p className="text-muted2">
                  <b>{st.poussieres.n}</b> ligne(s) sur {st.poussieres.n_total} engagent moins
                  de ${st.poussieres.seuil_notionnel} — des tranches résiduelles du
                  rééquilibrage, pas des trades. Elles pèsent {usd(st.poussieres.realise_petits)} de
                  réalisé mais comptent autant que les autres dans les moyennes.
                  {st.poussieres.win_rate_hors != null && (
                    <> Sans elles : <b className="mono">{(st.poussieres.win_rate_hors * 100).toFixed(0)}%</b> de
                    réussite et <b className="mono">{usd(st.poussieres.esperance_hors)}</b>/trade
                    sur {st.poussieres.n_significatifs} aller-retours.</>)}
                </p>)}
              {st.honnete.lots_sans_prix > 0 && (
                <p className="text-muted2">{st.honnete.lots_sans_prix} lot(s) sans prix courant : exclus du latent plutôt qu'estimés.</p>
              )}
              {st.honnete.avertissement && <p style={{ color: "#f59e0b" }}>⚠ {st.honnete.avertissement}</p>}
            </section>
          )}
          {st.perimetre?.avertissement && (
            <section className="card p-3 text-xs space-y-1">
              <p className="text-muted"><b>Périmètre affiché ≠ compte.</b> {st.perimetre.avertissement}</p>
              <p className="text-muted2 mono">
                affiché : {st.perimetre.affiche?.n ?? 0} lots · réalisé {usd(st.perimetre.affiche?.pnl_realise ?? 0)}
                {st.perimetre.affiche?.win_rate != null && ` · ${(st.perimetre.affiche.win_rate * 100).toFixed(0)}% de réussite`}
                {"  —  "}
                compte : {st.perimetre.compte?.n ?? 0} lots · réalisé {usd(st.perimetre.compte?.pnl_realise ?? 0)}
                {st.perimetre.compte?.win_rate != null && ` · ${(st.perimetre.compte.win_rate * 100).toFixed(0)}% de réussite`}
              </p>
              {st.origines && (
                <p className="text-muted2 mono">
                  origine des lots — robot : {st.origines.robot?.n ?? 0} ({usd(st.origines.robot?.pnl_realise ?? 0)})
                  {" · "}import historique : {st.origines["import"]?.n ?? 0} ({usd(st.origines["import"]?.pnl_realise ?? 0)})
                  {(st.origines.inconnu?.n ?? 0) > 0 &&
                    ` · NON RECONNUS : ${st.origines.inconnu.n} (${(st.origines.inconnus ?? []).join(", ")})`}
                </p>
              )}
            </section>
          )}
          {sl.available ? (
            <section className="card p-3 text-xs text-muted flex flex-wrap gap-x-6 gap-y-1">
              <span title="Écart entre le prix connu à la DÉCISION et le fill réel — sert à calibrer le sabotage-gate avec du vécu.">
                Slippage réel mesuré ({sl.n} fills) : médiane <b className="mono text-fg">{sl.median_bps} bps</b> · P90 <b className="mono text-fg">{sl.p90_bps} bps</b> · pire <b className="mono text-fg">{sl.worst_bps} bps</b></span>
            </section>
          ) : sl.status && (
            <p className="text-muted2 text-xs">Slippage réel : {sl.status} ({sl.hint ?? ""}).</p>
          )}
          <section className="card p-4 space-y-3">
            <div className="flex items-baseline gap-2 flex-wrap text-xs font-sans">
              <span className="text-fg">{rows.length} aller-retour(s) clôturé(s)</span>
              {ouverts.length > 0 && (
                <span className="text-muted2 text-[11px]">
                  · {ouverts.length} lot(s) encore ouvert(s) ne figurent pas ici : une
                  position n'est pas un trade tant qu'elle n'est pas refermée. Leur
                  latent est chiffré ci-dessus.
                </span>
              )}
            </div>
            <SortableTable rows={rows} cols={cols} filterKeys={["symbol", "venue", "regime"]}
              csvName="journal_roundtrips.csv" initialSort={{ key: "entry_ts", dir: "desc" }} dense />
          </section>
        </>
      )}
      <p className="text-muted2 text-[10px]">Paper trading — aucun conseil en investissement. Les positions réelles courtier restent local-only.</p>
    </main>
  );
}
