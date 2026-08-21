"use client";
import Link from "next/link";

// GLOSSAIRE — extrait de la page d'accueil (2026-08-21). L'accueil accueillait le visiteur avec
// GARCH(1,1) et Cornish-Fisher : c'est une RÉFÉRENCE, pas une porte d'entrée. Le contenu est
// déplacé ici sans rien perdre ; chaque terme garde sa définition complète, précédée d'une
// phrase « en clair » pour qui n'a pas fait de finance quantitative.

function G({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <details className="card p-3">
      <summary className="cursor-pointer text-sm font-medium select-none">{term}</summary>
      <div className="text-sm text-muted mt-2 space-y-1 font-sans">{children}</div>
    </details>
  );
}

// Traductions « en clair » : une phrase, zéro jargon, avant la définition technique.
const EN_CLAIR: Record<string, string> = {
  "Turnover annualisé (ex. 9,5×)": "À quelle fréquence le portefeuille est renouvelé. Plus il tourne, plus les frais grignotent le résultat.",
  "VaR / CVaR 95 %": "Combien on peut perdre lors d'une mauvaise journée, et combien lors des pires.",
  "GARCH(1,1)": "Une façon de prévoir si le marché va être agité demain, sachant qu'une période agitée en appelle une autre.",
  "Risque factoriel (ACP) & budget de risque": "Quelle part du risque vient du marché entier plutôt que de vos choix, et combien chaque position y contribue.",
  "Sharpe probabiliste (PSR) & déflaté (DSR)": "La probabilité qu'un bon résultat ne soit pas simplement de la chance.",
  "HRP / Min-variance / Risk parity (allocation optimale)": "Trois façons de répartir l'argent entre les positions pour ne pas tout miser au même endroit.",
  "ML : CV purgée, calibration, conformal, meta-labeling": "Comment on empêche un modèle de tricher en regardant le futur, et comment on vérifie qu'il dit vrai.",
  "Fondamentaux : DCF, Piotroski, Altman Z": "Estimer ce que vaut vraiment une entreprise, si elle est solide, et si elle risque la faillite.",
  "Playbook VIX": "L'indicateur de peur du marché, et comment l'exposition est réduite quand il monte.",
};

function Clair({ term }: { term: string }) {
  const t = EN_CLAIR[term];
  return t ? <p className="text-fg"><b>En clair</b> : {t}</p> : null;
}

export default function Glossaire() {
  return (
    <main className="max-w-3xl mx-auto p-6 space-y-6">
      <header className="space-y-2">
        <Link href="/accueil" className="text-sm text-muted hover:text-fg">← Retour à l'accueil</Link>
        <h1 className="text-2xl font-bold tracking-tight">Glossaire</h1>
        <p className="text-muted">
          Chaque terme employé sur le site, expliqué d'abord en une phrase simple, puis en détail.
          Vous n'avez pas besoin de lire cette page pour utiliser le site — elle est là quand un mot
          vous arrête.
        </p>
      </header>
      <div className="space-y-2">
        <G term="Turnover annualisé (ex. 9,5×)">
            <Clair term={"Turnover annualisé (ex. 9,5×)"} />
          <p><b>Définition</b> : volume tradé sur l'année rapporté au capital. <b>9,5×</b> = sur un an, on a acheté/vendu l'équivalent de ~9,5 fois la taille du portefeuille.</p>
          <p><b>Calcul</b> : Σ(|qté×prix d'entrée| + |qté×prix de sortie|) / equity moyenne × (252 / nb de jours).</p>
          <p><b>Interprétation</b> : élevé = rotation rapide → plus de frais/slippage. À surveiller : un alpha brut peut être mangé par les coûts. La <Link href="/live" className="text-accent">bande de non-trading</Link> sert justement à réduire ce churn.</p>
        </G>
        <G term="VaR / CVaR 95 %">
            <Clair term={"VaR / CVaR 95 %"} />
          <p><b>VaR 95 %</b> : perte qu'on ne dépasse pas dans 95 % des cas (sur l'horizon). <b>CVaR</b> : perte moyenne dans les 5 % pires cas (plus prudent).</p>
          <p><b>Sources/calcul</b> : historique (quantile des rendements) + paramétrique. La <b>VaR Cornish-Fisher</b> corrige l'asymétrie/épaisseur des queues ; l'<b>EVT</b> modélise les extrêmes (99,9 %).</p>
          <p><b>Interprétation</b> : plus la VaR/CVaR est élevée, plus le risque de perte est grand. À croiser avec le <b>backtest de VaR (Kupiec)</b> qui vérifie que le modèle est fiable.</p>
        </G>
        <G term="GARCH(1,1)">
            <Clair term={"GARCH(1,1)"} />
          <p><b>Rôle</b> : prévoir la volatilité de demain en tenant compte du « volatility clustering » (les chocs s'enchaînent).</p>
          <p><b>Interprétation</b> : une vol prévue qui grimpe = marché qui se tend → réduire l'exposition.</p>
        </G>
        <G term="Risque factoriel (ACP) & budget de risque">
            <Clair term={"Risque factoriel (ACP) & budget de risque"} />
          <p><b>ACP</b> : part du risque expliquée par quelques facteurs communs (= risque systématique, non diversifiable).</p>
          <p><b>Budget de risque</b> : contribution de chaque position à la volatilité totale (≠ poids en capital). Permet d'équilibrer le <i>risque</i>, pas seulement le montant investi.</p>
        </G>
        <G term="Sharpe probabiliste (PSR) & déflaté (DSR)">
            <Clair term={"Sharpe probabiliste (PSR) & déflaté (DSR)"} />
          <p><b>PSR</b> : probabilité que le vrai Sharpe soit positif (tient compte de la taille d'échantillon et des queues).</p>
          <p><b>DSR</b> : PSR corrigé du nombre de stratégies essayées → garde-fou anti-« data mining ». Proche de 1 = robuste, proche de 0 = sans doute de la chance.</p>
        </G>
        <G term="HRP / Min-variance / Risk parity (allocation optimale)">
            <Clair term={"HRP / Min-variance / Risk parity (allocation optimale)"} />
          <p><b>HRP</b> (López de Prado) : alloue par grappes de corrélation, sans inverser la covariance (stable). <b>Min-variance</b> : minimise la vol. <b>Risk parity (ERC)</b> : chaque actif contribue également au risque.</p>
          <p><b>Usage</b> : compare ton allocation actuelle à ces 3 références pour rééquilibrer.</p>
        </G>
        <G term="ML : CV purgée, calibration, conformal, meta-labeling">
            <Clair term={"ML : CV purgée, calibration, conformal, meta-labeling"} />
          <p><b>CV purgée + embargo</b> : validation sans fuite du futur (labels chevauchants neutralisés).</p>
          <p><b>Calibration (Brier)</b> : une proba 0,8 doit se réaliser ~80 % du temps. <b>Conformal</b> : garantit un taux de couverture. <b>Meta-labeling</b> : un 2ᵉ modèle filtre les faux positifs ; le <b>sizing</b> module la taille selon la confiance.</p>
        </G>
        <G term="Fondamentaux : DCF, Piotroski, Altman Z">
            <Clair term={"Fondamentaux : DCF, Piotroski, Altman Z"} />
          <p><b>DCF</b> : valeur intrinsèque par actualisation des flux → marge de sécurité (intrinsèque/prix − 1).</p>
          <p><b>Piotroski (0-9)</b> : solidité financière (rentabilité, levier, marges). <b>Altman Z</b> : risque de faillite (Z&gt;2,99 sûr, &lt;1,81 détresse).</p>
          <p><b>Note combinée</b> = 60 % fondamental + 40 % technique.</p>
        </G>
        <G term="Playbook VIX">
            <Clair term={"Playbook VIX"} />
          <p>Le VIX mesure la peur du marché. <b>&lt;20</b> calme (exposition pleine) · <b>20-30</b> tendu (réduite) · <b>&gt;30</b> panique (défensif). L'exposition du portefeuille est modulée automatiquement.</p>
        </G>
      </div>
    </main>
  );
}
