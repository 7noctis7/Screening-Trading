"use client";
// Error boundary global (App Router) — évite l'écran blanc si l'API tombe.
export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <main className="max-w-xl mx-auto p-10 text-center space-y-4">
      <div className="text-3xl">⚠️</div>
      <h1 className="text-lg font-semibold">Données momentanément indisponibles</h1>
      <p className="text-muted text-sm">
        Impossible de joindre l'API du terminal. Vérifie qu'elle est lancée
        (<code className="mono">uvicorn apps.api.main:app</code>) puis réessaie.
      </p>
      <p className="text-muted text-xs mono">{error?.message}</p>
      <button onClick={reset}
        className="px-4 py-2 rounded-lg bg-accent text-white text-sm hover:opacity-90">
        Réessayer
      </button>
    </main>
  );
}
