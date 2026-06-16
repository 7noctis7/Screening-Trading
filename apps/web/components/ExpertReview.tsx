const lst = (title: string, items: string[], color: string) =>
  items?.length ? (
    <div className="mb-2">
      <div className="text-xs font-semibold" style={{ color }}>{title}</div>
      <ul className="mt-1 pl-5 text-sm list-disc">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </div>
  ) : null;

export function ExpertReview({ review }: { review: any }) {
  if (!review) return null;
  const s = review.health_score;
  const color = s >= 65 ? "#22c55e" : s < 45 ? "#ef4444" : "#f59e0b";
  return (
    <section className="card p-4">
      <div className="flex justify-between items-center mb-3">
        <h2 className="text-sm uppercase tracking-wide text-muted">Revue experte (CFA/FRM/CPA/CAIA)</h2>
        <div className="mono text-2xl" style={{ color }}>{s}<span className="text-sm text-muted">/100</span></div>
      </div>
      {lst("Forces", review.strengths, "#22c55e")}
      {lst("Faiblesses", review.weaknesses, "#f59e0b")}
      {lst("Risques", review.risks, "#ef4444")}
      {lst("Recommandations", review.recommendations, "#3b82f6")}
      <p className="text-xs text-muted italic mt-2">{review.disclaimer}</p>
    </section>
  );
}
