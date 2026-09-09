"use client";
import { useFundamentals } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { SortableTable, type Col } from "@/components/SortableTable";
import { StepBanner } from "@/components/Pipeline";
import { IR } from "@/lib/ir";
import { ReportButton } from "@/components/ReportButton";

const RC: Record<string, string> = { BUY: "#22c55e", HOLD: "#9aa1ad", SELL: "#f43f5e" };
const pp = (x?: number) => (x == null ? "—" : `${(x * 100).toFixed(0)}%`);
const colorPct = (x: number) => (x > 0 ? "#22c55e" : x < 0 ? "#f43f5e" : "#9aa1ad");

export default function Fundamentals() {
  const { data: f } = useFundamentals();
  if (!f) return <PageSkeleton />;
  if (!f.available)
    return <main className="max-w-3xl mx-auto p-6"><EmptyState title="Aucun compte d'entreprise disponible" hint="Une crypto ou une devise n'a ni chiffre d'affaires ni bénéfice : il n'y a rien à analyser ici." /></main>;

  const cols: Col[] = [
    { key: "symbol", label: "Actif", render: (v, row) => (<span className="inline-flex items-center gap-1.5"><IR ticker={v} name={row.name} assetClass={row.asset_class} className="mono text-accent hover:underline" /><ReportButton ticker={v} assetClass={row.asset_class} /></span>) },
    { key: "sector", label: "Secteur", render: (v) => <span className="text-muted text-xs">{v}</span> },
    { key: "per", label: "Prix / bénéfices", num: true, title: "Combien d'années de bénéfices actuels il faut pour rembourser le prix de l'action. Plus c'est bas, moins on paie cher." },
    { key: "ps", label: "Prix / ventes", num: true, title: "Le prix de l'action rapporté au chiffre d'affaires par action. Utile quand l'entreprise ne fait pas encore de bénéfices.", render: (v) => (v == null ? "—" : v) },
    { key: "pb", label: "Prix / patrimoine", num: true, title: "Le prix payé rapporté à ce que l'entreprise possède réellement, une fois ses dettes déduites." },
    { key: "roe", label: "Rendement des capitaux", num: true, title: "Ce que l'entreprise gagne chaque année pour 100 € que les actionnaires y ont laissés.", render: pp, csv: (v) => v },
    { key: "net_margin", label: "Marge nette", num: true, title: "Sur 100 € de ventes, combien restent en bénéfice une fois tout payé.", render: pp, csv: (v) => v },
    { key: "fcf_yield", label: "Cash généré / prix", num: true, title: "L'argent réellement dégagé chaque année, rapporté au prix payé. C'est le rendement en argent sonnant.", render: pp, csv: (v) => v },
    { key: "margin_of_safety", label: "Décote estimée", num: true, csv: (v) => v, title: "Écart entre ce que l'entreprise semble valoir et son prix actuel. Positif = elle paraît moins chère qu'elle ne vaut.",
      render: (v) => (v == null ? "—" : <span style={{ color: colorPct(v) }}>{(v * 100).toFixed(0)}%</span>) },
    { key: "f_score", label: "Solidité (sur 9)", num: true, title: "Neuf contrôles de bonne santé financière (rentabilité, dettes, marges). 9 = tout va bien.",
      render: (v) => <span style={{ color: v >= 7 ? "#22c55e" : v >= 4 ? "#f59e0b" : "#f43f5e" }}>{v}/9</span> },
    { key: "altman_z", label: "Risque de faillite", num: true, title: "Au-dessus de 2,99 l'entreprise est solide ; en dessous de 1,81 elle est en danger ; entre les deux, zone grise.",
      render: (v, r) => <span style={{ color: r.altman_zone === "sûr" ? "#22c55e" : r.altman_zone === "gris" ? "#f59e0b" : "#f43f5e" }}>{v}</span> },
    { key: "tech_score", label: "Tendance du cours", num: true, title: "Ce que dit le graphique en ce moment : le cours monte, baisse, ou hésite.",
      render: (v, r) => <span style={{ color: r.tech_label === "haussier" ? "#22c55e" : r.tech_label === "baissier" ? "#f43f5e" : "#9aa1ad" }}>{v}</span> },
    { key: "combined_score", label: "Note d'ensemble", num: true, title: "La santé de l'entreprise et la tendance du cours, réunies en une seule note.", render: (v) => <b>{v}</b> },
    { key: "rating", label: "Avis", align: "right", title: "BUY : les deux voyants sont au vert. HOLD : sans avis tranché. SELL : les deux sont au rouge. Ce n'est pas un conseil en investissement.",
      render: (v) => <span className="font-sans font-medium" style={{ color: RC[v] }}>{v}</span> },
  ];

  return (
    <main className="max-w-[1500px] mx-auto p-5 space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">La santé des entreprises</h1>
        <p className="text-muted text-sm mt-1 max-w-3xl">
          Ici on ne regarde pas le graphique, on regarde les comptes : est-ce que l'entreprise
          gagne de l'argent, est-elle endettée, son prix est-il raisonnable ? Un cours qui monte
          ne dit rien de la solidité de ce qu'il y a derrière.
        </p>
      </div>
      <StepBanner active="fundamentals" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card p-4"><div className="text-muted text-xs uppercase">Source</div><div className="text-lg mt-1">{f.source}</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Entreprises analysées</div><div className="text-lg mono mt-1">{f.n}{f.total_equities ? <span className="text-muted text-sm"> / {f.total_equities}</span> : null}</div></div>
        <div className="card p-4" title="Comptes solides et tendance du cours favorable."><div className="text-muted text-xs uppercase">Les deux voyants au vert</div><div className="text-lg mono mt-1" style={{ color: "#22c55e" }}>{f.buys}</div></div>
        <div className="card p-4" title="Comptes fragiles et tendance du cours défavorable."><div className="text-muted text-xs uppercase">Les deux voyants au rouge</div><div className="text-lg mono mt-1" style={{ color: "#f43f5e" }}>{(f.rows ?? []).filter((r: any) => r.rating === "SELL").length}</div></div>
      </div>
      {f.capped && (
        <div className="card p-3 text-xs" style={{ borderColor: "color-mix(in srgb, var(--warn) 40%, transparent)" }}>
          ⚠️ Seulement <b>{f.n}</b> entreprises analysées sur {f.total_equities} : une limite volontaire arrête l'analyse avant la fin.
          Pour en couvrir davantage, augmentez <code className="mono">QUANT_FUND_MAX</code> dans le fichier <code className="mono">.env</code>.
        </div>
      )}
      {!f.capped && String(f.source ?? "").startsWith("réel") && (
        <p className="text-muted2 text-xs">✓ {f.n} entreprises sur {f.total_equities} avec des chiffres <b>réels</b>. Pour chacune on essaie plusieurs sources l'une après l'autre (yfinance, puis FMP, puis les dépôts officiels à la SEC). Celles dont on ne trouve les comptes nulle part sont retirées du tableau plutôt qu'estimées.</p>
      )}
      <p className="text-muted text-xs">{f.method} · Seules les <b>actions et les ETF</b> ont des comptes à analyser : une crypto, une devise ou une matière première n'a ni chiffre d'affaires ni bilan. <b>Cliquez un titre de colonne pour trier</b> (▲/▼), filtrez, ou téléchargez le tableau.</p>
      <section className="card p-4">
        <SortableTable rows={f.rows} cols={cols} filterKeys={["symbol", "sector"]} csvName="fondamentaux" dense
          initialSort={{ key: "combined_score", dir: "desc" }} />
      </section>
    </main>
  );
}
