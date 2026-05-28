"""
Sweep _ALPHA_BUF over the training window (hours 0–1847, 70% split)
to find the alpha that minimises mean analytical cost/hr.

Uses actual per-hour arrival counts from the CSV (not HOD means) so the
sweep sees real spike hours and calibrates the buffer against them.
"""

import numpy as np
import pandas as pd

from scheduling_algo import (
    HOD_STATS, compute_hod_stats, _SLOTS, _MU_SLOT, _PEAK_SHAPE,
    _cost, _next_N,
)

TRAIN_END  = 1848          # hours 0–1847  (70% of 2640)
ALPHAS     = range(0, 16)  # sweep 0–15
DT         = 0.005
STEPS      = int(1.0 / DT) # 200 steps per simulated hour

df = pd.read_csv('arrivals.csv')
df['hour'] = df['arrival_timestamp'].astype(int)
arrivals_by_hour = df.groupby('hour').size()

# Dynamic HOD stats as they will be at the START of the test window —
# computed from the training portion only (no leakage from test period).
train_ts   = df[df['hour'] < TRAIN_END]['arrival_timestamp'].values
live_stats = compute_hod_stats(train_ts)

train_hours = range(1, TRAIN_END)
actual_rates = {
    h: float(arrivals_by_hour.get(h, live_stats[h % 24]['mean']))
    for h in train_hours
}

print(f"Training window : hours 0 – {TRAIN_END - 1}  ({TRAIN_END} hrs, actual arrivals)")
print(f"HOD stats source: dynamic (computed from training data only — no leakage)")
print(f"Sweeping alpha  : {list(ALPHAS)}\n")
print(f"{'alpha':>6}  {'mean_cost/hr':>14}  {'k=1 hrs':>8}  {'k>=2 hrs':>9}  {'spike hrs >10k':>14}")
print("-" * 58)

best_alpha, best_cost = None, np.inf
results = []

for alpha in ALPHAS:
    costs  = []
    k1_hrs = 0
    k2_hrs = 0

    for h in train_hours:
        hod      = h % 24
        r_actual = actual_rates[h]

        # k sizing with this alpha using LIVE (training-only) stats
        r_safe = live_stats[hod]['mean'] + alpha * live_stats[hod]['std']
        k      = max(1, int(np.ceil(r_safe * _PEAK_SHAPE / _MU_SLOT / _SLOTS)))

        # N0: steady-state from previous HOD mean using live stats
        N = float(live_stats[(h - 1) % 24]['mean']) / _MU_SLOT

        # Analytical simulation with actual bursty arrival rate
        hour_cost = 0.0
        for _ in range(STEPS):
            N          = _next_N(N, k, r_actual, DT)
            hour_cost += _cost(k, N) * DT

        costs.append(hour_cost)
        if k == 1:
            k1_hrs += 1
        else:
            k2_hrs += 1

    mean_cost  = float(np.mean(costs))
    spike_hrs  = sum(1 for r in actual_rates.values() if r > 10_000)
    results.append((alpha, mean_cost))
    print(f"{alpha:>6}  ${mean_cost:>13.4f}  {k1_hrs:>8}  {k2_hrs:>9}  {spike_hrs:>14}")

    if mean_cost < best_cost:
        best_cost  = mean_cost
        best_alpha = alpha

print("-" * 58)
print(f"\n  Optimal alpha = {best_alpha}  (mean cost = ${best_cost:.4f}/hr)")
print(f"\n  → Update _ALPHA_BUF = {best_alpha} in scheduling_algo.py")
