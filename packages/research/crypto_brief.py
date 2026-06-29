"""Note de marché crypto pour Obsidian — DÉTERMINISTE (aucun texte/chiffre inventé).

Transforme le cockpit (packages.data.crypto_market.cockpit) en une note Markdown
scannable et indexable par `make vault-search`. C'est du CONTEXTE de marché, pas un
signal. Tout champ absent → "n/d" (jamais d'invention). Front-matter pour Obsidian.
"""

from __future__ import annotations


def _usd(x) -> str:
    if not isinstance(x, (int, float)):
        return "n/d"
    for div, suf in ((1e12, " T"), (1e9, " Md"), (1e6, " M")):
        if x >= div:
            return f"${x / div:.2f}{suf}"
    return f"${x:,.0f}"


def _pct(x) -> str:
    return f"{x:+.1f}%" if isinstance(x, (int, float)) else "n/d"


def _fng_str(fng: dict) -> str:
    if not fng.get("available") or fng.get("value") is None:
        return "n/d"
    return f"{int(fng['value'])} ({fng.get('label')})"


def _dom(x) -> str:
    return f"{x}%" if x is not None else "n/d"


def render(ck: dict, today: str) -> str:
    """Cockpit → Markdown (front-matter + sections). `today` = date ISO injectée."""
    ck = ck or {}
    g = ck.get("global") or {}
    se = ck.get("sentiment") or {}
    fng = ck.get("fng") or {}
    defi = ck.get("defi") or {}
    label = se.get("label", "n/d") if se.get("available") else "n/d"
    score = se.get("score", "n/d") if se.get("available") else "n/d"

    lines = [
        "---", "type: crypto_brief", f"date: {today}",
        f"humeur: {label}", f"score: {score}", "tags: [crypto, marché, contexte]",
        "---", "", f"# 🪙 Cockpit crypto — {today}", "",
        f"**Humeur marché : {label} ({score}/100)** — contexte, *pas un conseil*.",
    ]
    for d in (se.get("drivers") or []):
        lines.append(f"- {d}")

    lines += ["", "## Pouls",
              f"- Capitalisation totale : **{_usd(g.get('total_mcap'))}** "
              f"(24 h {_pct(g.get('mcap_chg_24h'))})",
              f"- Dominance : BTC {_dom(g.get('btc_dom'))} · "
              f"ETH {_dom(g.get('eth_dom'))}",
              f"- Fear & Greed : {_fng_str(fng)}",
              f"- TVL DeFi : **{_usd(defi.get('total_tvl'))}**"]

    cats = ck.get("categories") or []
    if cats:
        lines += ["", "## Narratifs (24 h)"]
        lines += [f"- {c['name']} : **{_pct(c.get('chg24h'))}**" for c in cats[:6]]

    gain = ck.get("gainers") or []
    lose = ck.get("losers") or []
    if gain or lose:
        lines += ["", "## Gagnants / Perdants 24 h"]
        lines += [f"- 📈 {m.get('sym')} {_pct(m.get('chg24h'))}" for m in gain[:5]]
        lines += [f"- 📉 {m.get('sym')} {_pct(m.get('chg24h'))}" for m in lose[:5]]

    stab = ck.get("stablecoins") or []
    off = [s for s in stab if isinstance(s.get("peg_dev"), (int, float))
           and abs(s["peg_dev"]) > 0.005]
    if off:
        lines += ["", "## ⚠ Stablecoins décrochés du peg"]
        lines += [f"- {s['sym']} : écart {s['peg_dev'] * 100:+.2f}%" for s in off]

    lines += ["", "---",
              "*Généré automatiquement (déterministe). Sources : CoinGecko, DefiLlama, "
              "alternative.me. Contexte de marché — pas un conseil financier.*", ""]
    return "\n".join(lines)
