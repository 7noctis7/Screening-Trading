const palette: Record<string, string> = { expansion:"#22c55e", recovery:"#3b82f6", slowdown:"#f59e0b", recession:"#ef4444" };
export function RegimeBanner({ regime }: { regime: any }) {
  if (!regime) return null;
  const c = palette[regime.cycle] ?? "#9aa1ab";
  return (
    <div className="card p-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />
        <span className="capitalize font-medium">{regime.cycle}</span>
        <span className="text-muted">· {regime.risk_mode}</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full"
          title={Object.entries(regime.macro_sources ?? {}).map(([k, v]) => `${k}: ${v}`).join(" · ")}
          style={{ background: regime.macro_real ? "color-mix(in srgb,#22c55e 16%,transparent)" : "color-mix(in srgb,#f59e0b 18%,transparent)",
                   color: regime.macro_real ? "#22c55e" : "#f59e0b" }}>
          {regime.macro_real ? "macro réelle" : "macro synthétique"}</span>
      </div>
      <div className="mono text-sm text-muted">
        VIX {regime.vix?.toFixed?.(0) ?? "—"} · exposition ×{regime.exposure_multiplier}
      </div>
    </div>
  );
}
