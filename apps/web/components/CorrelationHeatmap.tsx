const cell = (v: number) => {
  const r = Math.round(120 + 100 * Math.max(0, v));
  const b = Math.round(120 + 100 * Math.max(0, -v));
  return `rgb(${r},100,${b})`;
};
export function CorrelationHeatmap({ data }: { data: any }) {
  if (!data?.symbols) return null;
  const { symbols, matrix, clusters } = data;
  return (
    <section className="card p-4">
      <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Corrélation</h2>
      <p className="text-xs text-muted mb-3">Clusters : {JSON.stringify(clusters)}</p>
      {/* scroll horizontal contenu DANS la carte (sinon la matrice déborde l'écran en mobile) */}
      <div className="overflow-x-auto -mx-1 px-1">
        <table className="mono" style={{ borderSpacing: 3, borderCollapse: "separate" }}>
          <tbody>
            <tr><th className="sticky left-0 z-10" style={{ background: "var(--surface)" }}></th>
              {symbols.map((s: string) => <th key={s} className="text-muted text-xs px-1 whitespace-nowrap">{s}</th>)}</tr>
            {matrix.map((row: number[], i: number) => (
              <tr key={i}>
                <th className="text-muted text-xs pr-1 text-right sticky left-0 z-10 whitespace-nowrap"
                  style={{ background: "var(--surface)" }}>{symbols[i]}</th>
                {row.map((v, j) => (
                  <td key={j} className="text-center text-xs text-white rounded" style={{ background: cell(v), padding: "6px", minWidth: 38 }}>
                    {v.toFixed(2)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
