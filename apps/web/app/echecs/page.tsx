"use client";
// Negative Results Registry — l'autorité par la transparence radicale. Chaque hypothèse
// d'alpha rejetée par le gate (placebo→DSR→PBO→sabotage) est affichée, citable, reproductible.
// Cible : quants/traders sérieux (rigueur), pas le retail (aucun « signal d'achat »).
import { useState } from "react";
import { useFailures } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { Reveal } from "@/components/Reveal";

// Interprétation pédagogique d'un verdict : que dit chaque étage du gate, et pourquoi rejeté.
function interpret(r: any): { stage: string; verdict: string; text: string }[] {
  const out: { stage: string; verdict: string; text: string }[] = [];
  const p = r.placebo_p_value, d = r.dsr, b = r.pbo;
  out.push(p == null
    ? { stage: "01 · Placebo", verdict: "—",
        text: "Non calculé séparément (event-study : le p ci-dessus EST le test de "
          + "permutation/hasard). Règle : p < 0,05 pour passer." }
    : p >= 0.05
      ? { stage: "01 · Placebo", verdict: "❌",
          text: `p = ${p} ≥ 0,05 : l'effet n'est PAS distinguable du hasard. Un t-stat ou `
            + "un CAR brut spectaculaire peut être du bruit (fenêtres qui se chevauchent, "
            + "queues épaisses)." }
      : { stage: "01 · Placebo", verdict: "✅",
          text: `p = ${p} < 0,05 : bat le hasard — mais le placebo SEUL ne promeut rien.` });
  out.push(d == null
    ? { stage: "02 · DSR", verdict: "—", text: "Non atteint (rejeté en amont)." }
    : d <= 0.5
      ? { stage: "02 · DSR", verdict: "❌",
          text: `${d} ≤ 0,5 : après déflation par le nombre d'essais (anti data-mining, `
            + "López de Prado), le Sharpe n'est pas significatif. Essayer N stratégies en "
            + "fait ressortir une par chance — le DSR l'annule." }
      : { stage: "02 · DSR", verdict: "✅", text: `${d} > 0,5.` });
  out.push(b == null
    ? { stage: "03 · PBO", verdict: "—", text: "Non calculé." }
    : b >= 0.5
      ? { stage: "03 · PBO", verdict: "❌",
          text: `${(b * 100).toFixed(0)} % de probabilité de SURAJUSTEMENT (CSCV) : la `
            + "configuration championne in-sample finit sous la médiane hors-échantillon. "
            + "Elle est optimisée sur le passé, pas généralisable." }
      : { stage: "03 · PBO", verdict: "✅",
          text: `${(b * 100).toFixed(0)} % < 50 % : robuste hors-échantillon.` });
  return out;
}

const num = (x: any, d = 3) => (typeof x === "number" ? x.toFixed(d) : "n/d");

function exportCsv(items: any[]) {
  const cols = ["date", "facteur", "classe", "horizon", "statut",
    "placebo_p_value", "dsr", "pbo", "these"];
  const esc = (v: any) => `"${String(Array.isArray(v) ? v.join("|") : v ?? "").replace(/"/g, '""')}"`;
  const rows = [cols.join(","), ...items.map((r) => cols.map((c) => esc(r[c])).join(","))];
  const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "quant-terminal-negative-results.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function Echecs() {
  const { data, isLoading } = useFailures();
  const [sel, setSel] = useState<any>(null);
  if (isLoading) return <PageSkeleton />;
  const items = (data?.items ?? []) as any[];
  return (
    <main className="max-w-4xl mx-auto p-6 space-y-5">
      <Reveal>
        <div>
          <div className="text-[11px] font-semibold tracking-[0.18em] uppercase"
            style={{ color: "var(--accent2)" }}>Negative Results Registry</div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight mt-1">
            {data?.n_rejected ?? 0} hypothèses d'alpha. {data?.n_rejected ?? 0} rejetées. 0 cachée.</h1>
          <p className="text-muted text-sm mt-2 max-w-2xl">
            Chaque piste affronte un gate déterministe en 4 étages —
            <b> Placebo · DSR · PBO · Sabotage</b> — et n'est <b>jamais</b> promue sans les
            franchir tous. Les négatifs sont publiés, datés et <b>reproductibles</b>
            (<code className="mono">make &lt;facteur&gt;-study</code>). Un négatif honnête vaut
            mille faux positifs.
          </p>
          {items.length > 0 && (
            <button onClick={() => exportCsv(items)}
              className="mt-3 text-xs px-3 py-1.5 rounded-lg border border-border hover:border-border2 hover:text-accent transition-colors">
              ⤓ Télécharger le registre (CSV)
            </button>
          )}
        </div>
      </Reveal>

      {!items.length ? (
        <EmptyState title="Registre vide sur ce build"
          hint="Le ledger est généré par les études (make regime-study / breakout-study…)." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {items.map((r, i) => (
            <Reveal key={(r.facteur ?? "") + i} delay={(i % 4) * 60}>
              <button onClick={() => setSel(r)}
                className="card p-4 h-full w-full text-left cursor-pointer hover:border-border2 transition-colors block">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="font-medium mono">{r.facteur ?? "—"} <span style={{ opacity: .5 }}>＋</span></h2>
                  <span className="text-[10px] px-2 py-0.5 rounded-full"
                    style={{ background: "color-mix(in srgb, #f43f5e 15%, transparent)", color: "#f43f5e" }}>
                    {r.statut ?? "rejete"}</span>
                </div>
                <div className="text-muted2 text-[11px] mt-0.5">
                  {(r.classe ?? []).join(", ") || "—"} · {r.horizon ?? "—"} · {r.date ?? ""}</div>
                <p className="text-sm text-muted mt-2">{r.these ?? ""}</p>
                <div className="grid grid-cols-3 gap-2 mt-3 text-center">
                  <div><div className="text-[10px] text-muted2">placebo p</div>
                    <div className="mono text-sm">{num(r.placebo_p_value, 3)}</div></div>
                  <div><div className="text-[10px] text-muted2">DSR</div>
                    <div className="mono text-sm">{num(r.dsr, 3)}</div></div>
                  <div><div className="text-[10px] text-muted2">PBO</div>
                    <div className="mono text-sm">{num(r.pbo, 2)}</div></div>
                </div>
                <div className="text-[10px] text-accent mt-2">Cliquer → comment l'interpréter</div>
              </button>
            </Reveal>
          ))}
        </div>
      )}

      <p className="text-muted2 text-xs">
        Méthodologie : López de Prado (DSR, PBO/CSCV). Outil éducatif · pas un conseil
        financier · 100 % open-source · ledger append-only <code className="mono">research/hypotheses.jsonl</code>.
      </p>

      {sel && (
        <div onClick={() => setSel(null)} role="dialog" aria-modal="true"
          className="fixed inset-0 z-[70] grid place-items-center p-4"
          style={{ background: "rgba(0,0,0,.6)" }}>
          <div onClick={(e) => e.stopPropagation()}
            className="card p-5 w-full max-w-lg max-h-[85vh] overflow-y-auto"
            style={{ background: "var(--surface)" }}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold mono">{sel.facteur}</h3>
                <div className="text-muted2 text-[11px]">{(sel.classe ?? []).join(", ")} · {sel.date}</div>
              </div>
              <button onClick={() => setSel(null)} aria-label="Fermer"
                className="text-muted2 hover:text-fg text-xl leading-none">×</button>
            </div>
            <p className="text-sm text-muted mt-2 italic">{sel.these}</p>
            <div className="mt-3 space-y-2">
              {interpret(sel).map((s) => (
                <div key={s.stage} className="rounded-lg border border-border p-2.5"
                  style={{ background: "var(--surface2)" }}>
                  <div className="text-[11px] font-medium">{s.stage} <span>{s.verdict}</span></div>
                  <div className="text-sm text-muted mt-0.5">{s.text}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 text-sm text-muted">
              <b>Verdict</b> : rejeté — au moins un étage du gate échoue. Le signal reste en
              recherche, <b>rien n'est câblé</b>. <i>Un négatif honnête vaut mille faux positifs.</i>
            </div>
            <div className="mt-2 text-[11px] text-muted2">
              Reproduire : <code className="mono">make {(sel.facteur ?? "").split("_")[0]}-study</code>
              {" "}· données réelles, gate déterministe.
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
