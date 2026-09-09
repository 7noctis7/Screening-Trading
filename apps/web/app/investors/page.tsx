"use client";
import { useInvestors } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { SortableTable, type Col } from "@/components/SortableTable";
import { StepBanner } from "@/components/Pipeline";
import { IR } from "@/lib/ir";

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
    return <main className="max-w-3xl mx-auto p-6"><EmptyState title="Notes indisponibles" hint="Ces quatre grilles ne s'appliquent qu'aux actions et aux ETF : elles ont besoin des comptes d'une entreprise." /></main>;

  const cols: Col[] = [
    { key: "symbol", label: "Actif", render: (v, row) => <IR ticker={v} name={row.name} assetClass={row.asset_class} className="mono text-accent hover:underline" /> },
    { key: "sector", label: "Secteur", render: (v) => <span className="text-muted text-xs">{v}</span> },
    { key: "graham", label: "Graham · payée pas cher", num: true, render: bar },
    { key: "fisher", label: "Fisher · qualité et croissance", num: true, render: bar },
    { key: "thiel", label: "Thiel · position dominante", num: true, render: bar },
    { key: "schwab", label: "Schwab · technologies d'avenir", num: true, render: bar },
    { key: "overall", label: "Moyenne des quatre", num: true, render: (v) => <b style={{ color: v >= 60 ? "#22c55e" : v >= 35 ? "#f59e0b" : "#f43f5e" }}>{v}</b> },
  ];

  const investors = [
    ["Benjamin Graham", "L'Investisseur intelligent", "Acheter solide et pas cher : des bénéfices réguliers, peu de dettes, un prix raisonnable par rapport aux profits et au patrimoine, et de l'argent qui rentre vraiment en caisse."],
    ["Philip Fisher", "Actions ordinaires, profits extraordinaires", "Payer le prix pour de la qualité : de grosses marges, des ventes et des bénéfices qui grandissent, un capital bien employé, et des profits qui se transforment en argent liquide."],
    ["Peter Thiel", "Zero to One", "Chercher les entreprises quasi sans concurrent : marges très élevées (elles fixent leurs prix), rentabilité écrasante, machine à cash, peu de dettes."],
    ["Klaus Schwab", "4ᵉ révolution industrielle", "Miser sur les technologies qui changent le monde : intelligence artificielle, puces, robotique, biotech, énergies propres, blockchain, cybersécurité, cloud, espace, véhicules électriques, finance numérique."],
  ];

  return (
    <main className="max-w-[1300px] mx-auto p-5 space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Quatre façons de choisir une action</h1>
        <p className="text-muted text-sm mt-1 max-w-3xl">
          Quatre investisseurs célèbres, quatre manières de juger une entreprise. Chaque titre
          reçoit une note sur 100 selon chacune de ces grilles : un même titre peut être excellent
          pour l'un et médiocre pour l'autre — c'est normal, ils ne cherchent pas la même chose.
        </p>
      </div>
      <StepBanner active="investors" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {investors.map(([n, b, d]) => (
          <div key={n} className="card p-4"><div className="font-medium">{n}</div>
            <div className="text-xs text-accent2">{b}</div>
            <div className="text-muted text-xs mt-1.5">{d}</div></div>
        ))}
      </div>
      <p className="text-muted text-xs">{f.method} · La <b>moyenne des quatre</b> est l'un des cinq éléments qui composent la <a href="/conviction" className="text-accent">note de conviction</a>. Cliquez un titre de colonne pour trier.</p>
      <section className="card p-4">
        <SortableTable rows={f.rows} cols={cols} filterKeys={["symbol", "sector"]} csvName="investisseurs" dense
          initialSort={{ key: "overall", dir: "desc" }} />
      </section>
    </main>
  );
}
