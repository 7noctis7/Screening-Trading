// KILL-SWITCH DRAWDOWN — pourquoi le robot n'achète rien (17/11).
//
// Constaté le 16/11 : la page expliquait l'absence d'achats par le plancher de ligne, alors
// que c'était le kill-switch qui bloquait TOUT, y compris le rachat de QQQ. Le bandeau dit
// désormais la vraie cause, avec la même règle que le robot (`/api/positions.kill_switch`,
// calculé par `packages/execution/live_guards.etat_courant`) : rien n'est recalculé ici.

type EtatKillSwitch = {
  available?: boolean;
  breach?: boolean;
  drawdown?: number;
  limit?: number;
  fenetre?: number;
  peak?: number;
  last?: number;
  reprise?: number;
  depuis?: string | null;
};

const usd = (x?: number | null) => (x ?? 0).toLocaleString("fr-FR", { maximumFractionDigits: 0 });
const pct = (x?: number | null) => `${((x ?? 0) * 100).toFixed(1)} %`;

export function BandeauKillSwitch({ etat }: { etat?: EtatKillSwitch | null }) {
  if (!etat?.available || !etat.breach) return null;
  return (
    <section className="card p-4" style={{ borderColor: "#ef4444" }}>
      <p className="text-sm">
        <b>Kill-switch actif : aucun achat.</b> Le compte est à {pct(etat.drawdown)} sous son plus
        haut des {etat.fenetre} dernières séances (${usd(etat.peak)}), au-delà du seuil
        de {pct(etat.limit)}.
      </p>
      <p className="text-muted text-xs mt-1">
        Les achats reprennent quand le compte repasse au-dessus de ${usd(etat.reprise)}, ou quand
        ce plus haut sort de la fenêtre. Les ventes restent permises : un garde-fou ne vend jamais
        d'office. Réglages : <code>max_drawdown_pct</code> et <code>drawdown_window_sessions</code> dans
        {" "}<code>config/risk.yaml</code>. Dernier point d'equity : {etat.depuis ?? "n/d"}.
      </p>
    </section>
  );
}
