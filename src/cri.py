"""Run the CRI SQL models and produce relocation / corridor analytics."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, SQL = ROOT / "data" / "raw", ROOT / "sql"


def connect():
    con = duckdb.connect()
    # true_state exists ONLY in the synthetic data, for evaluation. The models never read it.
    con.execute(f"CREATE VIEW customers AS SELECT customer_id, open_state FROM read_parquet('{RAW / 'customers.parquet'}')")
    con.execute(f"CREATE VIEW truth AS SELECT customer_id, true_state FROM read_parquet('{RAW / 'customers.parquet'}')")
    con.execute(f"CREATE VIEW events AS SELECT * FROM read_parquet('{RAW / 'events.parquet'}')")
    return con


def run_models(con) -> pd.DataFrame:
    for f in ["01_state_signals.sql", "02_v1_weighted_model.sql", "03_separate_models.sql"]:
        con.execute((SQL / f).read_text())
    return con.execute("""
        SELECT c.customer_id, c.open_state,
               v.inferred_state AS v1_state, v.confidence AS v1_confidence,
               b.branch_state, b.branch_confidence,
               a.atm_state, a.atm_confidence
        FROM customers c
        LEFT JOIN cri_v1 v USING (customer_id)
        LEFT JOIN cri_branch b USING (customer_id)
        LEFT JOIN cri_atm a USING (customer_id)
        ORDER BY c.customer_id
    """).df()


def corridors(con, model: str = "cri_atm", state_col: str = "atm_state", top: int = 10) -> pd.DataFrame:
    q = (SQL / "04_corridors.sql").read_text().format(model=model, state_col=state_col)
    return con.execute(q).df().head(top)


def relocation_summary(df: pd.DataFrame, state_col: str, conf_col: str) -> dict:
    d = df.dropna(subset=[state_col])
    moved = d[state_col] != d.open_state
    inflow = d[moved].groupby(state_col).size()
    outflow = d[moved].groupby("open_state").size()
    net = inflow.sub(outflow, fill_value=0).sort_values(ascending=False)
    return {
        "customers_scored": int(len(d)),
        "relocated_share": round(float(moved.mean()), 4),
        "confidence_mix": d[conf_col].value_counts(normalize=True).round(4).to_dict(),
        "net_inflow_by_state": net.astype(int).to_dict(),
    }


def accuracy_vs_truth(con, df: pd.DataFrame) -> pd.DataFrame:
    """Synthetic-only evaluation: how often does each model recover the true residence?"""
    t = con.execute("SELECT * FROM truth").df()
    d = df.merge(t, on="customer_id")
    rows = []
    for name, sc, cc in [("V1 weighted blend", "v1_state", "v1_confidence"),
                         ("Branch model", "branch_state", "branch_confidence"),
                         ("ATM model", "atm_state", "atm_confidence")]:
        x = d.dropna(subset=[sc])
        rows.append({"model": name, "coverage": len(x) / len(d), "accuracy_all": (x[sc] == x.true_state).mean(),
                     "accuracy_HIGH": (x[x[cc] == "HIGH"][sc] == x[x[cc] == "HIGH"].true_state).mean(),
                     "share_HIGH": (x[cc] == "HIGH").mean(),
                     "accuracy_ogun_residents": (x[x.true_state == "OGUN"][sc] == "OGUN").mean()})
    return pd.DataFrame(rows).round(3)
