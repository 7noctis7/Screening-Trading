// État de chargement global (App Router).
export default function Loading() {
  return (
    <main className="max-w-6xl mx-auto p-6 space-y-3">
      <div className="h-6 w-48 rounded bg-surfaceAlt animate-pulse" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card p-4 h-20 animate-pulse" />
        ))}
      </div>
      <div className="card h-60 animate-pulse" />
    </main>
  );
}
