#!/usr/bin/env python3
"""
CP Calculus ε (Tolerance) sensitivity: Distribution Switching event rate and spacing.

- Vary ε from 1 ms to 100 ms in 5 ms steps; measure count and spacing of
  'Distribution Switching' (Convergence Point) events over the full interval.
- Compare how ε affects 3:4 (Rational) vs e:π (Irrational) canon event patterns.
- Goal: Show with data that ε is a compositional parameter controlling 'texture transition density',
  not just an error tolerance.

Reference: paper.tex Section 4.4, Definition (Convergence Point).
"""

import csv
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# -----------------------------------------------------------------------------
# Parameters
# -----------------------------------------------------------------------------
DURATION_SEC = 60.0  # Full piece duration (seconds)
# ε: 1 ms, 5 ms, 10 ms, ..., 100 ms (5 ms step)
EPSILON_MS = [1] + list(range(5, 101, 5))  # 1, 5, 10, ..., 100 (21 values)


def rational_34_event_times(epsilon_sec: float, duration_sec: float) -> np.ndarray:
    """
    3:4 Rational canon: T1(n)=n*1.0, T2(m)=m*0.75.
    CP when |T1 - T2| < epsilon. Return sorted merged event times in [0, duration_sec].
    """
    events = []
    n_max = int(duration_sec / 1.0) + 1
    m_max = int(duration_sec / 0.75) + 1
    for n in range(n_max):
        t1 = n * 1.0
        if t1 > duration_sec:
            break
        for m in range(m_max):
            t2 = m * 0.75
            if t2 > duration_sec:
                break
            if abs(t1 - t2) < epsilon_sec:
                t_event = (t1 + t2) / 2.0
                if 0 <= t_event <= duration_sec:
                    events.append(t_event)
    if not events:
        return np.array([])
    events = np.sort(np.unique(np.round(events, 6)))
    merged = [events[0]]
    for t in events[1:]:
        if t - merged[-1] > epsilon_sec:
            merged.append(t)
    return np.array(merged)


def irrational_epi_event_times(epsilon_sec: float, duration_sec: float) -> np.ndarray:
    """
    e:π Irrational canon: T1(n)=n/e, T2(m)=m/π.
    CP when |T1 - T2| < epsilon. Return sorted merged event times in [0, duration_sec].
    """
    e_val = np.e
    pi_val = np.pi
    n_max = int(duration_sec * e_val) + 2
    m_max = int(duration_sec * pi_val) + 2
    events = []
    for n in range(n_max):
        t1 = n / e_val
        if t1 > duration_sec:
            break
        for m in range(m_max):
            t2 = m / pi_val
            if t2 > duration_sec:
                break
            if abs(t1 - t2) < epsilon_sec:
                t_event = (t1 + t2) / 2.0
                if 0 <= t_event <= duration_sec:
                    events.append(t_event)
    if not events:
        return np.array([])
    events = np.sort(np.unique(np.round(events, 6)))
    merged = [events[0]]
    for t in events[1:]:
        if t - merged[-1] > epsilon_sec:
            merged.append(t)
    return np.array(merged)


def inter_event_intervals(event_times: np.ndarray) -> np.ndarray:
    """Event times (sorted) -> inter-event intervals in seconds."""
    if len(event_times) < 2:
        return np.array([])
    return np.diff(event_times)


def run_sweep():
    """Run ε sweep: for each ε collect event count and spacing stats for 3:4 and e:π."""
    rows = []
    for eps_ms in EPSILON_MS:
        eps_sec = eps_ms / 1000.0
        # Rational 3:4
        t_r = rational_34_event_times(eps_sec, DURATION_SEC)
        n_r = len(t_r)
        gaps_r = inter_event_intervals(t_r)
        mean_gap_r = float(np.mean(gaps_r)) if len(gaps_r) > 0 else np.nan
        std_gap_r = float(np.std(gaps_r)) if len(gaps_r) > 1 else (0.0 if len(gaps_r) == 1 else np.nan)
        rate_r = n_r / DURATION_SEC
        # Irrational e:π
        t_i = irrational_epi_event_times(eps_sec, DURATION_SEC)
        n_i = len(t_i)
        gaps_i = inter_event_intervals(t_i)
        mean_gap_i = float(np.mean(gaps_i)) if len(gaps_i) > 0 else np.nan
        std_gap_i = float(np.std(gaps_i)) if len(gaps_i) > 1 else (0.0 if len(gaps_i) == 1 else np.nan)
        rate_i = n_i / DURATION_SEC
        rows.append({
            "epsilon_ms": eps_ms,
            "count_3_4": n_r,
            "rate_3_4_per_s": rate_r,
            "mean_gap_3_4_s": mean_gap_r,
            "std_gap_3_4_s": std_gap_r,
            "count_epi": n_i,
            "rate_epi_per_s": rate_i,
            "mean_gap_epi_s": mean_gap_i,
            "std_gap_epi_s": std_gap_i,
            "duration_sec": DURATION_SEC,
        })
    return rows


def save_csv(rows: list, out_path: str) -> None:
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "epsilon_ms", "count_3_4", "rate_3_4_per_s", "mean_gap_3_4_s", "std_gap_3_4_s",
            "count_epi", "rate_epi_per_s", "mean_gap_epi_s", "std_gap_epi_s", "duration_sec"
        ])
        w.writeheader()
        w.writerows(rows)


def plot_epsilon_sensitivity(rows: list, out_dir: str) -> None:
    """Plot ε vs event rate and spacing (3:4 vs e:π)."""
    eps = [r["epsilon_ms"] for r in rows]
    c_34 = [r["count_3_4"] for r in rows]
    c_epi = [r["count_epi"] for r in rows]
    rate_34 = [r["rate_3_4_per_s"] for r in rows]
    rate_epi = [r["rate_epi_per_s"] for r in rows]
    mean_gap_34 = [r["mean_gap_3_4_s"] for r in rows]
    mean_gap_epi = [r["mean_gap_epi_s"] for r in rows]

    # Three panels at print-legible type size (the former fourth panel repeated panel 1).
    plt.rcParams.update({"font.size": 15, "axes.titlesize": 15, "legend.fontsize": 12})
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    panels = [
        (c_34, c_epi, "Event count", "Event count"),
        (rate_34, rate_epi, "Events per second", "Event rate"),
        (mean_gap_34, mean_gap_epi, "Mean inter-event interval (s)", "Mean inter-event interval"),
    ]
    for ax, (y_34, y_epi, ylabel, title) in zip(axes, panels):
        ax.plot(eps, y_34, "o-", color="C0", label="3:4 (rational)", markersize=5)
        ax.plot(eps, y_epi, "s--", color="C1", label=r"$e:\pi$ (irrational)", markersize=5)
        ax.set_xlabel("$\\epsilon$ (ms)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig_path = os.path.join(out_dir, "epsilon_sensitivity_cp_full_sweep.png")
    plt.savefig(fig_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved: {fig_path}")


def print_summary(rows: list) -> None:
    """Print summary statistics and interpretation."""
    print()
    print("=" * 70)
    print("CP Calculus ε sensitivity: summary")
    print("=" * 70)
    print(f"Interval: {DURATION_SEC} s, ε = 1–100 ms (5 ms step)")
    print()
    # Rational: largely invariant to ε
    c_34_vals = [r["count_3_4"] for r in rows]
    print("3:4 (Rational):")
    print(f"  Event count: min={min(c_34_vals)}, max={max(c_34_vals)} (almost invariant to ε)")
    print(f"  -> Exact periodicity of rational ratio keeps CP count same as ε increases.")
    print()
    # Irrational: monotonic increase with ε
    c_epi_vals = [r["count_epi"] for r in rows]
    print("e:π (Irrational):")
    print(f"  Event count: ε=1ms -> {rows[0]['count_epi']}, ε=100ms -> {rows[-1]['count_epi']}")
    print(f"  -> Monotonic increase with ε; ε acts as continuous control for texture transition density.")
    print()
    # Correlation (if 3:4 constant, r=nan -> interpret as 0)
    eps_arr = np.array([r["epsilon_ms"] for r in rows])
    r_34 = np.corrcoef(eps_arr, c_34_vals)[0, 1] if len(eps_arr) > 1 else np.nan
    r_epi = np.corrcoef(eps_arr, c_epi_vals)[0, 1] if len(eps_arr) > 1 else np.nan
    r_34_str = f"{r_34:.4f}" if not np.isnan(r_34) else "0 (invariant)"
    r_epi_str = f"{r_epi:.4f}" if not np.isnan(r_epi) else "N/A"
    print("ε vs event count correlation:")
    print(f"  3:4:   r = {r_34_str} (independent of ε)")
    print(f"  e:π:   r = {r_epi_str} (ε up -> events up)")
    print()
    print("Conclusion: ε is a compositional parameter for 'texture transition density', not just error tolerance.")
    print("=" * 70)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = script_dir

    rows = run_sweep()
    csv_path = os.path.join(out_dir, "epsilon_sensitivity_full_sweep.csv")
    save_csv(rows, csv_path)
    print(f"Saved: {csv_path}")

    plot_epsilon_sensitivity(rows, out_dir)
    print_summary(rows)


if __name__ == "__main__":
    main()
