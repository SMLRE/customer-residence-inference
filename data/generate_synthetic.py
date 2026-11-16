"""
Synthetic data for Customer Residence Inference (CRI).

Customers open accounts in one state, but many later move, mostly towards
Lagos. The account-opening state goes stale and is never updated. The only
evidence of where people live now is where they transact.

    customers.parquet     customer_id, open_state  (+ true_state, hidden; synthetic only, for evaluation)
    events.parquet        customer_id, month_idx, channel (BRANCH / ATM / POS), state, n_events

Behaviour that makes the problem non-trivial (and that shaped the real design):
  * ATM use is LOCAL: people withdraw near home -> a residence signal
  * branch visits follow MOBILITY: people visit branches near work or on
    trips (e.g. Ogun residents banking in Lagos where they work)
  * POS follows spending: home, work and travel mixed
  * occasional trips home ("visiting family") put activity in the opening state
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

STATES = ["LAGOS", "OGUN", "OYO", "ABUJA_FCT", "RIVERS", "KANO", "KADUNA", "ENUGU", "ANAMBRA", "DELTA",
          "EDO", "KWARA", "OSUN", "ONDO", "AKWA_IBOM", "BENUE", "PLATEAU", "IMO"]
OPEN_P = np.array([.10, .07, .09, .06, .07, .07, .06, .07, .07, .06, .05, .04, .05, .04, .03, .03, .02, .02])
# where movers go
DEST_P = {"LAGOS": .58, "ABUJA_FCT": .14, "OGUN": .08, "RIVERS": .06, "OYO": .04, "KANO": .03, "ENUGU": .03, "EDO": .02, "DELTA": .02}
COMMUTE = {"OGUN": "LAGOS", "LAGOS": "LAGOS", "ABUJA_FCT": "ABUJA_FCT"}  # Ogun residents often work in Lagos


def generate(n: int = 30000, seed: int = 13):
    rng = np.random.default_rng(seed)
    cid = np.array([f"G{5_000_000 + i}" for i in range(n)])
    open_state = rng.choice(STATES, n, p=OPEN_P / OPEN_P.sum())
    moved = rng.random(n) < 0.92
    dest = rng.choice(list(DEST_P), n, p=np.array(list(DEST_P.values())) / sum(DEST_P.values()))
    true_state = np.where(moved & (dest != open_state), dest, open_state)
    work_state = np.array([COMMUTE.get(s, s) if rng.random() < 0.55 else s for s in true_state])
    activity = rng.gamma(1.6, 1.0, n)

    rows = []
    for m in range(12):
        travel = rng.random(n) < 0.08
        trip_state = np.where(rng.random(n) < 0.6, open_state, rng.choice(STATES, n))
        for ch, lam, home_w, work_w in [("ATM", 2.2, .85, .10), ("BRANCH", 0.6, .40, .55), ("POS", 3.0, .60, .30)]:
            k = rng.poisson(lam * activity)
            u = rng.random(n)
            st = np.where(u < home_w, true_state, np.where(u < home_w + work_w, work_state, rng.choice(STATES, n)))
            st = np.where(travel, trip_state, st)
            df = pd.DataFrame({"customer_id": cid, "month_idx": m, "channel": ch, "state": st, "n_events": k})
            rows.append(df[df.n_events > 0])
    events = pd.concat(rows).groupby(["customer_id", "month_idx", "channel", "state"], as_index=False).n_events.sum()
    customers = pd.DataFrame({"customer_id": cid, "open_state": open_state, "true_state": true_state})
    return customers, events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--customers", type=int, default=30000)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "raw")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    c, e = generate(a.customers, a.seed)
    c.to_parquet(a.out / "customers.parquet", index=False)
    e.to_parquet(a.out / "events.parquet", index=False)
    print(f"customers {len(c):,} | event rows {len(e):,}")


if __name__ == "__main__":
    main()
