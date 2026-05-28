import numpy as np

# Cost parameters 
_GAMMA   = 0.33   # effective energy cost ($/kWh)
_PI      = 6.0    # idle power floor per server (kW)
_DP      = 4.0    # active power delta per job (kW)
_MU_MEM  = 0.35   # memory factor (kW)
_ALPHA   = 1.2    # complexity exponent
_LAMBDA  = 100   # SLA/congestion penalty coefficient ($/h)
_BETA    = 2.0    # congestion elasticity

# Server / queue parameters 
_SLOTS     = 20
_MU_SLOT   = 590.0        # 1 / mean_service_time = 3600 / 6.10s ≈ 590 /hr per slot
_MU_SERVER = _MU_SLOT * _SLOTS   # ~11800 completions/hr per server

# Within-hour burst peak factor 
# EDA: splitting each hour into 12 five-minute bins reveals a consistent
# ramp-up/ramp-down shape.  The peak bin (35-40 min) carries 1.497× the
# hourly mean rate.  k must be sized for this peak to avoid SLA penalty.
_PEAK_SHAPE = 1.497

# Forecast uncertainty safety buffer 
# size k for r_safe = r_mean + ALPHA_BUF × r_std.
#
# Calibrated by sweeping alpha 0–15 over the training window (hours 0–1847,
# 70/30 split) using the analytical queue model (_next_N + _cost, dt=0.005):
#
#   alpha=0–3  → k=1 always; spike hours overflow         → mean ~$529/hr
#   alpha=4    → k=2 for ~384 hrs; hod=17 still misses   → mean ~$67/hr
#   alpha=5    → analytically optimal on training data    → mean ~$5.08/hr
#                BUT hod=17 training std=1349 gives r_safe=7734, just below
#                the k_safe=2 threshold (7883) → k=1 early in test window
#   alpha=6    → hod=17 r_safe=9083 → k_safe=2 guaranteed → chosen value
#                slight over-provisioning cost on training (~$5.66/hr) is
#                acceptable to ensure robustness on the unseen test period

_ALPHA_BUF = 6.0

# Hour-of-day statistics — cold-start fallback only
# Used when fewer than 48 hours of history are available.
HOD_STATS = {
     0: {'mean':    904, 'std':  1569},
     1: {'mean':    829, 'std':  1829},
     2: {'mean':    728, 'std':  1420},
     3: {'mean':    687, 'std':  1367},
     4: {'mean':    661, 'std':  1270},
     5: {'mean':    571, 'std':  1150},
     6: {'mean':    544, 'std':  1179},
     7: {'mean':    483, 'std':   968},
     8: {'mean':    535, 'std':  1265},
     9: {'mean':    574, 'std':   893},
    10: {'mean':    714, 'std':  1016},
    11: {'mean':    935, 'std':  1643},
    12: {'mean':    868, 'std':  1858},
    13: {'mean':    861, 'std':  1483},
    14: {'mean':    896, 'std':  1194},
    15: {'mean':    999, 'std':  1345},
    16: {'mean':   1160, 'std':  1628},
    17: {'mean':   1135, 'std':  1804},
    18: {'mean':   1014, 'std':  2015},
    19: {'mean':   1072, 'std':  1888},
    20: {'mean':    945, 'std':  1447},
    21: {'mean':    910, 'std':  1504},
    22: {'mean':    993, 'std':  1666},
    23: {'mean':    922, 'std':  1565},
}

HOD_AVG = {hod: v['mean'] for hod, v in HOD_STATS.items()}


def compute_hod_stats(past_arrival_timestamps):
    """
    Compute per-hour-of-day mean and std from actual observed arrivals.

    Counts arrivals in every completed hour, groups by hour-of-day (0–23),
    and returns a dict with the same structure as HOD_STATS.

    Falls back to the static HOD_STATS entry for any HOD that has fewer
    than 2 observations, or entirely when fewer than 48 hours of history
    are available (cold-start).

    Parameters
    past_arrival_timestamps : np.ndarray
        Individual arrival timestamps in hours (same units as arrivals.csv).

    Returns
    dict  {hod: {'mean': float, 'std': float}}
    """
    if past_arrival_timestamps.size < 2:
        return HOD_STATS

    span = past_arrival_timestamps[-1] - past_arrival_timestamps[0]
    if span < 48.0:
        return HOD_STATS

    # Count arrivals in each completed integer hour
    max_hr = int(past_arrival_timestamps[-1])   # open (current) hour excluded
    hour_indices = past_arrival_timestamps.astype(int)
    hour_counts  = np.bincount(hour_indices, minlength=max_hr + 1)[:max_hr]

    # Group counts by hour-of-day
    hod_buckets = {hod: [] for hod in range(24)}
    for h, c in enumerate(hour_counts):
        hod_buckets[h % 24].append(float(c))

    stats = {}
    for hod in range(24):
        vals = np.array(hod_buckets[hod])
        if len(vals) >= 2:
            stats[hod] = {
                'mean': float(vals.mean()),
                'std':  float(vals.std()),   # population std (ddof=0)
            }
        else:
            stats[hod] = HOD_STATS[hod]     # cold-start fallback for this HOD

    return stats


def _next_N(N, k, r, dt):
    """
    Advance E[N(t)] by dt.

    Linear regime  (N > k×20):  E[N+dt] = N + (r − kμ_server)·dt
    Exponential regime (N≤k×20): dN/dt = r − N·μ_slot  (each job departs at
        rate μ_slot; total service rate = N·μ_slot when N ≤ capacity).
        Exact solution: E[N+dt] = N·e^{−μ_slot·dt} + (r/μ_slot)·(1−e^{−μ_slot·dt})
    """
    kmu = k * _MU_SERVER
    if N > k * _SLOTS:
        return max(0.0, N + (r - kmu) * dt)
    a = np.exp(-_MU_SLOT * dt)
    return N * a + (r / _MU_SLOT) * (1.0 - a)


def _cost(k, N):
    """Instantaneous cost c(k,N)"""
    elec     = _GAMMA * (k * _PI + N * _DP)
    mem      = _GAMMA * (_MU_MEM * (N ** _ALPHA))
    overflow = max(N - k * _SLOTS, 0.0)
    penalty  = _LAMBDA * ((overflow / max(k * _SLOTS, 1.0)) ** _BETA)
    return elec + mem + penalty


# Arrival rate forecast 

def _estimate_r(past_arrival_timestamps, hod_stats):
    """
    Blend forecast: r_est = 0.3×r_last + 0.7×HOD_mean.
    EDA showed this beats pure HOD mean and pure last-hour as predictors.
    Used only for the cost simulation in _optimal_k, NOT for k sizing.
    k sizing uses the safety rate r_safe = mean + ALPHA_BUF × std.
    """
    now       = past_arrival_timestamps[-1]
    next_hod  = int(now + 1.0) % 24
    curr_hour = int(now)

    # Count arrivals in the most recently completed hour
    r_last = float(np.sum(
        (past_arrival_timestamps >= curr_hour) &
        (past_arrival_timestamps <  curr_hour + 1)
    ))

    r_hod = float(hod_stats[next_hod]['mean'])
    return 0.3 * r_last + 0.7 * r_hod


def _estimate_N0(past_arrival_timestamps, hod_stats):
    """
    N0 = HOD mean of the previous hour divided by μ_slot.
    In the exponential regime the system converges to N_ss = r/μ_slot,
    so this is analytically exact (verified: MAE=0.08 vs MAE=406 for
    simulation-based reconstruction).
    """
    now      = past_arrival_timestamps[-1]
    prev_hod = int(now) % 24
    r_prev   = float(hod_stats[prev_hod]['mean'])
    return r_prev / _MU_SLOT


# Optimal server count 

def _optimal_k(r_forecast, N0, next_hod, hod_stats):
    """
    Find k minimising simulated hourly cost.

    Two-step sizing:
      1. k_min from SAFETY rate (prevents under-provisioning on high-variance hours):
            r_safe  = r_mean + ALPHA_BUF × r_std
            k_safe  = ceil(r_safe × PEAK_SHAPE / μ_slot / slots)

      2. Search [k_safe, k_safe+2] using r_forecast (point estimate) to
         find the k that minimises expected cost:
            V = min_k Σ c(k, N(t)) · dt   (Wk14 DP, 1-hour horizon)

    The separation is deliberate:
      - k_safe is a hard floor — never provisioned below it regardless of forecast
      - The simulation uses r_forecast (mean) to avoid over-provisioning cost
    """
    r_mean = float(hod_stats[next_hod]['mean'])
    r_std  = float(hod_stats[next_hod]['std'])
    r_safe = r_mean + _ALPHA_BUF * r_std

    # k floor: sized for worst-case peak bin of worst-case hour
    k_safe = max(1, int(np.ceil(r_safe * _PEAK_SHAPE / _MU_SLOT / _SLOTS)))

    dt    = 0.005
    steps = int(1.0 / dt)
    best_k, best_cost = k_safe, np.inf

    for k in range(k_safe, k_safe + 3):  # k_safe is a hard floor, never go below it
        N, total = float(N0), 0.0
        for _ in range(steps):
            N      = _next_N(N, k, r_forecast, dt)
            total += _cost(k, N) * dt
        if total < best_cost:
            best_cost = total
            best_k    = k

    return best_k


# Public API 

def server_schedule(past_arrival_timestamps):
    """
    Called every hour by the simulator.

    Derives HOD statistics dynamically from past_arrival_timestamps once
    48+ hours of history are available; falls back to the static HOD_STATS
    table during cold-start.

    Parameters
    ----------
    past_arrival_timestamps : np.ndarray
        All arrival timestamps (in hours) up to now.

    Returns
    -------
    times   : list[float]   activation fractions starting with 0.0
    servers : list[int]     number of active servers per interval
    """
    if past_arrival_timestamps.size == 0:
        return [0.0], [3]   # safe default: covers most HOD loads

    hod_stats = compute_hod_stats(past_arrival_timestamps)

    now      = past_arrival_timestamps[-1]
    next_hod = int(now + 1.0) % 24

    r  = _estimate_r(past_arrival_timestamps, hod_stats)
    N0 = _estimate_N0(past_arrival_timestamps, hod_stats)
    k  = _optimal_k(r, N0, next_hod, hod_stats)

    return [0.0], [k]
