"use client";
// Primitives UI — skeletons de chargement + états vides (best practice : jamais d'écran nu).

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-surfaceAlt ${className}`} />;
}

export function PageSkeleton() {
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <Skeleton className="h-7 w-48" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
      </div>
      <Skeleton className="h-56" />
      <Skeleton className="h-40" />
    </main>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="card p-8 text-center">
      <div className="text-muted text-sm">{title}</div>
      {hint && <div className="text-muted2 text-xs mt-1">{hint}</div>}
    </div>
  );
}
