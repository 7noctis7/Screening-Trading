"use client";
import { useInvestors } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { SortableTable, type Col } from "@/components/SortableTable";
import { StepBanner } from "@/components/Pipeline";

const bar = (v: number) => (
  <span className="inline-flex items-center gap-1.5">
    <span className="h-1.5 rounded" style={{ width: Math.max(4, v * 0.5), background: v >= 66 ? "#22c55e" : v >= 33 ? "#f59e0b" : "#f43f5e" }} />
    <span>{v}</span>
  </span>
);

export default function Investors() {
  const { data: f } = useInvestors();
  if (!f) return <PageSkeleton />;
  if (!f.available)
    return <main className="max-w-3xl mx-auto p-6"><EmptyState title="Scores investisseurs indisponibles" hint="Actions/ETF requis." /></main>;

  const cols: Col[] = [
    { key: "symbol", label: "Actif" },
    { key: "sector", label: "Secteur", render: (v) => <span className="text-muted text-xs">{v}</span> },
    { key: "graham", label: "Graham (value)", num: true, render: bar },
    { key: "fisher", label: "Fisher (qualité)", num: true, render: bar },
    { key: "thiel", label: "Thiel (moat)", num: true, render: bar },
    { key: "schwab", label: "Schwab (4IR)", num: true, render: bar },
    { key: "overall", label: "Global", num: true, render: (v) => <b style={{ color: v >= 60 ? "#22c55e" : v >= 35 ? "#f59e0b" : "#f43f5e" }}>{v}</b> },
  ];

  const investors = [
    ["Benjamin Graham", "L'Investisseur intelligent", "Value défensive : rentabilité stable, faible dette, PER/PB raisonnables (Graham number), FCF positif."],
    ["Philip Fisher", "Actions ordinaires, profits extraordinaires", "Qualité-croissance : marges élevées, croissance du CA et des bénéfices, ROIC, conversion FCF."],
    ["Peter Thiel", "Zero to One", "Monopole/moat : marges brutes très élevées (pricing power), ROIC dominant, machine à cash, peu de dette."],
    ["Klaus Schwab", "4ᵉ révolution industrielle", "Exposition thématique : IA, semis, robotique, biotech, énergie propre, blockchain, cyber, cloud, espace, VE, fintech."],
  ];

  return (
    <main className="max-w-[1300px] mx-auto p-5 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Doctrines d'investisseurs</h1>
      <StepBanner active="investors" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {investors.map(([n, b, d]) => (
          <div key={n} className="card p-4"><div className="font-medium">{n}</div>
            <div className="text-xs text-accent2">{b}</div>
            <div className="text-muted text-xs mt-1.5">{d}</div></div>
        ))}
      </div>
      <p className="text-muted text-xs">{f.method} · Le score <b>global</b> alimente la <a href="/conviction" className="text-accent">note de conviction</a> (5ᵉ composante). Clique un en-tête pour trier.</p>
      <section className="card p-4">
        <SortableTable rows={f.rows} cols={cols} filterKeys={["symbol", "sector"]} csvName="investisseurs" dense
          initialSort={{ key: "overall", dir: "desc" }} />
      </section>
    </main>
  );
}
