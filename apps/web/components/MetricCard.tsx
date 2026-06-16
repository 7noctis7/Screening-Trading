export function MetricCard({ label, value, tone }: { label: string; value: string; tone?: "pos" | "neg" }) {
  const color = tone === "pos" ? "text-pos" : tone === "neg" ? "text-neg" : "text-fg";
  return (
    <div className="card p-4">
      <div className="text-muted text-xs uppercase tracking-wide">{label}</div>
      <div className={`mono text-2xl mt-1 ${color}`}>{value}</div>
    </div>
  );
}
