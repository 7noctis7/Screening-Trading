"use client";
// Negative Results Registry — l'autorité par la transparence radicale. Chaque hypothèse
// d'alpha rejetée par le gate (placebo→DSR→PBO→sabotage) est affichée, citable, reproductible.
// Cible : quants/traders sérieux (rigueur), pas le retail (aucun « signal d'achat »).
import { useFailures } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { Reveal } from "@/components/Reveal";

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
              <article className="card p-4 h-full">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="font-medium mono">{r.facteur ?? "—"}</h2>
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
              </article>
            </Reveal>
          ))}
        </div>
      )}

      <p className="text-muted2 text-xs">
        Méthodologie : López de Prado (DSR, PBO/CSCV). Outil éducatif · pas un conseil
        financier · 100 % open-source · ledger append-only <code className="mono">research/hypotheses.jsonl</code>.
      </p>
    </main>
  );
}
