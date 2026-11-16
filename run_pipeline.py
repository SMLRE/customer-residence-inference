"""
End-to-end Customer Residence Inference.

    1. Generate synthetic data (if missing)
    2. Build location signals and run CRI V1 (blended) + the final design (separate branch & ATM models)
    3. Relocation share, confidence mix, net inflow by state, top migration corridors
    4. Synthetic-only check against the hidden true residence (impossible in production, possible here)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.cri import accuracy_vs_truth, connect, corridors, relocation_summary, run_models

ROOT = Path(__file__).parent
REPORTS, FIG = ROOT / "reports", ROOT / "reports" / "figures"
ACCENT = "#E8A54B"
plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False})


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    if not (ROOT / "data/raw/events.parquet").exists():
        subprocess.run([sys.executable, str(ROOT / "data/generate_synthetic.py")], check=True)
    con = connect()
    df = run_models(con)

    summ = {"v1_blended": relocation_summary(df, "v1_state", "v1_confidence"),
            "atm_model": relocation_summary(df, "atm_state", "atm_confidence"),
            "branch_model": relocation_summary(df, "branch_state", "branch_confidence")}
    for k, v in summ.items():
        print(f"{k:13s} relocated {v['relocated_share']:.1%} | HIGH {v['confidence_mix'].get('HIGH', 0):.1%} | "
              f"top net inflow {list(v['net_inflow_by_state'].items())[:2]}")
    cor = corridors(con, "cri_atm", "atm_state")
    acc = accuracy_vs_truth(con, df)
    print(cor); print(acc.to_string())

    # disagreement between the two final models = commuters / mobile customers
    both = df.dropna(subset=["atm_state", "branch_state"])
    disagree = (both.atm_state != both.branch_state).mean()

    # ---- figures
    net = pd.Series(summ["atm_model"]["net_inflow_by_state"]).sort_values()
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.barh(net.index, net.values, color=["#3C8D5A" if v > 0 else "#D9534F" for v in net.values])
    ax.set_xlabel("net customers gained (+) / lost (−)"); ax.set_title("Net migration by state (ATM residence model)")
    fig.tight_layout(); fig.savefig(FIG / "net_inflow_by_state.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    lab = cor.open_state + " → " + cor.inferred_state
    ax.barh(lab[::-1], cor.customers[::-1], color=ACCENT)
    ax.set_xlabel("customers"); ax.set_title("Top 10 migration corridors")
    fig.tight_layout(); fig.savefig(FIG / "top_corridors.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.bar(acc.model, acc.accuracy_ogun_residents * 100, color=["#8A8A8A", "#5B8DEF", ACCENT])
    for i, v in enumerate(acc.accuracy_ogun_residents * 100):
        ax.text(i, v + 1, f"{v:.0f}%", ha="center")
    ax.set_ylabel("% correctly placed in Ogun"); ax.set_ylim(0, 110)
    ax.set_title("Ogun residents who commute to Lagos (synthetic truth)")
    fig.tight_layout(); fig.savefig(FIG / "commuter_test.png"); plt.close(fig)

    df.to_csv(REPORTS / "cri_inferred_locations.csv", index=False)
    metrics = {**summ, "top_corridors_atm": cor.to_dict(orient="records"),
               "branch_vs_atm_disagreement": round(float(disagree), 4),
               "synthetic_accuracy_vs_truth": acc.to_dict(orient="records")}
    (REPORTS / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    print(f"branch vs ATM model disagree for {disagree:.1%} of customers")
    return metrics


if __name__ == "__main__":
    main()
