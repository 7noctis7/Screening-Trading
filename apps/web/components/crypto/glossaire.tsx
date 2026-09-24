"use client";
// Les définitions que le cockpit met sous l'infobulle. FACTUELLES, jamais un chiffre :
// un glossaire explique un mot, il n'annonce pas un résultat.
import { InfoTip } from "@/components/InfoTip";

// Glossaire pédagogique (définitions factuelles, pas de chiffre inventé).
export const GLOSSARY: Record<string, string> = {
  "Capitalisation totale":
    "Ce que vaut le marché crypto tout entier : pour chaque crypto, son prix multiplié par le nombre d'unités en circulation, le tout additionné.",
  "Variation cap 24 h":
    "De combien cette valeur totale a bougé en 24 heures. Positif = le marché monte dans son ensemble.",
  "Dominance BTC":
    "La part du Bitcoin dans le total. Quand elle monte, les investisseurs se replient sur la crypto la plus établie ; quand elle baisse, ils prennent plus de risques ailleurs.",
  "Dominance ETH":
    "La part d'Ethereum dans le total. C'est le réseau de référence pour les applications décentralisées.",
  "Fear & Greed":
    "Un indice d'humeur de 0 à 100 (alternative.me). 0 = peur panique, souvent près d'un creux ; 100 = euphorie, souvent près d'un sommet. Il se lit à l'envers de ce qu'on croit.",
  "TVL DeFi totale":
    "L'argent déposé dans les services financiers décentralisés. C'est la mesure de leur usage réel, pas de leur promesse.",
  breadth:
    "Combien de cryptos montent, comparé à combien descendent. Une hausse portée par beaucoup d'actifs est plus solide qu'une hausse portée par deux ou trois.",
  peg:
    "Une crypto dite « stable » vaut en principe toujours 1,00 $. Cet écart mesure sa dérive : s'il dure, c'est un signe de tension ou de perte de confiance.",
};

export function Label({ text }: { text: string }) {
  const def = GLOSSARY[text];
  return (
    <span className="inline-flex items-center gap-1">
      {text}
      {def && <InfoTip label={text}>{def}</InfoTip>}
    </span>
  );
}
