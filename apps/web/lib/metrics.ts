// Helpers de perf/série — partagés entre le Dashboard et les charts (equity/underwater).
// Aucune dépendance UI. Toute la math tourne côté client sur les JSON exportés (site statique).
export type Point = { t: string; v: number };

// Métriques annualisées (base 252 j) recalculées sur la fenêtre choisie.
export function statsFrom(eq: Point[]) {
  if (!eq || eq.length < 2) return null;
  const v = eq.map((p) => p.v);
  const r: number[] = [];
  for (let i = 1; i < v.length; i++) if (v[i - 1] > 0) r.push(v[i] / v[i - 1] - 1);
  const mean = r.reduce((a, b) => a + b, 0) / (r.length || 1);
  const sd = Math.sqrt(r.reduce((a, b) => a + (b - mean) ** 2, 0) / (r.length || 1));
  const dn = r.filter((x) => x < 0);
  const dsd = Math.sqrt(dn.reduce((a, b) => a + b * b, 0) / (dn.length || 1));
  let peak = v[0], mdd = 0;
  for (const x of v) { peak = Math.max(peak, x); mdd = Math.min(mdd, x / peak - 1); }
  const total = v[v.length - 1] / v[0] - 1;
  const cagr = r.length > 1 ? Math.pow(1 + total, 252 / r.length) - 1 : total;
  return {
    total_return: total, cagr,
    sharpe: sd > 0 ? (mean / sd) * Math.sqrt(252) : 0,
    sortino: dsd > 0 ? (mean / dsd) * Math.sqrt(252) : 0,
    max_drawdown: mdd,
  };
}

// Rebase une série pour qu'elle démarre à `base` au début de la fenêtre (comparaison équitable).
export function rebase(arr?: Point[], base = 10000): Point[] {
  if (!arr?.length || !arr[0].v) return arr ?? [];
  const f = base / arr[0].v;
  return arr.map((p) => ({ t: p.t, v: Math.round(p.v * f * 100) / 100 }));
}

// Série underwater (drawdown) dérivée d'une equity : dd[i] = v[i]/running_max − 1 (≤ 0).
export function underwater(eq: Point[]): Point[] {
  let peak = -Infinity;
  return (eq ?? []).map((p) => { peak = Math.max(peak, p.v); return { t: p.t, v: peak > 0 ? p.v / peak - 1 : 0 }; });
}

// Downsampling LTTB (Largest-Triangle-Three-Buckets) : réduit à `threshold` points en préservant
// la forme visuelle (pics/creux) — clé du 60 fps sur 2600+ points. Recalculé à chaque zoom.
export function lttb<T extends { v: number }>(data: T[], threshold: number): T[] {
  const n = data.length;
  if (threshold >= n || threshold < 3) return data;
  const sampled: T[] = [data[0]];
  const every = (n - 2) / (threshold - 2);
  let a = 0;
  for (let i = 0; i < threshold - 2; i++) {
    const rangeStart = Math.floor((i + 1) * every) + 1;
    const rangeEnd = Math.min(Math.floor((i + 2) * every) + 1, n);
    let avgX = 0, avgY = 0;
    const rangeLen = rangeEnd - rangeStart || 1;
    for (let j = rangeStart; j < rangeEnd; j++) { avgX += j; avgY += data[j].v; }
    avgX /= rangeLen; avgY /= rangeLen;
    const bucketStart = Math.floor(i * every) + 1;
    const bucketEnd = Math.floor((i + 1) * every) + 1;
    const ax = a, ay = data[a].v;
    let maxArea = -1, next = bucketStart;
    for (let j = bucketStart; j < bucketEnd; j++) {
      const area = Math.abs((ax - avgX) * (data[j].v - ay) - (ax - j) * (avgY - ay));
      if (area > maxArea) { maxArea = area; next = j; }
    }
    sampled.push(data[next]); a = next;
  }
  sampled.push(data[n - 1]);
  return sampled;
}
