"""Ce que les garde-fous du chemin d'exécution ont RÉELLEMENT fait.

POURQUOI CE FICHIER EXISTE (21/09). Cinq garde-fous protègent le seul chemin qui envoie
des ordres — kill-switch TradingView, kill-switch drawdown, disjoncteur journalier, garde
journalière, portail de risque. Tous les cinq DÉCIDENT et IMPRIMENT ; aucun ne COMPTE.
La trace vit dans le `stdout` d'un run, donc dans `/tmp/quant_live.log`, sur une machine,
jusqu'au prochain nettoyage. Impossible de répondre à « combien d'ordres le portail a-t-il
réduits ce mois-ci, de combien, et pour quelle règle ? » autrement qu'en greppant un
journal à la main, machine par machine.

CE QUE L'ABSENCE DE COMPTEUR REND IMPOSSIBLE, et c'est le vrai coût. `coupe_circuit`
écrit dans son propre en-tête qu'on armera le disjoncteur « une fois qu'on a vu sur
plusieurs semaines les jours où il AURAIT coupé ». Rien n'enregistre ces jours. La
condition d'armement est donc INOBSERVABLE : elle ne peut pas être remplie, jamais.

CE MODULE N'EST QU'UN TÉMOIN. Il reçoit des verdicts DÉJÀ rendus et les additionne.
Aucune de ses méthodes ne peut refuser, réduire, retarder ni modifier un ordre — un
observateur capable d'agir ne serait plus un observateur. Il ne touche pas non plus au
disque : la persistance appartient à `garde_fous_store`, pour que `risk/order_gate` reste
une fonction PURE et qu'écrire une statistique ne puisse jamais faire échouer un ordre.

ABSENT ≠ ZÉRO, et c'est toute la lecture :
  · jamais observé            → désarmé, ou le run n'est jamais allé jusque-là ;
  · observé, zéro déclenchement → ACTIVE à 0 : il tourne et ne sert à rien — un seuil
    hors d'atteinte ressemble exactement à un marché calme ;
  · observé sans conclusion   → UNCALIBRATED (historique trop court, relevé indisponible) ;
  · en panne                  → ERROR, jamais un silence.
Un zéro et une absence qui se ressemblent produisent précisément la confusion qu'un
garde-fou existe pour empêcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field

ACTIVE = "ACTIVE"
DESARME = "DISABLED"
UNCALIBRATED = "UNCALIBRATED"
ERREUR = "ERROR"

PORTAIL = "portail_de_risque"
KILL_TV = "kill_switch_tradingview"
KILL_DD = "kill_switch_drawdown"
DISJONCTEUR = "disjoncteur_journalier"
GARDE_JOUR = "garde_journaliere"
SEANCE = "garde_de_seance"

# L'ordre d'affichage suit le chemin d'exécution, pas l'alphabet : on lit le rapport
# comme on lit un run.
ORDRE: tuple[str, ...] = (KILL_TV, KILL_DD, DISJONCTEUR, GARDE_JOUR, SEANCE, PORTAIL)


@dataclass
class Garde:
    """Compte-rendu d'UN garde-fou sur UN run.

    `effet_usd` vaut `None` tant que l'effet n'est pas mesurable EN DOLLARS (un
    kill-switch coupe une exposition, il ne retient pas un montant). `0.0` veut dire
    « mesuré, et nul » — les deux ne doivent jamais se confondre.
    """

    nom: str
    etat: str = UNCALIBRATED
    observations: int = 0
    declenchements: int = 0
    aurait_declenche: int = 0          # mode observation : il aurait coupé, il n'a pas agi
    effet_usd: float | None = None
    motifs: dict[str, int] = field(default_factory=dict)

    def rapport(self) -> dict:
        n, d = self.observations, self.declenchements
        return {
            "etat": self.etat,
            "observations": n,
            "declenchements": d,
            "taux": round(d / n, 4) if n else None,
            "aurait_declenche": self.aurait_declenche,
            "effet_usd": None if self.effet_usd is None else round(self.effet_usd, 2),
            "effet_moyen": (round(self.effet_usd / d, 2)
                            if d and self.effet_usd is not None else None),
            "motifs": dict(sorted(self.motifs.items())),
        }


class Collecteur:
    """Additionne les verdicts d'un run. Total par construction : aucune méthode ne lève.

    Il n'expose AUCUN moyen d'influer sur une décision — pas de retour exploitable, pas
    d'exception. C'est ce qui permet de l'appeler depuis le chemin d'ordre sans lui
    donner le pouvoir de le bloquer.
    """

    def __init__(self) -> None:
        self.gardes: dict[str, Garde] = {}

    def observer(self, nom: str, *, etat: str = ACTIVE, declenche: bool = False,
                 aurait: bool = False, effet_usd: float | None = None,
                 motif: str | None = None) -> None:
        g = self.gardes.get(nom) or Garde(nom)
        self.gardes[nom] = g
        g.observations += 1
        # ERROR est COLLANT. Un garde-fou qui tombe en panne une fois dans le run doit
        # le dire même si les observations suivantes se passent bien : c'est la panne
        # qu'on veut voir, pas la moyenne.
        if etat == ERREUR or g.etat != ERREUR:
            g.etat = etat
        if declenche:
            g.declenchements += 1
        if aurait:
            g.aurait_declenche += 1
        if effet_usd is not None:
            g.effet_usd = (g.effet_usd or 0.0) + float(effet_usd)
        if motif:
            g.motifs[motif] = g.motifs.get(motif, 0) + 1

    def portail(self, verdict: object, demande: float) -> None:
        """Un ordre passé au portail de risque.

        L'EFFET EST LE MONTANT QUI N'EST PAS PARTI, et il se mesure dans les deux cas :
        un refus retient tout le montant demandé, une réduction retient la différence.
        Compter le montant DEMANDÉ sur une réduction gonflerait l'effet d'un facteur
        dix ; compter zéro sur un refus effacerait le garde-fou le jour où il sert le
        plus.
        """
        demande = max(0.0, float(demande or 0.0))
        autorise = bool(getattr(verdict, "autorise", False))
        regle = str(getattr(verdict, "regle", "") or "inconnue")
        if not autorise:
            self.observer(PORTAIL, declenche=True, effet_usd=demande, motif=regle)
        elif bool(getattr(verdict, "reduit", False)):
            retenu = float(getattr(verdict, "montant", demande) or 0.0)
            self.observer(PORTAIL, declenche=True,
                          effet_usd=max(0.0, demande - retenu), motif=regle)
        else:
            self.observer(PORTAIL, effet_usd=0.0)

    def rapport(self) -> dict:
        return {nom: g.rapport() for nom, g in self.gardes.items()}


def noter(obs: object | None, nom: str, **kw: object) -> None:
    """Appel d'observation à l'épreuve de tout — À UTILISER DEPUIS LE CHEMIN D'ORDRE.

    Un observateur cassé ne doit ni bloquer un ordre ni faire échouer un garde-fou. Mais
    il ne doit pas DISPARAÎTRE en silence non plus : l'incident s'imprime. Un compteur
    absent se lira « jamais observé », et la ligne imprimée dira pourquoi.
    """
    if obs is None:
        return
    try:
        obs.observer(nom, **kw)  # type: ignore[attr-defined]
    except Exception as e:  # noqa: BLE001 — observer ne peut pas coûter un ordre
        print(f"⚠️  observabilité du garde-fou {nom} indisponible ({str(e)[:60]}) — "
              "la décision, elle, a bien été appliquée.")


def noter_portail(obs: object | None, verdict: object, demande: float) -> None:
    """Même protection que `noter`, pour l'ordre qui vient de traverser le portail."""
    if obs is None:
        return
    try:
        obs.portail(verdict, demande)  # type: ignore[attr-defined]
    except Exception as e:  # noqa: BLE001 — observer ne peut pas coûter un ordre
        print(f"⚠️  observabilité du {PORTAIL} indisponible ({str(e)[:60]}) — "
              "le verdict, lui, a bien été appliqué.")


def _fusionner(cumul: dict, g: dict) -> dict:
    cumul["observations"] += int(g.get("observations") or 0)
    cumul["declenchements"] += int(g.get("declenchements") or 0)
    cumul["aurait_declenche"] += int(g.get("aurait_declenche") or 0)
    if g.get("effet_usd") is not None:
        cumul["effet_usd"] = round((cumul["effet_usd"] or 0.0) + float(g["effet_usd"]), 2)
    for m, n in (g.get("motifs") or {}).items():
        cumul["motifs"][m] = cumul["motifs"].get(m, 0) + int(n)
    etat = str(g.get("etat") or UNCALIBRATED)
    cumul["etats"][etat] = cumul["etats"].get(etat, 0) + 1
    return cumul


def agreger(runs: list[dict], mode: str | None = "live") -> dict:
    """Cumule N runs. `mode=None` prend tout ; par défaut on ne compte QUE le réel.

    Un aperçu (`dry-run`) évalue le portail sans rien envoyer : additionner les deux
    répondrait à « qu'aurait fait le robot », pas à « qu'a-t-il fait ». Les deux
    questions sont légitimes — elles ne se mélangent pas dans la même colonne.
    """
    retenus = [r for r in runs if mode is None or (r.get("mode") or "") == mode]
    gardes: dict[str, dict] = {}
    for r in retenus:
        for nom, g in (r.get("gardes") or {}).items():
            gardes.setdefault(nom, {"observations": 0, "declenchements": 0,
                                    "aurait_declenche": 0, "effet_usd": None,
                                    "motifs": {}, "etats": {}})
            _fusionner(gardes[nom], g)
    for g in gardes.values():
        n, d = g["observations"], g["declenchements"]
        g["taux"] = round(d / n, 4) if n else None
        g["effet_moyen"] = (round(g["effet_usd"] / d, 2)
                            if d and g["effet_usd"] is not None else None)
    horos = sorted(str(r.get("horodatage") or "") for r in retenus)
    return {"n_runs": len(retenus), "n_runs_total": len(runs), "mode": mode,
            "depuis": horos[0] if horos else None, "jusqu_a": horos[-1] if horos else None,
            "gardes": gardes}


def _grouper(noms: list[str], phrase: str) -> str:
    """Une phrase, les garde-fous qu'elle concerne. Pas six copies de la même ligne.

    CONSTATÉ SUR LE PREMIER RUN RÉEL (21/09). Au premier passage, les SIX garde-fous
    sont trivialement à zéro déclenchement : la section « ce qu'il faut regarder »
    affichait six fois la même phrase, à un nom près. Une liste dont toutes les lignes
    se ressemblent n'est plus lue — et c'est la section qui doit attirer l'œil.

    Ce n'est pas un seuil : on ne cache rien et on ne décide de rien. On DÉDUPLIQUE.
    """
    if len(noms) == 1:
        return f"{noms[0]} : {phrase}"
    return f"{len(noms)} garde-fous ({', '.join(noms)}) : {phrase}"


def verdicts(agrege: dict) -> list[str]:
    """Ce qu'un opérateur doit REGARDER — sans seuil inventé.

    Aucune alerte ne repose sur un nombre choisi à la main : toutes sont STRUCTURELLES
    (jamais observé, jamais déclenché, panne, déclenché sans effet). Fixer ici un
    « effet moyen négligeable en dessous de X $ » reviendrait à calibrer sur rien —
    l'effet moyen est donc AFFICHÉ, et c'est l'opérateur qui le juge.

    Les constats IDENTIQUES sont regroupés en une ligne ; ceux qui portent un chiffre
    propre à un garde-fou (panne, jours où il aurait coupé) restent séparés, parce que
    les fondre ferait perdre ce chiffre.
    """
    g = agrege.get("gardes") or {}
    if not agrege.get("n_runs"):
        return ["UNCALIBRATED — aucun run enregistré pour ce mode. "
                "Les compteurs se remplissent au premier passage réel du robot."]
    jamais: list[str] = []
    muets: list[str] = []
    individuels: list[str] = []
    for nom in ORDRE:
        d = g.get(nom)
        if not d:
            jamais.append(nom)
            continue
        if d["etats"].get(ERREUR):
            individuels.append(f"{nom} : ERROR sur {d['etats'][ERREUR]} run(s) — "
                               "garde-fou en panne.")
        if d["etats"].get(DESARME) and not d["etats"].get(ACTIVE):
            individuels.append(f"{nom} : DÉSARMÉ sur {d['observations']} observation(s) — "
                               "il a été traversé sans jamais pouvoir agir.")
        # « Jamais déclenché » compte AUSSI les déclenchements retenus par le mode
        # observation : un disjoncteur qui aurait coupé deux fois a atteint son seuil.
        # L'alerte « seuil inatteignable » serait alors un contresens. Et on ne
        # l'annonce que pour un garde-fou VRAIMENT actif : dire « ACTIVE » d'un
        # garde-fou désarmé serait le contresens inverse.
        if (d["etats"].get(ACTIVE) and d["observations"]
                and not (d["declenchements"] + d["aurait_declenche"])):
            muets.append(nom)
        if d["declenchements"] and d["effet_usd"] == 0.0:
            individuels.append(f"{nom} : {d['declenchements']} déclenchement(s) pour un "
                               "effet mesuré NUL — il se déclenche sans rien retenir.")
        if d["aurait_declenche"]:
            individuels.append(f"{nom} : aurait coupé {d['aurait_declenche']} fois "
                               "(observation) — matière à décider de son armement.")
    out: list[str] = []
    if jamais:
        out.append(_grouper(jamais, "JAMAIS OBSERVÉ — désarmé, ou le run ne va jamais "
                                    "jusque-là."))
    if muets:
        # ON CONSTATE, ON N'ACCUSE PAS. « Vérifier que son seuil est atteignable » après
        # deux passages faisait d'un échantillon court un soupçon de défaut : un
        # disjoncteur à 3 037 $ qui ne mord pas sur une journée à −336 $ fait exactement
        # son travail. La phrase dit QUAND s'inquiéter, sans poser de seuil — le nombre
        # de runs est affiché, l'opérateur tranche.
        out.append(_grouper(muets, f"ACTIVE, ZÉRO déclenchement sur "
                                   f"{agrege['n_runs']} run(s) — attendu sur un "
                                   "échantillon court ; sur plusieurs semaines, c'est un "
                                   "seuil à revoir. Le détail par garde-fou est au "
                                   "tableau ci-dessus."))
    return out + individuels
