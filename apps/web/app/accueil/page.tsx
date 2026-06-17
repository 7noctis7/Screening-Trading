"use client";
import Link from "next/link";

// Page d'accueil : présentation, rôle de chaque fenêtre, et glossaire/méthodologie déroulant.

const WINDOWS: [string, string, string][] = [
  ["/", "Dashboard", "Vue d'ensemble : performance, régime de marché, playbook VIX, top screener (facteurs + ML), humeur de marché."],
  ["/themes", "Thèmes de marché", "Heatmap de performance par secteur (4ᵉ révolution industrielle) — où va l'argent."],
  ["/ml", "Signaux ML", "Probabilité de hausse à ~1 mois (modèle entraîné en CV purgée) + validation : walk-forward, calibration, conformal, meta-labeling, drift."],
  ["/fundamentals", "Fondamentaux", "Ratios (PER, EV/EBITDA, P/B, ROE), DCF, Piotroski, Altman Z, note technique et note combinée. Reco BUY/HOLD/SELL."],
  ["/sentiment", "Sentiment & news", "Humeur par position (FinBERT / lexique / momentum), titres d'actualité (RSS gratuit)."],
  ["/universe", "Univers", "Les 929 actifs (actions, ETF, forex, crypto, commodités) — recherche, filtres, export CSV."],
  ["/data", "Données", "Qualité des données (NaN, outliers, fraîcheur), couverture réelle par classe d'actifs."],
  ["/portfolio", "Portefeuille & Analyse", "Mesures relatives, Monte-Carlo, attribution, corrélation, revue experte."],
  ["/risk", "Risque", "VaR/CVaR/EVT/GARCH, backtest de VaR, risque factoriel, budget de risque, limites, stress-tests, allocation optimale, multi-stratégie."],
  ["/positions", "Positions", "Positions ouvertes + clic sur un actif → graphique technique (volumes, MM, marqueurs, ligne d'info)."],
  ["/trades", "Trades", "Historique et trades en cours, statistiques (win rate, profit factor, turnover)."],
  ["/live", "Portefeuille réel", "Connexion Alpaca (actions, paper) / Bitmart (crypto), ordres cibles, réconciliation, coûts d'exécution (TCA)."],
];

function G({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <details className="card p-3">
      <summary className="cursor-pointer text-sm font-medium select-none">{term}</summary>
      <div className="text-sm text-muted mt-2 space-y-1 font-sans">{children}</div>
    </details>
  );
}

export default function Accueil() {
  return (
    <main className="max-w-4xl mx-auto p-6 space-y-6">
      <section className="card p-6">
        <h1 className="text-2xl font-semibold tracking-tight">Quant Terminal</h1>
        <p className="text-muted mt-2">
          Terminal de <b>screening</b> et de <b>trading systématique</b> multi-actifs (actions, ETF, forex, crypto,
          commodités), de niveau hedge-fund. Données réelles, ML anti-fuite, gestion du risque institutionnelle,
          exécution paper. <b>Aide à la décision — pas un conseil en investissement.</b>
        </p>
        <div className="flex gap-2 mt-3 text-xs flex-wrap">
          <span className="px-2 py-1 rounded-full" style={{ background: "var(--surface3)" }}>Paper par défaut</span>
          <span className="px-2 py-1 rounded-full" style={{ background: "var(--surface3)" }}>Point-in-time (anti-fuite)</span>
          <span className="px-2 py-1 rounded-full" style={{ background: "var(--surface3)" }}>⌘K pour naviguer</span>
        </div>
      </section>

      <section>
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Les fenêtres</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {WINDOWS.map(([href, name, desc]) => (
            <Link key={href} href={href} className="card p-4 hover:bg-surfaceAlt transition-colors">
              <div className="font-medium">{name}</div>
              <div className="text-muted text-sm mt-1">{desc}</div>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Méthodologie & glossaire (clique pour déplier)</h2>
        <div className="space-y-2">
          <G term="Turnover annualisé (ex. 9,5×)">
            <p><b>Définition</b> : volume tradé sur l'année rapporté au capital. <b>9,5×</b> = sur un an, on a acheté/vendu l'équivalent de ~9,5 fois la taille du portefeuille.</p>
            <p><b>Calcul</b> : Σ(|qté×prix d'entrée| + |qté×prix de sortie|) / equity moyenne × (252 / nb de jours).</p>
            <p><b>Interprétation</b> : élevé = rotation rapide → plus de frais/slippage. À surveiller : un alpha brut peut être mangé par les coûts. La <Link href="/live" className="text-accent">bande de non-trading</Link> sert justement à réduire ce churn.</p>
          </G>
          <G term="VaR / CVaR 95 %">
            <p><b>VaR 95 %</b> : perte qu'on ne dépasse pas dans 95 % des cas (sur l'horizon). <b>CVaR</b> : perte moyenne dans les 5 % pires cas (plus prudent).</p>
            <p><b>Sources/calcul</b> : historique (quantile des rendements) + paramétrique. La <b>VaR Cornish-Fisher</b> corrige l'asymétrie/épaisseur des queues ; l'<b>EVT</b> modélise les extrêmes (99,9 %).</p>
            <p><b>Interprétation</b> : plus la VaR/CVaR est élevée, plus le risque de perte est grand. À croiser avec le <b>backtest de VaR (Kupiec)</b> qui vérifie que le modèle est fiable.</p>
          </G>
          <G term="GARCH(1,1)">
            <p><b>Rôle</b> : prévoir la volatilité de demain en tenant compte du « volatility clustering » (les chocs s'enchaînent).</p>
            <p><b>Interprétation</b> : une vol prévue qui grimpe = marché qui se tend → réduire l'exposition.</p>
          </G>
          <G term="Risque factoriel (ACP) & budget de risque">
            <p><b>ACP</b> : part du risque expliquée par quelques facteurs communs (= risque systématique, non diversifiable).</p>
            <p><b>Budget de risque</b> : contribution de chaque position à la volatilité totale (≠ poids en capital). Permet d'équilibrer le <i>risque</i>, pas seulement le montant investi.</p>
          </G>
          <G term="Sharpe probabiliste (PSR) & déflaté (DSR)">
            <p><b>PSR</b> : probabilité que le vrai Sharpe soit positif (tient compte de la taille d'échantillon et des queues).</p>
            <p><b>DSR</b> : PSR corrigé du nombre de stratégies essayées → garde-fou anti-« data mining ». Proche de 1 = robuste, proche de 0 = sans doute de la chance.</p>
          </G>
          <G term="HRP / Min-variance / Risk parity (allocation optimale)">
            <p><b>HRP</b> (López de Prado) : alloue par grappes de corrélation, sans inverser la covariance (stable). <b>Min-variance</b> : minimise la vol. <b>Risk parity (ERC)</b> : chaque actif contribue également au risque.</p>
            <p><b>Usage</b> : compare ton allocation actuelle à ces 3 références pour rééquilibrer.</p>
          </G>
          <G term="ML : CV purgée, calibration, conformal, meta-labeling">
            <p><b>CV purgée + embargo</b> : validation sans fuite du futur (labels chevauchants neutralisés).</p>
            <p><b>Calibration (Brier)</b> : une proba 0,8 doit se réaliser ~80 % du temps. <b>Conformal</b> : garantit un taux de couverture. <b>Meta-labeling</b> : un 2ᵉ modèle filtre les faux positifs ; le <b>sizing</b> module la taille selon la confiance.</p>
          </G>
          <G term="Fondamentaux : DCF, Piotroski, Altman Z">
            <p><b>DCF</b> : valeur intrinsèque par actualisation des flux → marge de sécurité (intrinsèque/prix − 1).</p>
            <p><b>Piotroski (0-9)</b> : solidité financière (rentabilité, levier, marges). <b>Altman Z</b> : risque de faillite (Z&gt;2,99 sûr, &lt;1,81 détresse).</p>
            <p><b>Note combinée</b> = 60 % fondamental + 40 % technique.</p>
          </G>
          <G term="Playbook VIX">
            <p>Le VIX mesure la peur du marché. <b>&lt;20</b> calme (exposition pleine) · <b>20-30</b> tendu (réduite) · <b>&gt;30</b> panique (défensif). L'exposition du portefeuille est modulée automatiquement.</p>
          </G>
        </div>
      </section>

      <p className="text-muted2 text-xs">⚠️ Données synthétiques ou réelles selon votre configuration (YAHOO.db). Outil éducatif — aucune recommandation personnalisée. Paper trading par défaut.</p>
    </main>
  );
}
