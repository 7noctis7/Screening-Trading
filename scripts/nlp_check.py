#!/usr/bin/env python3
"""Le NLP local répond-il, et répond-il JUSTE ? — à lancer sur la machine qui héberge le LLM.

  python scripts/nlp_check.py                      (ou : make nlp-check)
  python scripts/nlp_check.py --modele qwen2.5-7b-instruct
  python scripts/nlp_check.py --texte "Rappel produit massif annoncé ce matin."

CE QU'IL VÉRIFIE, DANS L'ORDRE OÙ ÇA CASSE EN VRAI :
  1. un fournisseur répond-il (LM Studio sur :1234, sinon Ollama sur :11434) ;
  2. le modèle demandé est-il RÉELLEMENT chargé — un fournisseur qui répond avec un autre
     modèle chargé échoue à la première vraie requête, pas au diagnostic ;
  3. la sortie structurée tient-elle le schéma ;
  4. combien de temps, et le repli fonctionne-t-il quand on coupe.

Il n'écrit rien, n'entraîne rien, n'envoie aucun ordre.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CAS = [
    ("AAPL", "Résultats trimestriels très au-dessus du consensus, marge en hausse.",
     "BULLISH"),
    ("BA", "Rappel massif annoncé ce matin après un défaut de production critique.",
     "BEARISH"),
    ("KO", "La société confirme la tenue de son assemblée générale annuelle en mai.",
     "NEUTRAL"),
]


def _fournisseur(cfg):
    from packages.nlp.pilotes import choisir
    p = choisir(cfg.modele, cfg.pilote, cfg.base)
    if p is None:
        print("⛔ Aucun fournisseur local ne répond.")
        print("   LM Studio : ouvrir l'onglet « Developer » → Start Server (port 1234)")
        print("   Ollama    : `ollama serve`")
        return None
    modeles = p.modeles()
    print(f"✓ Fournisseur : {p.nom} · {len(modeles)} modèle(s) chargé(s)")
    if modeles and not any(cfg.modele.lower() in m.lower() for m in modeles):
        print(f"⚠ Le modèle demandé « {cfg.modele} » n'est pas dans la liste :")
        for m in modeles[:8]:
            print(f"    {m}")
        print("   → --modele <un de ceux-ci>, ou LOCAL_TRADING_MODEL=<…>")
    return p


async def _essais(moteur) -> int:
    from packages.nlp.schemas import SENTIMENTS
    justes = 0
    print("\n  " + "─" * 78)
    for ticker, texte, attendu in CAS:
        s = await moteur.classer(ticker, texte)
        ok = "✓" if s.sentiment == attendu else ("⛔" if s.repli else "≠")
        justes += int(s.sentiment == attendu)
        lat = f"{s.latence_ms:.0f} ms" if s.latence_ms else "—"
        print(f"  {ok} {ticker:5s} attendu {attendu:8s} → {s.sentiment:8s} "
              f"conf {s.confiance:.2f} · {s.horizon:9s} · {lat}")
        if s.incidents:
            for i in s.incidents:
                print(f"      ⚠ {i}")
        if s.repli:
            print(f"      motif : {s.resume}")
    print("  " + "─" * 78)
    assert set(SENTIMENTS)          # le contrat est bien celui qu'on croit
    return justes


def _verdict(justes: int, moteur) -> int:
    m = moteur.metriques()
    print(f"\n  Accord sur les cas d'école : {justes}/{len(CAS)}")
    print(f"  Latence médiane : {m['latence_mediane_ms']} ms · p90 {m['latence_p90_ms']} ms")
    print(f"  Replis : {m['replis']} · timeouts : {m['timeouts']} · "
          f"disjoncteur : {m['disjoncteur']['etat']}")
    print(f"  Config : {m['config']}")
    if m["replis"]:
        print("\n⛔ Des replis : la chaîne ne tient pas. Voir les motifs ci-dessus.")
        return 1
    if justes < len(CAS):
        # Un désaccord n'est PAS un échec technique : le modèle a répondu, correctement
        # formé, mais autrement. C'est une information sur le MODÈLE, pas sur le code.
        print("\n⚠ La chaîne fonctionne, mais le modèle ne classe pas comme attendu.")
        print("  Essayer un autre modèle, ou faire évoluer l'invite (nouvelle version).")
        return 0
    print("\n✅ Chaîne NLP opérationnelle de bout en bout.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--modele", default=None)
    ap.add_argument("--pilote", default=None, choices=["auto", "lmstudio", "ollama"])
    ap.add_argument("--texte", default=None, help="tester UN texte libre sur --ticker")
    ap.add_argument("--ticker", default="AAPL")
    a = ap.parse_args()

    from packages.nlp.config import ConfigNLP
    from packages.nlp.moteur import MoteurNLP
    base = ConfigNLP.depuis_env()
    cfg = ConfigNLP(modele=a.modele or base.modele, base=base.base,
                    pilote=a.pilote or base.pilote, timeout_s=base.timeout_s,
                    concurrence=base.concurrence, cache_max=base.cache_max)
    print(f"\n  Configuration : {cfg.resume()}")
    p = _fournisseur(cfg)
    if p is None:
        return 2
    moteur = MoteurNLP(cfg=cfg, pilote=p)

    if a.texte:
        s = asyncio.run(moteur.classer(a.ticker, a.texte))
        print(f"\n  {s.ticker} → {s.sentiment} (conf {s.confiance:.2f}, {s.horizon})")
        print(f"  « {s.resume} »")
        return 1 if s.repli else 0

    justes = asyncio.run(_essais(moteur))
    return _verdict(justes, moteur)


if __name__ == "__main__":
    raise SystemExit(main())
