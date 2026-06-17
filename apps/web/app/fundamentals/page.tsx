"use client";
import { useFundamentals } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { SortableTable, type Col } from "@/components/SortableTable";

const RC: Record<string, string> = { BUY: "#22c55e", HOLD: "#9aa1ad", SELL: "#f43f5e" };
const pp = (x?: number) => (x == null ? "—" : `${(x * 100).toFixed(0)}%`);
const colorPct = (x: number) => (x > 0 ? "#22c55e" : x < 0 ? "#f43f5e" : "#9aa1ad");

export default function Fundamentals() {
  const { data: f } = useFundamentals();
  if (!f) return <PageSkeleton />;
  if (!f.available)
    return <main className="max-w-3xl mx-auto p-6"><EmptyState title="Aucun fondamental disponible" hint="Actifs sans données fondamentales (crypto/forex)." /></main>;

  const cols: Col[] = [
    { key: "symbol", label: "Actif" },
    { key: "sector", label: "Secteur", render: (v) => <span className="text-muted text-xs">{v}</span> },
    { key: "per", label: "PER", num: true },
    { key: "ps", label: "P/S", num: true, render: (v) => (v == null ? "—" : v) },
    { key: "ev_ebitda", label: "EV/EBITDA", num: true },
    { key: "pb", label: "P/B", num: true },
    { key: "roe", label: "ROE", num: true, render: pp, csv: (v) => v },
    { key: "net_margin", label: "Marge nette", num: true, render: pp, csv: (v) => v },
    { key: "gross_margin", label: "Marge brute", num: true, render: pp, csv: (v) => v },
    { key: "rev_growth", label: "Croiss. CA", num: true, csv: (v) => v,
      render: (v) => (v == null ? "—" : <span style={{ color: colorPct(v) }}>{(v * 100).toFixed(0)}%</span>) },
    { key: "earnings_growth", label: "Croiss. bénéf.", num: true, csv: (v) => v,
      render: (v) => (v == null ? "—" : <span style={{ color: colorPct(v) }}>{(v * 100).toFixed(0)}%</span>) },
    { key: "fcf_yield", label: "FCF yield", num: true, render: pp, csv: (v) => v },
    { key: "margin_of_safety", label: "Marge sécu.", num: true, csv: (v) => v,
      render: (v) => (v == null ? "—" : <span style={{ color: colorPct(v) }}>{(v * 100).toFixed(0)}%</span>) },
    { key: "f_score", label: "F-score", num: true,
      render: (v) => <span style={{ color: v >= 7 ? "#22c55e" : v >= 4 ? "#f59e0b" : "#f43f5e" }}>{v}/9</span> },
    { key: "altman_z", label: "Altman Z", num: true,
      render: (v, r) => <span style={{ color: r.altman_zone === "sûr" ? "#22c55e" : r.altman_zone === "gris" ? "#f59e0b" : "#f43f5e" }}>{v}</span> },
    { key: "tech_score", label: "Tech", num: true,
      render: (v, r) => <span style={{ color: r.tech_label === "haussier" ? "#22c55e" : r.tech_label === "baissier" ? "#f43f5e" : "#9aa1ad" }}>{v}</span> },
    { key: "combined_score", label: "Fond+Tech", num: true, render: (v) => <b>{v}</b> },
    { key: "rating", label: "Reco", align: "right",
      render: (v) => <span className="font-sans font-medium" style={{ color: RC[v] }}>{v}</span> },
  ];

  return (
    <main className="max-w-6xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Analyse fondamentale</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card p-4"><div className="text-muted text-xs uppercase">Source</div><div className="text-lg mt-1">{f.source}</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Titres analysés</div><div className="text-lg mono mt-1">{f.n}</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Signaux BUY</div><div className="text-lg mono mt-1" style={{ color: "#22c55e" }}>{f.buys}</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Tri</div><div className="text-sm mt-1 text-muted">clique un en-tête</div></div>
      </div>
      <p className="text-muted text-xs">{f.method} · Seuls les <b>actions/ETF</b> ont des fondamentaux (crypto/forex/commodités exclus). Trie en cliquant les colonnes, filtre, exporte en CSV.</p>
      <section className="card p-4">
        <SortableTable rows={f.rows} cols={cols} filterKeys={["symbol", "sector"]} csvName="fondamentaux"
          initialSort={{ key: "combined_score", dir: "desc" }} />
      </section>
    </main>
  );
}
