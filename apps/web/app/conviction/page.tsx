"use client";
import { useConviction } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { SortableTable, type Col } from "@/components/SortableTable";
import { StepBanner } from "@/components/Pipeline";

const z = (v?: number) => (v == null ? "—" : <span style={{ color: v > 0 ? "#22c55e" : v < 0 ? "#f43f5e" : "#9aa1ad" }}>{v.toFixed(2)}</span>);

export default function Conviction() {
  const { data: c } = useConviction();
  if (!c) return <PageSkeleton />;
  if (!c.available)
    return <main className="max-w-3xl mx-auto p-6"><EmptyState title="Conviction indisponible" hint="Signaux insuffisants." /></main>;

  const cols: Col[] = [
    { key: "symbol", label: "Actif" },
    { key: "sector", label: "Secteur", render: (v) => <span className="text-muted text-xs">{v}</span> },
    { key: "trend", label: "Tendance", num: true, render: z, csv: (v) => v },
    { key: "ml", label: "ML", num: true, render: z, csv: (v) => v },
    { key: "fundamental", label: "Fondam.", num: true, render: z, csv: (v) => v },
    { key: "sentiment", label: "Sentiment", num: true, render: z, csv: (v) => v },
    { key: "conviction", label: "Conviction", num: true, render: (v) => <b style={{ color: v > 0 ? "#22c55e" : "#f43f5e" }}>{v.toFixed(2)}</b> },
    { key: "target_weight", label: "Poids cible", num: true, align: "right",
      render: (v) => (v > 0 ? `${(v * 100).toFixed(1)}%` : "—"), csv: (v) => v },
  ];

  return (
    <main className="max-w-6xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Conviction — signaux fusionnés</h1>
      <StepBanner active="screener" />
      <div className="card p-4 text-sm">
        <b>La synthèse de toutes les fenêtres en une seule note.</b>
        <p className="text-muted mt-1">{c.method}</p>
        <p className="text-muted2 text-xs mt-2">Les colonnes Tendance/ML/Fondam./Sentiment sont des <b>z-scores</b> (écart à la moyenne de l'univers). La <b>conviction</b> est leur moyenne. Le <b>poids cible</b> = allocation conviction × inverse-volatilité, plafonnée à 20 % — c'est l'allocation « best practice » qui fait converger les lentilles sous contrôle du risque.</p>
      </div>
      <section className="card p-4">
        <SortableTable rows={c.rows} cols={cols} filterKeys={["symbol", "sector"]} csvName="conviction"
          initialSort={{ key: "conviction", dir: "desc" }} />
      </section>
    </main>
  );
}
