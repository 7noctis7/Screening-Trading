"""Quels enregistrements du journal décrivent un trade PRIS PAR LE ROBOT ?

POURQUOI CE MODULE EXISTE. `/api/journal` répondait à cette question avec
`all(legacy=False)`. Or `legacy` répond à une AUTRE question — « ce trade porte-t-il
les features de décision ? », celle de la calibration ML. Les deux axes se sont
confondus, et le panneau a affiché **+139,75 $ sur 62 trades** là où le robot avait
fait **−23,15 $ sur 112** (mesuré le 17/09, après `make reparer-journal`). Le premier
chiffre n'était pas faux : il décrivait un sous-ensemble, et ce sous-ensemble était
favorable parce que les pertes non appariées en étaient absentes.

LES ORIGINES, lues sur le PRÉFIXE DE L'IDENTIFIANT :

  ``P-``    `live_journal` : ouverture décidée par le robot, features capturées à la
            décision. `legacy=0`.
  ``C-``    `completer_ouvertures` : ouverture RECONSTITUÉE depuis un fill réel du
            courtier. Le robot a bien passé l'ordre — c'est la journalisation qui a
            manqué, pas la décision. Sans features, donc `legacy=1`, et pourtant
            pleinement un trade du robot.
  ``R-``    `reconstruire_journal` : lot REJOUÉ depuis l'historique des ordres exécutés
            du courtier. Même statut épistémique que ``C-``, et même raisonnement — le
            robot a bien passé l'ordre, c'est la journalisation qui a manqué. Sa
            provenance est même la PLUS SÛRE des quatre : `P-` est ce que le robot dit
            avoir fait, `R-` est ce que le courtier a exécuté. Sans features, donc
            `legacy=1`, et pleinement un trade du robot.

            L'HYPOTHÈSE EST ÉCRITE PLUTÔT QUE TUE : tout fill de ce compte vient du
            robot. C'est vrai d'un compte paper qu'aucune main ne touche ; le jour où
            un ordre serait passé à la main, il serait compté ici comme un trade du
            robot, et rien ne le distinguerait. Le préfixe dit d'où vient l'ÉCRITURE,
            pas qui a décidé — et sur ce compte les deux coïncident.

  ``LEG-``  import historique. **Aucun script du dépôt n'écrit ce préfixe** (constaté
            par `diag_journal_compte._dump_symbole`) ; l'import qui l'a produit n'est
            plus dans l'arbre, et deux symboles y portent jusqu'à 1,9 fois leur achat.
            Provenance inconnue : ce ne sont pas des trades du robot.

Une vente partielle suffixe l'identifiant du lot (`-Xn` dans `live_roundtrip`, `-Rn`
dans `reconcilier_journal`). La classification lit donc le DÉBUT de l'identifiant,
jamais sa totalité.

UN PRÉFIXE INCONNU N'EST NI INCLUS NI IGNORÉ. Il est compté à part et nommé. Un filtre
qui écarte en silence ce qu'il ne reconnaît pas fabrique le seul mode de défaillance
qu'on ne sait pas mesurer — et ce dépôt en a déjà payé plusieurs.
"""

from __future__ import annotations

ROBOT = "robot"
IMPORT = "import"
INCONNU = "inconnu"

# Ordre sans importance : les préfixes ne sont pas préfixes les uns des autres.
PREFIXES: dict[str, str] = {"P-": ROBOT, "C-": ROBOT, "R-": ROBOT,
                            "LEG-": IMPORT}

LIBELLES = {
    ROBOT: "trades pris par le robot",
    IMPORT: "import historique (provenance inconnue)",
    INCONNU: "identifiant non reconnu",
}


def origine(trade_id: object) -> str:
    """`ROBOT`, `IMPORT` ou `INCONNU` — d'après le préfixe de l'identifiant."""
    tid = str(trade_id or "")
    for prefixe, quoi in PREFIXES.items():
        if tid.startswith(prefixe):
            return quoi
    return INCONNU


def pris_par_le_robot(trade_id: object) -> bool:
    """Vrai pour une ouverture décidée (`P-`), reconstituée d'un fill réel (`C-`) ou
    rejouée depuis l'historique des ordres du courtier (`R-`)."""
    return origine(trade_id) == ROBOT


def _bilan(rows: list[dict]) -> dict:
    fermes = [r for r in rows if r.get("exit_ts")]
    return {
        "n": len(rows),
        "n_fermes": len(fermes),
        "pnl_realise": round(sum(float(r.get("pnl_net") or 0.0) for r in fermes), 2),
    }


def ventiler(rows: list[dict]) -> dict:
    """Combien de lots et de réalisé par origine, LES INCONNUS COMPRIS.

    `rows` porte des dictionnaires `{"id", "exit_ts", "pnl_net"}` au minimum. Le
    résultat nomme ce qui n'a pas été reconnu plutôt que de le taire : `inconnus`
    liste les identifiants concernés (tronqués), pour qu'un nouveau préfixe se voie
    le jour où un script en introduit un.
    """
    par_origine: dict[str, list[dict]] = {ROBOT: [], IMPORT: [], INCONNU: []}
    for r in rows or []:
        par_origine[origine(r.get("id"))].append(r)
    out = {quoi: _bilan(lignes) for quoi, lignes in par_origine.items()}
    out["inconnus"] = sorted({str(r.get("id"))[:24] for r in par_origine[INCONNU]})[:10]
    return out
