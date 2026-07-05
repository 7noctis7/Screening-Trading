import { cyclePalette } from "@/lib/tokens";

// Bandeau régime : phase du cycle (pastille colorée) + risk-on/off (badge OUTLINE désaturé, tokens régime —
// jamais le plein du P&L) + VIX + qualité macro. Couleurs 100 % via tokens (aucun hex en dur).
export function RegimeBanner({ regime }: { regime: any }) {
  if (!regime) return null;
  const c = cyclePalette[regime.cycle] ?? "var(--muted)";
  const off = /off/i.test(String(regime.risk_mode ?? ""));
  const riskLabel = off ? "risk-off" : "risk-on";
  return (
    <div className="card p-4 flex items-center justify-between flex-wrap gap-2">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="h-2.5 w-2.5 rounded-full pulse-dot" style={{ background: c }} />
        <span className="capitalize font-medium">{regime.cycle}</span>
        <span className={`badge-regime ${off ? "off" : "on"}`}>{riskLabel}</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full"
          title={Object.entries(regime.macro_sources ?? {}).map(([k, v]) => `${k}: ${v}`).join(" · ")}
          style={{ background: regime.macro_real ? "color-mix(in srgb, var(--accent) 16%, transparent)" : "color-mix(in srgb, var(--warn) 18%, transparent)",
                   color: regime.macro_real ? "var(--accent2)" : "var(--warn)" }}>
          {regime.macro_real ? "macro réelle" : "macro synthétique"}</span>
      </div>
      <div className="mono text-sm text-muted tnum">
        VIX {regime.vix?.toFixed?.(0) ?? "—"} · exposition ×{regime.exposure_multiplier}
      </div>
    </div>
  );
}
