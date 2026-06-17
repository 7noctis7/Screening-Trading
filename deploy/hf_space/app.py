"""Démo publique **Quant Terminal** pour HuggingFace Spaces (Gradio, gratuit).

Déploiement : créez un Space « Gradio » sur huggingface.co, poussez ce dossier
(`app.py` + `requirements.txt`). Le Space construit le snapshot (synthétique par défaut —
ne committez JAMAIS votre `YAHOO.db`) et affiche perf, screener, signaux ML et sentiment.

Lancer en local :  python deploy/hf_space/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _snapshot():
    from apps.api.snapshot import build_snapshot
    return build_snapshot()


def overview() -> str:
    s = _snapshot()
    m, d = s["meta"], s["dashboard"]
    k = d["portfolio"]
    return (f"### Quant Terminal — démo\n"
            f"- **Mode données** : {m.get('mode')}  ·  univers {m.get('universe_size')} · "
            f"tradés {m.get('traded_assets')}\n"
            f"- **Portefeuille fictif** : {k['value']:,.0f} $ "
            f"(P&L {k['pnl_pct']*100:+.1f} %, {k['n_positions']} positions, "
            f"exposition {k['exposure_pct']*100:.0f} %)\n"
            f"- **VIX** : {d.get('vix', 0):.1f}  ·  profil : {m.get('profile')}\n\n"
            f"> Paper trading — aide à la décision, pas un conseil en investissement.")


def screener_rows():
    s = _snapshot()
    out = []
    for r in s["screener"]["rows"][:25]:
        out.append([r.get("symbol"), r.get("sector", ""), round(r.get("score", 0), 3),
                    None if r.get("ml_score") is None else round(r["ml_score"], 3)])
    return out


def sentiment_rows():
    s = _snapshot().get("sentiment", {})
    return [[r["symbol"], r["label"], round(r["score"], 2), r["n_news"]]
            for r in s.get("rows", [])]


def main() -> None:
    import gradio as gr
    with gr.Blocks(title="Quant Terminal", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 📈 Quant Terminal — screening & trading systématique")
        md = gr.Markdown(overview())
        with gr.Tab("Screener"):
            t1 = gr.Dataframe(headers=["Actif", "Secteur", "Score", "ML"], value=screener_rows())
        with gr.Tab("Sentiment"):
            t2 = gr.Dataframe(headers=["Actif", "Sentiment", "Score", "News"], value=sentiment_rows())
        btn = gr.Button("🔄 Rafraîchir")
        btn.click(lambda: (overview(), screener_rows(), sentiment_rows()), outputs=[md, t1, t2])
    demo.launch()


if __name__ == "__main__":
    main()
