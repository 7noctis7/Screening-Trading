"""Le moteur NLP — asynchrone, borné, et incapable de faire tomber quoi que ce soit.

CE QU'IL GARANTIT, ET C'EST TOUT CE QUI COMPTE. `classer()` rend TOUJOURS un `SignalNLP`.
Fournisseur éteint, modèle absent, JSON invalide, délai dépassé, disjoncteur ouvert,
exception inattendue : la réponse est un repli NEUTRE à confiance nulle, marqué `repli=True`.
Aucune exception ne remonte. Une classification de dépêche n'a pas à pouvoir interrompre
les prix, la stratégie, le risque ou l'exécution — qui passent tous avant elle.

LES QUATRE BORNES
  · TEMPS         `asyncio.wait_for` — un titre qui n'a pas répondu en douze secondes ne
                  vaut plus qu'on l'attende ; la séance, elle, n'attend pas.
  · CONCURRENCE   un sémaphore. Deux requêtes simultanées sur un 7B quantifié saturent déjà
                  la mémoire unifiée d'un Mac 16 Go ; au-delà, macOS échange sur disque et
                  la latence explose — ce qui ressemble exactement à une panne de modèle.
  · MÉMOIRE       cache LRU borné. Sans borne, classer deux cents titres par jour pendant
                  un mois garde tout en RAM pour un gain de cache proche de zéro.
  · ÉCHECS        le disjoncteur. Sans lui, fournisseur éteint = deux cents fois douze
                  secondes d'attente, soit quarante minutes à ne rien faire.

LE CACHE EST VOLONTAIREMENT NAÏF : même texte, même titre, même modèle, même version
d'invite ⇒ même réponse. Changer l'invite invalide donc le cache, ce qui est l'effet voulu —
comparer deux versions d'invite sur des réponses mises en cache par l'ancienne ne
comparerait rien.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import OrderedDict, deque

from packages.nlp import invites
from packages.nlp.config import ConfigNLP
from packages.nlp.disjoncteur import Disjoncteur
from packages.nlp.pilotes import choisir
from packages.nlp.schemas import SignalNLP, repli, valider

LATENCES_GARDEES = 200        # de quoi calculer une médiane sans grossir sans fin


class MoteurNLP:
    """Un moteur par processus. Sans état persistant : ce qu'il mesure décrit MAINTENANT."""

    def __init__(self, cfg: ConfigNLP | None = None, pilote=None,
                 disjoncteur: Disjoncteur | None = None):
        self.cfg = cfg or ConfigNLP.depuis_env()
        self._pilote = pilote                     # injecté en test ; sinon résolu au 1er appel
        self._pilote_resolu = pilote is not None
        self.disjoncteur = disjoncteur or Disjoncteur()
        self._cache: OrderedDict[str, SignalNLP] = OrderedDict()
        self._semaphore = asyncio.Semaphore(self.cfg.concurrence)
        self._latences: deque[float] = deque(maxlen=LATENCES_GARDEES)
        self._compteurs = {"appels": 0, "cache": 0, "replis": 0, "timeouts": 0,
                           "disjoncteur": 0, "invalides": 0, "succes": 0, "neutres": 0}

    # ── pilote ─────────────────────────────────────────────────────────────────────────
    def pilote(self):
        """Résolu UNE fois, paresseusement : sonder les fournisseurs à l'import ferait
        payer trois secondes de réseau à tout script qui importe ce paquet."""
        if not self._pilote_resolu:
            self._pilote = choisir(self.cfg.modele, self.cfg.pilote, self.cfg.base)
            self._pilote_resolu = True
        return self._pilote

    # ── cache ──────────────────────────────────────────────────────────────────────────
    def _cle(self, ticker: str, texte: str, version: str) -> str:
        empreinte = hashlib.sha256(texte.encode("utf-8")).hexdigest()[:24]
        return f"{ticker.upper()}|{empreinte}|{self.cfg.modele}|{version}"

    def _lire_cache(self, cle: str) -> SignalNLP | None:
        s = self._cache.get(cle)
        if s is not None:
            self._cache.move_to_end(cle)
            self._compteurs["cache"] += 1
        return s

    def _ecrire_cache(self, cle: str, signal: SignalNLP) -> None:
        # Un repli n'est PAS mis en cache : il décrit une panne passagère, pas une
        # classification. Le mettre en cache figerait la panne pour toute la session.
        if signal.repli or self.cfg.cache_max <= 0:
            return
        self._cache[cle] = signal
        while len(self._cache) > self.cfg.cache_max:
            self._cache.popitem(last=False)

    # ── classification ─────────────────────────────────────────────────────────────────
    async def classer(self, ticker: str, texte: str,
                      version_invite: str = invites.VERSION_COURANTE) -> SignalNLP:
        """Rend TOUJOURS un signal. Ne lève jamais."""
        self._compteurs["appels"] += 1
        cle = self._cle(ticker, texte, version_invite)
        if (cache := self._lire_cache(cle)) is not None:
            return cache
        signal = await self._classer_sans_cache(ticker, texte, version_invite)
        self._ecrire_cache(cle, signal)
        if signal.neutre:
            self._compteurs["neutres"] += 1
        return signal

    async def _classer_sans_cache(self, ticker: str, texte: str,
                                  version: str) -> SignalNLP:
        p = self.pilote()
        if p is None:
            return self._repli(ticker, "AUCUN_FOURNISSEUR", version)
        if not self.disjoncteur.autorise():
            self._compteurs["disjoncteur"] += 1
            return self._repli(ticker, "DISJONCTEUR_OUVERT", version)

        debut = time.perf_counter()
        try:
            async with self._semaphore:
                # DEUX DÉLAIS, UN SEUL PLAFOND. Le pilote reçoit le même délai pour sa
                # socket ; `wait_for` est l'autorité. Une première version donnait à
                # `wait_for` deux secondes de marge « par prudence » — ce qui rendait le
                # délai annoncé mensonger : configurer 12 s en attendait 14.
                #
                # `to_thread` ne s'annule pas : quand `wait_for` expire, le fil du pilote
                # continue jusqu'à ce que SA socket lâche. C'est précisément pourquoi il
                # doit avoir un délai lui aussi — sans lui, un fil orphelin par appel.
                brut = await asyncio.wait_for(
                    asyncio.to_thread(p.classer, invites.systeme(version),
                                      invites.utilisateur(ticker, texte, version),
                                      self.cfg.timeout_s),
                    timeout=self.cfg.timeout_s)
        except TimeoutError:
            self._compteurs["timeouts"] += 1
            self.disjoncteur.echec()
            return self._repli(ticker, "TIMEOUT", version)
        except asyncio.CancelledError:
            raise                      # une annulation est une décision de l'appelant
        except Exception:              # noqa: BLE001 — aucune panne ne remonte
            self.disjoncteur.echec()
            return self._repli(ticker, "ERREUR_FOURNISSEUR", version)

        ms = (time.perf_counter() - debut) * 1000.0
        self._latences.append(ms)
        if brut is None:
            self._compteurs["invalides"] += 1
            self.disjoncteur.echec()
            return self._repli(ticker, "REPONSE_ILLISIBLE", version)

        self.disjoncteur.succes()
        signal = valider(brut, ticker, modele=self.cfg.modele, version_invite=version)
        if signal.repli:
            self._compteurs["replis"] += 1
            return signal
        self._compteurs["succes"] += 1
        return SignalNLP(**{**signal.en_dict(), "latence_ms": round(ms, 1),
                            "incidents": signal.incidents})

    def _repli(self, ticker: str, motif: str, version: str) -> SignalNLP:
        self._compteurs["replis"] += 1
        return repli(ticker, motif, modele=self.cfg.modele, version_invite=version)

    async def classer_lot(self, items: list[tuple[str, str]],
                          version_invite: str = invites.VERSION_COURANTE) -> list[SignalNLP]:
        """Un lot, borné par le sémaphore. `gather` ne lève pas : chaque élément rend
        son propre signal, et une panne sur un titre n'annule pas les autres."""
        taches = [self.classer(t, x, version_invite) for t, x in items]
        return list(await asyncio.gather(*taches))

    # ── observabilité ──────────────────────────────────────────────────────────────────
    def metriques(self) -> dict:
        """Ce que `/api/ai/metrics` doit montrer. Un taux de neutres qui s'envole est le
        premier symptôme visible d'un problème de source, d'invite ou de modèle — sans
        qu'on puisse conclure lequel."""
        n = max(1, self._compteurs["appels"])
        lat = sorted(self._latences)
        return {
            **self._compteurs,
            "taux_repli": round(self._compteurs["replis"] / n, 4),
            "taux_neutre": round(self._compteurs["neutres"] / n, 4),
            "taux_cache": round(self._compteurs["cache"] / n, 4),
            "latence_mediane_ms": round(lat[len(lat) // 2], 1) if lat else None,
            "latence_p90_ms": round(lat[int(len(lat) * 0.9)], 1) if lat else None,
            "cache_taille": len(self._cache),
            "cache_max": self.cfg.cache_max,
            "disjoncteur": self.disjoncteur.etat_public(),
            "config": self.cfg.resume(),
        }
