"use client";
import { useMemo, useState } from "react";
import { downloadCsv } from "@/lib/csv";

export type Col = {
  key: string;
  label: string;
  align?: "left" | "right";
  num?: boolean;                              // tri numérique
  render?: (v: any, row: any) => React.ReactNode;
  csv?: (v: any, row: any) => string | number | null;
};

// Tableau réutilisable : tri par colonne (clic en-tête) + filtre texte + export CSV.
export function SortableTable({ rows, cols, filterKeys, csvName, initialSort, pageSize = 0 }:
  { rows: any[]; cols: Col[]; filterKeys?: string[]; csvName?: string;
    initialSort?: { key: string; dir: "asc" | "desc" }; pageSize?: number }) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState(initialSort ?? { key: cols[0].key, dir: "asc" as "asc" | "desc" });

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    const keys = filterKeys ?? cols.map((c) => c.key);
    let r = !s ? rows : rows.filter((row) => keys.some((k) => String(row[k] ?? "").toLowerCase().includes(s)));
    const col = cols.find((c) => c.key === sort.key);
    r = [...r].sort((a, b) => {
      const va = a[sort.key], vb = b[sort.key];
      let c: number;
      if (col?.num) c = (Number(va) || -Infinity) - (Number(vb) || -Infinity);
      else c = String(va ?? "").localeCompare(String(vb ?? ""));
      return sort.dir === "asc" ? c : -c;
    });
    return r;
  }, [rows, q, sort, cols, filterKeys]);

  const shown = pageSize > 0 ? filtered.slice(0, pageSize) : filtered;
  const toggle = (k: string) =>
    setSort((s) => (s.key === k ? { key: k, dir: s.dir === "asc" ? "desc" : "asc" } : { key: k, dir: "desc" }));

  return (
    <div>
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        {filterKeys !== null && (
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filtrer…"
            className="text-sm flex-1 min-w-[160px]" />
        )}
        <span className="text-xs text-muted">{shown.length}{filtered.length !== rows.length ? ` / ${rows.length}` : ""}</span>
        {csvName && (
          <button onClick={() => downloadCsv(csvName, cols.map((c) => c.label),
            shown.map((row) => cols.map((c) => (c.csv ? c.csv(row[c.key], row) : row[c.key] ?? ""))))}
            className="text-xs px-3 py-1.5 rounded-lg border border-border text-muted hover:text-fg hover:bg-surfaceAlt">⬇ CSV</button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>{cols.map((c) => (
              <th key={c.key} onClick={() => toggle(c.key)} title="Trier"
                className="cursor-pointer select-none whitespace-nowrap hover:text-fg"
                style={{ textAlign: c.align ?? (c.num ? "right" : "left") }}>
                {c.label}{sort.key === c.key
                  ? <span style={{ color: "var(--accent2)" }}>{sort.dir === "asc" ? " ▲" : " ▼"}</span>
                  : <span style={{ opacity: 0.35 }}> ↕</span>}
              </th>))}</tr>
          </thead>
          <tbody>{shown.map((row, i) => (
            <tr key={row.symbol ?? row.id ?? i}>
              {cols.map((c) => (
                <td key={c.key} className={c.num ? "mono" : ""} style={{ textAlign: c.align ?? (c.num ? "right" : "left") }}>
                  {c.render ? c.render(row[c.key], row) : (row[c.key] ?? "—")}
                </td>))}
            </tr>))}</tbody>
        </table>
      </div>
    </div>
  );
}
