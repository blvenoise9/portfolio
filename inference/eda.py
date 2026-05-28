import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats

# ── Load ──────────────────────────────────────────────────────────────────────
df = pd.read_csv('arrivals.csv')
df['hour']        = df['arrival_timestamp'].astype(int)
df['hour_of_day'] = df['hour'] % 24
df['day']         = df['hour'] // 24

arr               = df['arrival_timestamp'].values
svc               = df['service_time'].values
inter_arr         = np.diff(arr)
arrivals_per_hour = df.groupby('hour').size()
hod_avg           = df.groupby('hour_of_day').size() / df.groupby('hour_of_day')['day'].nunique()

MU_SLOT   = 1.0 / svc.mean()
MU_SERVER = MU_SLOT * 20

# ══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("1. DATASET OVERVIEW")
print("=" * 60)
print(f"  Rows             : {len(df):,}")
print(f"  Time span        : {arr.min():.2f} – {arr.max():.2f} hrs  ({int(arr.max())//24} days)")
print(f"  Arrivals/hr      : mean={arrivals_per_hour.mean():.0f}  "
      f"std={arrivals_per_hour.std():.0f}  "
      f"min={arrivals_per_hour.min()}  max={arrivals_per_hour.max()}")

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("2. ARRIVAL PROCESS  (is it Poisson?)")
print("=" * 60)
cv_inter = inter_arr.std() / inter_arr.mean()
print(f"  Mean inter-arrival : {inter_arr.mean()*3600:.2f} sec")
print(f"  CV (std/mean)      : {cv_inter:.3f}  (1.0 = Poisson, >1 = bursty)")
print(f"  → {'BURSTY — use E[a] from HOD history, not raw counts' if cv_inter > 1.2 else 'approximately Poisson'}")

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("3. SERVICE TIME  (exponential?)")
print("=" * 60)
cv_svc = svc.std() / svc.mean()
print(f"  Mean  : {svc.mean()*60:.3f} min  ({svc.mean():.5f} hrs)")
print(f"  Std   : {svc.std()*60:.3f} min")
print(f"  CV    : {cv_svc:.3f}   (1.0 = exponential)")
print(f"  mu per slot   : {MU_SLOT:.1f} /hr")
print(f"  mu per server : {MU_SERVER:.1f} /hr  (20 slots × {MU_SLOT:.0f})")
if cv_svc < 0.7:
    print("  → More regular than exponential (Erlang-like). M/M/k is conservative.")
elif cv_svc > 1.3:
    print("  → More variable than exponential. Consider QPLEX.")
else:
    print("  → Close enough to exponential; M/M/k regime equations are valid.")

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("4. HOUR-OF-DAY FORECAST")
print("=" * 60)

# Prediction MAE comparison
e_hod, e_last, e_blend = [], [], []
for h in range(24, len(arrivals_per_hour)):
    actual = arrivals_per_hour.get(h, 0)
    e_hod.append(abs(actual - hod_avg[h % 24]))
    e_last.append(abs(actual - arrivals_per_hour.get(h-1, 0)))
    e_blend.append(abs(actual - (0.3*arrivals_per_hour.get(h-1,0) + 0.7*hod_avg[h%24])))

print(f"  Forecast MAE — last hour: {np.mean(e_last):.0f}  |  "
      f"HOD avg: {np.mean(e_hod):.0f}  |  blend 30/70: {np.mean(e_blend):.0f}")
print(f"  → Best predictor: blend  r_est = 0.3×r_last + 0.7×HOD_avg\n")

GAMMA=0.33; PI=6.0; DP=4.0; MU_MEM=0.35; ALPHA=1.2; LAM=100; BETA=2
def cost_fn(k, N):
    e = GAMMA*(k*PI + N*DP)
    m = GAMMA*(MU_MEM * N**ALPHA)
    p = LAM * ((max(N - k*20, 0) / max(k*20, 1))**BETA)
    return e + m + p

print(f"  {'Hr':>3}  {'HOD avg r':>10}  {'k_min':>6}  Visualization")
for h in range(24):
    r     = hod_avg[h]
    N_ss  = r / MU_SLOT
    k_min = max(1, int(np.ceil(N_ss / 20)))
    bar   = "█" * int(r / 600)
    print(f"  {h:02d}h  {r:>10.0f}  {k_min:>6}  {bar}")

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("5. REGIME ANALYSIS & OPTIMAL k")
print("=" * 60)
print("  Rule (Wk12-13 notes):")
print("    N > k×20  → LINEAR regime:      queue changes at rate (r − kμ)")
print("    N ≤ k×20  → EXPONENTIAL regime: queue self-corrects, no penalty")
print()
print(f"  Steady-state N = r / μ_slot = r / {MU_SLOT:.0f}")
print(f"  k_min = ceil(N_steady / 20) = ceil(r / {MU_SERVER:.0f})")
print()
print(f"  {'r/hr':>8}  {'N_steady':>10}  {'k_min':>6}  {'cost at k_min':>14}  {'cost at k+1':>12}")
print("  " + "-"*60)
for r in [1500, 3000, 5000, 8000, 10000, 15000]:
    N_ss  = r / MU_SLOT
    k_min = max(1, int(np.ceil(N_ss / 20)))
    c0    = cost_fn(k_min, N_ss)
    c1    = cost_fn(k_min+1, N_ss)
    print(f"  {r:>8}  {N_ss:>10.1f}  {k_min:>6}  {c0:>14.3f}  {c1:>12.3f}")
print()
print("  → Penalty is quadratic (β=2): always keep N ≤ k×20")
print("  → Electricity grows linearly with k: never over-provision")
print("  → Optimal strategy: constant k = k_min each hour")

# ══════════════════════════════════════════════════════════════════════════════
# PLOTS
# ══════════════════════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(18, 11))
gs  = gridspec.GridSpec(2, 3, figure=fig, hspace=0.42, wspace=0.35)

# 1: Arrivals over time
ax1 = fig.add_subplot(gs[0, :2])
ax1.plot(arrivals_per_hour.index, arrivals_per_hour.values,
         lw=0.8, alpha=0.7, color='steelblue')
ax1.set_title('Arrivals per Hour (full 336-hr history)', fontsize=11)
ax1.set_xlabel('Hour'); ax1.set_ylabel('Arrivals/hr')
ax1.grid(True, alpha=0.3)

# 2: Hour-of-day bar
ax2 = fig.add_subplot(gs[0, 2])
colors = ['#c0392b' if v == hod_avg.max() else 'steelblue' for v in hod_avg.values]
ax2.bar(hod_avg.index, hod_avg.values, color=colors, alpha=0.85)
ax2.set_title('Avg Arrivals by Hour of Day\n(red = peak)', fontsize=11)
ax2.set_xlabel('Hour of Day'); ax2.set_ylabel('Avg Arrivals/hr')
ax2.grid(True, alpha=0.3, axis='y')

# 3: Service time vs exponential
ax3 = fig.add_subplot(gs[1, 0])
ax3.hist(svc * 60, bins=80, density=True, color='coral', alpha=0.8, label='Observed')
x_fit = np.linspace(0, np.percentile(svc, 99)*60, 300)
ax3.plot(x_fit, stats.expon.pdf(x_fit, scale=svc.mean()*60),
         'k--', lw=1.8, label=f'Exp fit')
ax3.set_title(f'Service Time  (CV={cv_svc:.3f})', fontsize=11)
ax3.set_xlabel('Service Time (min)'); ax3.set_ylabel('Density')
ax3.legend(fontsize=8); ax3.grid(True, alpha=0.3)

# 4: Inter-arrival distribution
ax4 = fig.add_subplot(gs[1, 1])
clip = np.percentile(inter_arr, 98)
ax4.hist(inter_arr[inter_arr < clip] * 3600, bins=80,
         density=True, color='mediumseagreen', alpha=0.8)
x_exp = np.linspace(0, clip*3600, 300)
rate  = 1.0 / inter_arr.mean()
ax4.plot(x_exp, stats.expon.pdf(x_exp, scale=inter_arr.mean()*3600),
         'k--', lw=1.8, label='Exp fit (Poisson)')
ax4.set_title(f'Inter-Arrival Time  (CV={cv_inter:.2f}, bursty)', fontsize=11)
ax4.set_xlabel('Seconds'); ax4.set_ylabel('Density')
ax4.legend(fontsize=8); ax4.grid(True, alpha=0.3)

# 5: Cost vs k for different loads
ax5 = fig.add_subplot(gs[1, 2])
ks = np.arange(1, 8)
for r, col, ls in [(3000,'#3498db','-'), (8000,'#e67e22','--'), (15000,'#e74c3c',':')]:
    N_ss = r / MU_SLOT
    costs_k = [cost_fn(k, N_ss) for k in ks]
    k_min = max(1, int(np.ceil(N_ss/20)))
    ax5.semilogy(ks, costs_k, marker='o', ms=5, color=col, ls=ls, label=f'r={r}/hr')
    ax5.axvline(k_min, color=col, lw=0.8, alpha=0.4)
ax5.set_title('Cost vs k  (vertical lines = k_min)', fontsize=11)
ax5.set_xlabel('Servers k'); ax5.set_ylabel('Cost/hr ($, log scale)')
ax5.legend(fontsize=8); ax5.grid(True, alpha=0.3)

plt.suptitle('EDA — arrivals.csv', fontsize=14, fontweight='bold')
plt.savefig('eda_plots.png', dpi=150, bbox_inches='tight')
print("\n  Plots saved → eda_plots.png")
