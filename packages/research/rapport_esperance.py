"""Rapport d'une page : les quatre questions, chacune avec son nombre et son intervalle.

1. Espérance nette d'un aller-retour, frais et impact compris.
2. Ce livre contre QQQ + cash au même drawdown (et à la même volatilité).
3. Nombre de paris indépendants, et IC hors échantillon du classement tradé.
4. Encours où cette espérance devient nulle.

Tout ce qui n'a pas été calculé s'écrit « non mesuré ». Le verdict est mécanique :
le signal n'est ÉTABLI que si (1) et (2) ont un intervalle entièrement positif ET si
l'écart (2) survit à la déflation (DSR ≥ 0,95) par le nombre d'essais du registre.
Sinon, le robot rationnel est le mélange QQQ + cash, et la seule PR légitime est celle
qui retire ce qui coûte.
"""

from __future__ import annotations

NM = "non mesuré"
SEUIL_DSR = 0.95


def _pct(x, d: int = 2) -> str:
    return NM if x is None else f"{x * 100:+.{d}f} %"


def _ic(iv) -> str:
    return NM if not iv else f"[{iv[0] * 100:+.2f} % ; {iv[1] * 100:+.2f} %]"


def _iv(iv, d: int = 3) -> str:
    return NM if not iv else f"[{iv[0]:+.{d}f} ; {iv[1]:+.{d}f}]"


def _dollars(x) -> str:
    return NM if x is None else f"{x:,.0f} $".replace(",", " ")


def verdict(q1: dict, q2: dict) -> dict:
    """Signal établi seulement si 1 et 2 sont positifs, distincts de zéro, déflatés."""
    ok1 = bool(q1.get("available") and q1["ic95"][0] > 0)
    ok2 = bool(q2.get("available") and q2["ic95"][0] > 0
               and (q2.get("dsr_ecart") or 0) >= SEUIL_DSR)
    etabli = ok1 and ok2
    texte = ("Signal établi : espérance et écart au mélange positifs, distincts de "
             "zéro "
             "après déflation." if etabli else
             "Signal NON établi. Le robot rationnel est le mélange QQQ + cash au même "
             "risque ; pas de PR de modèle — la PR légitime retire ce qui coûte.")
    return {"etabli": etabli, "q1_positive": ok1, "q2_positive_deflatee": ok2,
            "texte": texte}


def _ligne_q1(q1: dict, y: str) -> str:
    titre = f"1 · espérance / aller-retour ({y})"
    if not q1.get("available"):
        return f"| {titre} | {NM} | — | n = {q1.get('n', 0)} |"
    return (f"| {titre} | {_pct(q1['esperance_ponderee'], 3)} | {_ic(q1['ic95'])} | "
            f"n = {q1['n']}, gagnants {q1['taux_gain'] * 100:.0f} % |")


def _ligne_q2(q2: dict) -> str:
    base = {"drawdown": "drawdown", "volatilite": "volatilité"}.get(
        q2.get("base", "drawdown"), q2.get("base"))
    if not q2.get("available"):
        return f"| 2 · livre − QQQ+cash, même {base} | {NM} | — | — |"
    dsr = q2.get("dsr_ecart")
    dsr_txt = NM if dsr is None else f"{dsr:.2f}"
    return (f"| 2 · livre − QQQ+cash, même {base} (α = {q2['alpha_qqq']:.2f}) | "
            f"{_pct(q2['ecart_annualise'])} / an | {_ic(q2['ic95'])} | "
            f"DSR {dsr_txt} ({q2['n_essais']} essais) |")


def _lignes_q3(q3: dict, ic: dict) -> list[str]:
    if q3.get("available"):
        par_an = q3.get("paris_independants_par_an")
        an = NM if par_an is None else f"{par_an:.0f}"
        n = (f"{q3['n_eff_median']:.1f} effectifs pour {q3['n_lignes_median']:.0f} "
             f"lignes ; {an} / an")
        iv = f"p10–p90 {_iv(q3['n_eff_p10_p90'], 1)}"
    else:
        n, iv = NM, "—"
    out = [f"| 3 · paris indépendants | {n} | {iv} | — |"]
    for r in (ic or {}).get("resultats", []):
        titre = f"3 · IC hors échantillon (2ᵉ moitié), h = {r['horizon']} j"
        if not r.get("available"):
            out.append(f"| {titre} | {NM} | — | — |")
            continue
        out.append(f"| {titre} | {r['ic_seconde_moitie']:+.4f} | "
                   f"{_iv(r.get('ic_seconde_moitie_ic95'))} | "
                   f"p_perm {r['p_permutation']:.3f} (période entière) |")
    return out


def _lignes_q4(q4: dict) -> list[str]:
    if not q4.get("available"):
        return [f"| 4 · encours d'espérance nulle | {NM} | — | — |"]
    out = []
    for y, v in q4["par_y"].items():
        e = v["encours"]
        txt = ("déjà ≤ 0 sans impact" if v["k"] == 0 else
               "> 10⁶ × le capital" if e is None else _dollars(e))
        out.append(f"| 4 · encours d'espérance nulle ({y}) | {txt} | — | "
                   f"{q4['hypothese']} |")
    return out


def markdown(r: dict) -> str:
    """Une page. `r` = {meta, q1_y05, q1_y10, q2_dd, q2_vol, q3, ic, q4, verdict}."""
    m = r.get("meta", {})
    lignes = [
        "# Rapport d'espérance nette — une page", "",
        f"Données : {m.get('mode', NM)} · {m.get('n_series', NM)} séries · "
        f"{m.get('debut', NM)} → {m.get('fin', NM)} · décision tous les "
        f"{m.get('pas', NM)} j · capital {_dollars(m.get('capital'))} · "
        f"{m.get('allers_retours', NM)} allers-retours", "",
        "| Question | Valeur | Intervalle 95 % | Note |", "|---|---|---|---|",
        _ligne_q1(r.get("q1_y05", {}), "Y = 0,5"),
        _ligne_q1(r.get("q1_y10", {}), "Y = 1,0"),
        _ligne_q2(r.get("q2_dd", {})), _ligne_q2(r.get("q2_vol", {})),
        *_lignes_q3(r.get("q3", {}), r.get("ic", {})),
        *_lignes_q4(r.get("q4", {})), "",
        f"**Verdict.** {r.get('verdict', {}).get('texte', NM)}", "",
        "Limites : allers-retours non indépendants (IC bootstrap optimiste) ; cash à "
        "0 % (avantage le livre) ; coût = barème + impact racine carrée, Y non "
        "calibré ; univers de survivants (délistés partiels).",
    ]
    return "\n".join(lignes) + "\n"
