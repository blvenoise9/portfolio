"""
Scoring metric:  Score = (1/T) * Σ ∫_0^1 c(k_t, N_t) dt

Models the system as an M/M/c queue:
  - Arrivals:  Poisson process at the realized rate r_actual (jobs/hr)
  - Service:   Exp(MU_SLOT) per slot; k*SLOTS total service slots per hour
  - Queue:     unlimited waiting room; overflow cost from cost function

Run:
    python backtest.py

Outputs:
    - Per-hour console summary
    - backtest_results.png
"""

import heapq
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from scheduling_algo import (
    server_schedule, HOD_STATS, compute_hod_stats,
    _cost, _MU_SLOT, _SLOTS,
    _ALPHA_BUF, _PEAK_SHAPE,
)

# Event type tags stored in heap tuples
_ARR  = 0   # arrival
_DEP  = 1   # departure
_SCHD = 2   # schedule (capacity) change


#  Discrete Event Simulation of one hour 

def simulate_hour_des(sched_times, sched_servers, r_actual, N0=0.0, seed=None):
    """
    Simulate one hour of an M/M/c queue via discrete event simulation.

    Parameters
    ----------
    sched_times   : list[float]   activation fractions (0.0 = hour start)
    sched_servers : list[int]     number of active servers per interval
    r_actual      : float         realized arrival rate (arrivals/hr)
    N0            : float         estimated jobs in system at hour start
    seed          : int | None    RNG seed for reproducibility

    Returns
    -------
    total_cost : float   ∫_0^1 c(k_t, N_t) dt
    N_end      : int     jobs in system at end of hour
    N_trace    : list[(t, N)]
    """
    rng = np.random.default_rng(seed)

    sched = sorted(zip(sched_times, sched_servers))

    def k_at(t):
        k = sched[0][1]
        for ts, ks in sched:
            if t >= ts:
                k = ks
        return k

    # Initial state
    n0         = max(0, int(round(N0)))
    cur_k      = k_at(0.0)
    capacity   = cur_k * _SLOTS
    n_srv      = min(n0, capacity)   # jobs being served
    n_q        = max(0, n0 - n_srv)  # jobs waiting in queue
    N          = n0                  # total in system

    heap = []

    # Remaining service times for jobs already in service (memoryless)
    for _ in range(n_srv):
        heapq.heappush(heap, (rng.exponential(1.0 / _MU_SLOT), _DEP))

    # First arrival
    if r_actual > 0:
        heapq.heappush(heap, (rng.exponential(1.0 / r_actual), _ARR))

    # Mid-hour schedule changes (skip the t=0 entry)
    for t_chg, k_new in sched[1:]:
        heapq.heappush(heap, (t_chg, _SCHD, k_new))

    #  Event loop           
    total_cost = 0.0
    last_t     = 0.0
    N_trace    = [(0.0, N)]

    def integrate_to(t_next):
        nonlocal total_cost, last_t
        dt = t_next - last_t
        if dt > 1e-15:
            total_cost += _cost(cur_k, float(N)) * dt
        last_t = t_next

    while heap:
        ev      = heapq.heappop(heap)
        ev_t    = ev[0]
        ev_type = ev[1]

        if ev_t >= 1.0:
            integrate_to(1.0)
            break

        integrate_to(ev_t)

        if ev_type == _ARR:
            N += 1
            if n_srv < capacity:
                n_srv += 1
                heapq.heappush(heap,
                    (ev_t + rng.exponential(1.0 / _MU_SLOT), _DEP))
            else:
                n_q += 1
            if r_actual > 0:
                heapq.heappush(heap,
                    (ev_t + rng.exponential(1.0 / r_actual), _ARR))

        elif ev_type == _DEP:
            N    -= 1
            n_srv -= 1
            if n_q > 0:
                n_q   -= 1
                n_srv += 1
                heapq.heappush(heap,
                    (ev_t + rng.exponential(1.0 / _MU_SLOT), _DEP))

        else:  # _SCHD
            k_new      = ev[2]
            cur_k      = k_new
            capacity   = k_new * _SLOTS
            # Drain queue into newly available slots
            while n_srv < capacity and n_q > 0:
                n_q   -= 1
                n_srv += 1
                heapq.heappush(heap,
                    (ev_t + rng.exponential(1.0 / _MU_SLOT), _DEP))

        N_trace.append((ev_t, N))

    else:
        integrate_to(1.0)   # heap emptied (only if r_actual == 0)

    N_trace.append((1.0, N))
    return total_cost, N, N_trace


#  Backtest loop 

def run_backtest(csv_path, start_hour=288, n_hours=48, verbose=True, seed=0):
    """
    Evaluate server_schedule over a held-out window using DES.

    Uses actual arrival counts (from CSV) as the Poisson rate for each hour,
    so the backtest reflects genuine out-of-sample performance.
    """
    df = pd.read_csv(csv_path)
    df['hour'] = df['arrival_timestamp'].astype(int)
    arrivals_by_hour = df.groupby('hour').size()

    past_ts = df[df['hour'] < start_hour]['arrival_timestamp'].values
    results = []
    rng_seeds = np.random.SeedSequence(seed).spawn(n_hours)

    for idx, h in enumerate(range(start_hour, start_hour + n_hours)):

        # Dynamic HOD stats from all history seen so far (mirrors server_schedule)
        live_hod = compute_hod_stats(past_ts)

        hod = h % 24

        # Realized rate (what actually arrived this hour)
        r_actual = float(arrivals_by_hour.get(h, live_hod[hod]['mean']))

        # N0: steady-state of previous hour's HOD mean (r/μ_slot)
        N0_est = float(live_hod[(h - 1) % 24]['mean']) / _MU_SLOT

        # Safety rate used for k sizing (matches algorithm internals)
        r_safe = live_hod[hod]['mean'] + _ALPHA_BUF * live_hod[hod]['std']
        k_safe = max(1, int(np.ceil(r_safe * _PEAK_SHAPE / _MU_SLOT / _SLOTS)))

        # Ask the scheduling algorithm
        s_times, s_servers = server_schedule(past_ts)

        # DES: simulate with ACTUAL arrival rate (out-of-sample)
        hour_seed = int(rng_seeds[idx].generate_state(1)[0])
        h_cost, N_end, _ = simulate_hour_des(
            s_times, s_servers, r_actual, N0=N0_est, seed=hour_seed
        )

        n_actual = int(arrivals_by_hour.get(h, 0))
        results.append({
            'hour'       : h,
            'hour_of_day': hod,
            'n_arrivals' : n_actual,
            'r_actual'   : r_actual,
            'r_safe'     : round(r_safe, 0),
            'N0_est'     : round(N0_est, 2),
            'k_safe'     : k_safe,
            'k_plan'     : s_servers,
            'cost'       : h_cost,
            'N_end'      : N_end,
        })

        if verbose and (h - start_hour) % 24 == 0:
            print(f"  Hour {h:4d}  hod={hod:02d}  "
                  f"actual={n_actual:6d}  r_safe={r_safe:7.0f}  "
                  f"k={str(s_servers):<6}  "
                  f"cost=${h_cost:8.3f}  N_end={N_end:6d}")

        hour_arr = df[df['hour'] == h]['arrival_timestamp'].values
        past_ts  = np.append(past_ts, hour_arr)

    results_df = pd.DataFrame(results)
    return results_df, results_df['cost'].mean()


#  Plots 

def _robust_ylim(series, percentile=99, headroom=1.15):
    """Cap y-axis at `percentile`th value × headroom; return (0, cap)."""
    cap = np.percentile(series, percentile) * headroom
    return 0, max(cap, np.median(series) * 2)


def _annotate_clipped(ax, hours, values, ylim_top, color='crimson'):
    """Draw downward arrows for points clipped above ylim_top."""
    clipped = [(h, v) for h, v in zip(hours, values) if v > ylim_top]
    for h, v in clipped:
        ax.annotate(
            f'${v:,.0f}',
            xy=(h, ylim_top), xytext=(h, ylim_top * 0.88),
            fontsize=6.5, color=color, ha='center',
            arrowprops=dict(arrowstyle='->', color=color, lw=0.8),
        )


def plot_results(results_df, score, save_path='backtest_results.png'):
    # ── Pre-compute aggregates ─────────────────────────────────────────────────
    rdf = results_df.copy()
    rdf['day']  = (rdf['hour'] - rdf['hour'].min()) // 24
    rdf['k_val'] = [p[0] for p in rdf['k_plan']]
    n_days = rdf['day'].max() + 1
    use_daily = n_days > 14

    daily = rdf.groupby('day').agg(
        day_start = ('hour',    'min'),
        cost_mean = ('cost',    'mean'),
        cost_max  = ('cost',    'max'),
    ).reset_index()
    days = daily['day_start']

    # Per-HOD summaries (the natural unit for this workload)
    hod_grp   = rdf.groupby('hour_of_day')
    hod_cost  = hod_grp['cost'].agg(['mean', 'max', 'median'])
    hod_arr   = hod_grp['n_arrivals'].agg(['mean', 'max'])
    hod_rsafe = hod_grp['r_safe'].mean()
    hod_k     = hod_grp['k_val'].mean()

    fig = plt.figure(figsize=(18, 13))
    gs  = gridspec.GridSpec(3, 3, figure=fig, hspace=0.50, wspace=0.38)

    # ── 1: Cost over time (top, full width) ────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, :])
    hours     = results_df['hour']
    cost_vals = results_df['cost'].values
    _, y_hi   = _robust_ylim(cost_vals)
    n_clipped = int((cost_vals > y_hi).sum())

    ax1.plot(hours, cost_vals, lw=0.5, color='steelblue', alpha=0.2, zorder=1)
    if use_daily:
        ax1.plot(days, daily['cost_mean'], lw=2.2, color='steelblue',
                 label='Daily mean cost', zorder=3)
        ax1.fill_between(days, daily['cost_mean'],
                         daily['cost_max'].clip(upper=y_hi),
                         alpha=0.12, color='steelblue', label='Daily max range', zorder=2)
    ax1.axhline(score, color='crimson', lw=1.4, ls='--',
                label=f'Overall mean = ${score:.2f}/hr', zorder=4)
    ax1.set_ylim(0, y_hi)
    _annotate_clipped(ax1, hours, cost_vals, y_hi)
    clip_note = (f'  ({n_clipped} spike{"s" if n_clipped != 1 else ""} clipped — shown with arrows)'
                 if n_clipped else '')
    ax1.set_title(f'Cost per Hour  (DES){clip_note}', fontsize=11)
    ax1.set_xlabel('Hour of dataset'); ax1.set_ylabel('Cost ($)')
    ax1.legend(fontsize=9); ax1.grid(True, alpha=0.3)

    # ── 2: Avg cost by HOD  (bar + median line) ────────────────────────────────
    ax2 = fig.add_subplot(gs[1, 0])
    colors_hod = ['#c0392b' if v == hod_cost['mean'].max() else 'steelblue'
                  for v in hod_cost['mean']]
    ax2.bar(hod_cost.index, hod_cost['mean'], color=colors_hod, alpha=0.85,
            label='Mean cost')
    ax2.plot(hod_cost.index, hod_cost['median'], 'o--', color='darkorange',
             ms=4, lw=1.2, label='Median cost')
    ax2.set_title('Avg Cost by Hour of Day\n(red = worst HOD)', fontsize=10)
    ax2.set_xlabel('Hour of Day (0–23)'); ax2.set_ylabel('Cost ($)')
    ax2.legend(fontsize=8); ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_xticks(range(0, 24, 3))

    # ── 3: Arrivals by HOD vs r_safe ───────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 1])
    hods = hod_arr.index
    ax3.bar(hods, hod_arr['mean'], alpha=0.7, color='steelblue',
            label='Avg actual arrivals')
    ax3.bar(hods, hod_arr['max'] - hod_arr['mean'],
            bottom=hod_arr['mean'], alpha=0.25, color='steelblue',
            label='Max observed')
    ax3.plot(hods, hod_rsafe, 'r--o', ms=4, lw=1.4,
             label='r_safe threshold')
    ax3.set_title('Arrivals vs Safety Rate\nby Hour of Day', fontsize=10)
    ax3.set_xlabel('Hour of Day (0–23)'); ax3.set_ylabel('Jobs/hr')
    ax3.legend(fontsize=8); ax3.grid(True, alpha=0.3, axis='y')
    ax3.set_xticks(range(0, 24, 3))

    # ── 4: Server count k by HOD ───────────────────────────────────────────────
    ax4 = fig.add_subplot(gs[1, 2])
    k_colors = ['#e67e22' if v > 1.05 else 'steelblue' for v in hod_k]
    bars = ax4.bar(hod_k.index, hod_k.values, color=k_colors, alpha=0.85)
    ax4.axhline(1, color='gray', lw=0.8, ls='--', alpha=0.6)
    ax4.axhline(2, color='gray', lw=0.8, ls='--', alpha=0.6)
    ax4.set_ylim(0.5, hod_k.max() + 0.5)
    ax4.set_yticks([1, 2])
    ax4.set_yticklabels(['k=1', 'k=2'])
    ax4.set_title('Avg Server Count k\nby Hour of Day  (orange = k≥2)', fontsize=10)
    ax4.set_xlabel('Hour of Day (0–23)'); ax4.set_ylabel('Avg k chosen')
    ax4.grid(True, alpha=0.3, axis='y')
    ax4.set_xticks(range(0, 24, 3))

    # ── 5: Cost distribution (log histogram) ──────────────────────────────────
    ax5 = fig.add_subplot(gs[2, 0])
    pct_normal = 100 * (cost_vals <= score * 3).mean()
    ax5.hist(cost_vals, bins=60, color='steelblue', alpha=0.8,
             log=True, edgecolor='white', linewidth=0.3)
    ax5.axvline(score, color='crimson', lw=1.4, ls='--',
                label=f'Mean ${score:.2f}')
    ax5.axvline(np.median(cost_vals), color='darkorange', lw=1.2, ls=':',
                label=f'Median ${np.median(cost_vals):.2f}')
    ax5.set_title(f'Cost Distribution  ({pct_normal:.0f}% of hours ≤ 3× mean)',
                  fontsize=10)
    ax5.set_xlabel('Cost/hr ($)'); ax5.set_ylabel('# hours (log)')
    ax5.legend(fontsize=8); ax5.grid(True, alpha=0.3, axis='y')

    # ── 6: Cumulative cost share by HOD ───────────────────────────────────────
    ax6 = fig.add_subplot(gs[2, 1])
    total_cost_hod = hod_grp['cost'].sum().sort_values(ascending=False)
    cumshare = total_cost_hod.cumsum() / total_cost_hod.sum() * 100
    ax6.bar(total_cost_hod.index, total_cost_hod.values / total_cost_hod.sum() * 100,
            color='steelblue', alpha=0.8, label='% of total cost')
    ax6.plot(total_cost_hod.index, [cumshare[h] for h in total_cost_hod.index],
             'o-', color='crimson', ms=4, lw=1.2, label='Cumulative %')
    ax6.set_title('Cost Share by Hour of Day\n(sorted by contribution)', fontsize=10)
    ax6.set_xlabel('Hour of Day'); ax6.set_ylabel('% of total cost')
    ax6.legend(fontsize=8); ax6.grid(True, alpha=0.3, axis='y')

    # ── 7: N_end by HOD (box-style: mean ± std) ───────────────────────────────
    ax7 = fig.add_subplot(gs[2, 2])
    hod_nend = hod_grp['N_end'].agg(['mean', 'std']).fillna(0)
    ax7.bar(hod_nend.index, hod_nend['mean'], alpha=0.75,
            color='mediumseagreen', label='Mean N_end')
    ax7.errorbar(hod_nend.index, hod_nend['mean'], yerr=hod_nend['std'],
                 fmt='none', color='seagreen', capsize=2, lw=0.8, alpha=0.6)
    ax7.axhline(0, color='k', lw=0.6, ls='--')
    ax7.set_title('Avg Jobs in System at Hour End\nby Hour of Day  (bars ± 1 std)',
                  fontsize=10)
    ax7.set_xlabel('Hour of Day (0–23)'); ax7.set_ylabel('N_end')
    ax7.grid(True, alpha=0.3, axis='y')
    ax7.set_xticks(range(0, 24, 3))

    plt.suptitle(
        f'Backtest Results (DES)  |  Mean cost/hr = ${score:.4f}  '
        f'|  Hours {results_df["hour"].min()}–{results_df["hour"].max()}  '
        f'({n_days} days)  |  α_buf={_ALPHA_BUF}',
        fontsize=13, fontweight='bold', y=1.01
    )
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\n  Plot saved → {save_path}")


#  Main 

if __name__ == '__main__':
    CSV        = 'arrivals.csv'
    START_HOUR = 1848   # 70% of 2640 total hours
    N_HOURS    = 792    # 30% of 2640 total hours

    print("=" * 70)
    print(f"BACKTEST (DES)  |  Hours {START_HOUR}–{START_HOUR+N_HOURS-1}  ({N_HOURS} hold-out hours)")
    print(f"Safety buffer α = {_ALPHA_BUF}  |  Peak shape = {_PEAK_SHAPE}")
    print("=" * 70)

    results_df, score = run_backtest(CSV, START_HOUR, N_HOURS, verbose=True)

    print("\n" + "=" * 70)
    print(f"  FINAL SCORE  (mean cost/hr) : ${score:.4f}")
    print("=" * 70)

    print("\n  PER-HOUR-OF-DAY SUMMARY:")
    summary = results_df.groupby('hour_of_day').agg(
        avg_actual=('n_arrivals', 'mean'),
        avg_r_safe=('r_safe',     'mean'),
        avg_k     =('k_plan',     lambda x: round(np.mean([p[0] for p in x]), 1)),
        avg_cost  =('cost',       'mean'),
        avg_N_end =('N_end',      'mean'),
        max_cost  =('cost',       'max'),
    ).round(2)
    print(summary.to_string())

    plot_results(results_df, score)
