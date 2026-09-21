"""Un même lot OUVERT enregistré deux fois — et aucun outil ne le retirait.

CE QUI S'EST PASSÉ (17-18/09). `completer_ouvertures` a reconstitué un achat que le
robot avait DÉJÀ journalisé le soir même : `diag-journal` a vu « QQQ ×2, 3,586126 @
716,86 le 2026-09-17 ». La cause est corrigée en amont (`deja_journalises`, 17/09) —
mais la ligne écrite ce jour-là est toujours là, et la chaîne de réparation n'avait
RIEN pour la retirer : `annuler_doublons_correction` ne traite que les doublons de
FERMETURE (même date et prix de SORTIE). Un défaut détecté sans remède est un défaut
qui reste.

POURQUOI IL FAUT LE RETIRER. Un lot ouvert en double gonfle la quantité au journal et
fournit un lot de PLUS à apparier en FIFO. La prochaine vente réelle fermera les deux,
et le second produira du « réalisé » sans contrepartie chez le courtier — exactement
l'invention que cette chaîne existe pour combattre.

LEQUEL ON GARDE, ET CE N'EST PAS ARBITRAIRE. L'ordre de préférence suit la QUALITÉ DE
LA PROVENANCE, pas la date d'écriture :

  1. ``P-``   ouverture décidée par le robot, features de décision capturées ;
  2. ``C-``   même ordre, reconstitué après coup depuis le fill réel du courtier ;
  3. ``LEG-`` import historique, provenance illisible ;
  4. le reste, préfixe non reconnu.

À rang égal, on garde celui qui PORTE des features (il sert la calibration ML), puis le
plus petit identifiant — pour que deux exécutions donnent le même résultat.

CE QU'ON NE TOUCHE PAS. Les lots FERMÉS. Leur retrait effacerait un réalisé déjà
comptabilisé : c'est une autre décision, qui se prend avec les fills du courtier sous
les yeux (`annuler_doublons_correction`), pas ici.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.execution.perimetre_journal import IMPORT, INCONNU, ROBOT, origine

# Rang de confiance. Plus petit = gardé en priorité.
_RANG_PREFIXE = {"P-": 0, "C-": 1, "LEG-": 2}
_RANG_ORIGINE = {ROBOT: 0, IMPORT: 2, INCONNU: 3}


def cle(t) -> tuple:
    """Symbole, quantité, prix d'entrée et JOUR — la clé de `diag-journal`.

    Deux achats réels du même titre, au même prix au millionième et pour la même
    quantité au millionième, le même jour, sont possibles mais rares. On ne les
    supprime donc jamais en silence : le plan les NOMME, et la simulation est le
    défaut.
    """
    return (str(t.instrument), round(float(t.qty or 0.0), 6),
            round(float(t.entry_price or 0.0), 6), str(t.entry_ts)[:10])


def _rang(t) -> tuple:
    tid = str(t.id or "")
    prefixe = next((r for p, r in _RANG_PREFIXE.items() if tid.startswith(p)),
                   _RANG_ORIGINE.get(origine(tid), 3))
    return (prefixe, 0 if (t.features_snapshot or {}) else 1, tid)


@dataclass(frozen=True)
class Doublon:
    """Un groupe : ce qu'on garde, ce qu'on retire, et de quoi le rejuger."""

    cle: tuple
    garde: str                    # identifiant conservé
    retires: tuple[str, ...]      # identifiants retirés
    qty: float
    prix: float
    jour: str

    def en_dict(self) -> dict:
        return {"symbole": self.cle[0], "qty": self.qty, "prix": self.prix,
                "jour": self.jour, "garde": self.garde,
                "retires": list(self.retires)}


def plan(lots) -> list[Doublon]:
    """Les groupes de lots OUVERTS identiques. Aucune écriture — c'est un plan.

    `lots` peut contenir des lots fermés : ils sont écartés ici, pas chez l'appelant,
    pour qu'aucun appelant ne puisse l'oublier.
    """
    groupes: dict[tuple, list] = {}
    for t in lots or []:
        if getattr(t, "exit_ts", None) is not None:
            continue
        groupes.setdefault(cle(t), []).append(t)
    out = []
    for k, membres in sorted(groupes.items()):
        if len(membres) < 2:
            continue
        ordonnes = sorted(membres, key=_rang)
        out.append(Doublon(cle=k, garde=str(ordonnes[0].id),
                           retires=tuple(str(t.id) for t in ordonnes[1:]),
                           qty=k[1], prix=k[2], jour=k[3]))
    return out


def identifiants_retires(doublons: list[Doublon]) -> list[str]:
    return [i for d in doublons for i in d.retires]
