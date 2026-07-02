"""MFE/MAE analysis of the trade journal -> concrete SL/TP corrections.
The single cheapest, highest-yield improvement loop in the system."""
from __future__ import annotations

import pandas as pd


def analyze(journal: pd.DataFrame) -> dict:
    """journal columns (R units): r_multiple, mfe_R, mae_R, win (bool)."""
    w, l = journal[journal["win"]], journal[~journal["win"]]
    out = {
        "n": len(journal), "win_rate": float(journal["win"].mean()),
        "expectancy_R": float(journal["r_multiple"].mean()),
        "profit_factor": float(w["r_multiple"].sum() / max(-l["r_multiple"].sum(), 1e-9)),
        "winners_mae_p90": float(w["mae_R"].quantile(0.9)) if len(w) else None,
        "mfe_left_on_table_R": float((journal["mfe_R"] - journal["r_multiple"]).clip(lower=0).median()),
    }
    recs = []
    if out["winners_mae_p90"] is not None and out["winners_mae_p90"] > 0.8:
        recs.append("90% of winners drew down >0.8R first: stop likely TOO TIGHT "
                    "-> widen k_sl or improve entry timing.")
    if out["mfe_left_on_table_R"] > 0.5:
        recs.append(f"Median {out['mfe_left_on_table_R']:.2f}R of favorable excursion "
                    "not captured -> loosen TP / trail wider.")
    losers_near_be = float((l["mfe_R"] > 0.75).mean()) if len(l) else 0.0
    if losers_near_be > 0.3:
        recs.append(f"{losers_near_be:.0%} of losers were once >0.75R in profit "
                    "-> add break-even move at +1R.")
    out["recommendations"] = recs or ["Stops/TP look consistent with trade behavior."]
    return out
