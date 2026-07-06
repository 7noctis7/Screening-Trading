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
  const rows = (data.rows ?? []).map((r: any) => ({ ...r, status: r.exit_ts ? "fermé" : "ouvert" }));
  const st = data.stats ?? {};
  const sl = data.slippage ?? {};

  const cols: Col[] = [
    { key: "symbol", label: "Actif", render: (v, r) => (
        <span className="mono">{v} <span className="text-muted2 text-[10px] font-sans">{r.venue}</span></span>) },
    { key: "status", label: "Statut", render: (v) => (
        <span className="text-xs px-1.5 py-0.5 rounded font-sans"
          style={{ background: v === "fermé" ? "color-mix(in srgb, var(--pos) 14%, transparent)" : "var(--surface2)",
                   color: v === "fermé" ? "var(--pos)" : "var(--muted)" }}>{v}</span>) },
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
      <p className="text-muted text-xs">Chaque aller-retour du rebalancement paper : features figées à la <b>décision</b>,
        fill broker, PnL réalisé, MFE/MAE. C'est la matière première du verdict GO/NO-GO du <b>2026-08-06</b> — publiée telle quelle, y compris les pertes.</p>

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
          {sl.available ? (
            <section className="card p-3 text-xs text-muted flex flex-wrap gap-x-6 gap-y-1">
              <span title="Écart entre le prix connu à la DÉCISION et le fill réel — sert à calibrer le sabotage-gate avec du vécu.">
                Slippage réel mesuré ({sl.n} fills) : médiane <b className="mono text-fg">{sl.median_bps} bps</b> · P90 <b className="mono text-fg">{sl.p90_bps} bps</b> · pire <b className="mono text-fg">{sl.worst_bps} bps</b></span>
            </section>
          ) : sl.status && (
            <p className="text-muted2 text-xs">Slippage réel : {sl.status} ({sl.hint ?? ""}).</p>
          )}
          <section className="card p-4">
            <SortableTable rows={rows} cols={cols} filterKeys={["symbol", "venue", "status", "regime"]}
              csvName="journal_roundtrips.csv" initialSort={{ key: "entry_ts", dir: "desc" }} dense />
          </section>
        </>
      )}
      <p className="text-muted2 text-[10px]">Paper trading — aucun conseil en investissement. Les positions réelles courtier restent local-only.</p>
    </main>
  );
}
