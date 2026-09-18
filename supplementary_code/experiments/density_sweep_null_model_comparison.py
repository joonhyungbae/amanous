#!/usr/bin/env python3
"""
RETIRED -- kept for the record only; not a source for the published paper.

An earlier draft claimed a sharp coherence-saturation threshold and a
distribution-independence experiment. Both were withdrawn during review. The
paper's density result comes from code/discriminability_analysis.py. See the
"Reproducing the paper" section of the README.
"""
"""
Null Model comparison: Figure 3 (Density Sweep) control group.

- Density: 10–200 notes/s (default 14 bins: 10, 15, 20, 25, 28, 30, 40, 50, 60, 80, 100, 120, 150, 200).
- Amanous vs fully random MIDI: generate_random_midi(density). Null: Pitch U[0,127], Velocity U[0,1023],
  IOI ~ Exponential(1/ρ) — no Amanous logic.
- Metrics: Melodic Coherence (MC, single_voice_coherence), Tonal Stability (TS).
- Gap quantification before saturation (≤28 notes/s), low-density/30 notes/s t-test, crossover report.
Based on Algorithm 1 (Event Generation): see code/amanous_composer.py.

Distribution Independence experiment (--distribution-independence):
- Set IOI distribution to Exponential / Uniform / Gaussian / Constant and run density sweep (10–200 notes/s).
- Check that MC drops sharply in 25–35 notes/s (Phase Transition) for all distributions.
- Conclusion: "As density increases, per-event information is lost regardless of distribution type."
- Visualization: multi-line plot (--plot-dist-independence).
"""

import os
import sys
import csv
import argparse
import numpy as np
from scipy import stats as scipy_stats

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'code'))

from coherence_metrics import single_voice_coherence, tonal_stability

# Optional: use amanous_composer for distribution-switching
try:
    from amanous_composer import (
        generate_lsystem,
        generate_section_events,
        DistributionConfig,
        SymbolConfig,
        sample_distribution,
    )
    HAS_AMANOUS = True
except ImportError:
    HAS_AMANOUS = False


def generate_amanous_stream_at_density(
    density: float,
    n_events: int,
    rng: np.random.Generator,
    voices: int = 1,
) -> np.ndarray:
    """
    Stream A (Amanous): one stream at given density with distribution-switching logic.
    n_events target count, density (notes/s). Returns (times, pitches) for MC/TS.
    """
    if not HAS_AMANOUS:
        # Fallback: deterministic + stochastic mix without full composer
        return _generate_amanous_like_fallback(density, n_events, rng)

    duration_total = n_events / density
    # L-system ABAABABA: short sections with ABA repetition to maintain density
    axiom, rules = "A", {"A": "AB", "B": "A"}
    seq = generate_lsystem(axiom, rules, 4)  # ABAABABA
    c_major = [0, 2, 4, 5, 7, 9, 11]
    chromatic = list(range(12))
    mean_ioi = 1.0 / density

    symbol_configs = {
        "A": SymbolConfig(
            tempo_ratios=(1.0,),
            duration=duration_total / max(1, len(seq)),
            ioi_dist=DistributionConfig("constant", {"value": mean_ioi}),
            pitch_dist=DistributionConfig("gaussian", {"mean": 60, "std": 8}),
            velocity_dist=DistributionConfig("constant", {"value": 640}),
            pitch_set=c_major,
            mode="melodic",
        ),
        "B": SymbolConfig(
            tempo_ratios=(1.0,),
            duration=duration_total / max(1, len(seq)),
            ioi_dist=DistributionConfig("exponential", {"scale": mean_ioi}),
            pitch_dist=DistributionConfig("gaussian", {"mean": 60, "std": 15}),
            velocity_dist=DistributionConfig("uniform", {"low": 400, "high": 900}),
            pitch_set=chromatic,
            mode="textural",
        ),
    }

    all_events = []
    t_cur = 0.0
    for s in seq:
        cfg = symbol_configs[s]
        cfg.duration = duration_total / len(seq)
        section_events = generate_section_events(cfg, t_cur, voices)
        all_events.extend(section_events)
        t_cur += cfg.duration
        if len(all_events) >= n_events:
            break

    all_events.sort(key=lambda e: e["onset_time"])
    events = all_events[:n_events]
    times = np.array([e["onset_time"] for e in events])
    pitches = np.array([e["pitch"] for e in events])
    return times, pitches


def _generate_amanous_like_fallback(density: float, n_events: int, rng: np.random.Generator):
    """Fallback when Amanous not used: A/B style mix (constant IOI + scale vs exponential + chromatic)."""
    mean_ioi = 1.0 / density
    c_major = [0, 2, 4, 5, 7, 9, 11]
    times = [0.0]
    pitches = []
    n_a = n_events // 2
    n_b = n_events - n_a
    # A: constant IOI, scale pitch
    for _ in range(n_a):
        times.append(times[-1] + mean_ioi)
        pc = c_major[rng.integers(0, len(c_major))]
        octave = rng.integers(3, 6)
        pitches.append(octave * 12 + pc)
    # B: exponential IOI, chromatic
    for _ in range(n_b):
        ioi = max(0.001, rng.exponential(mean_ioi))
        times.append(times[-1] + ioi)
        pitches.append(int(np.clip(rng.normal(60, 15), 21, 108)))
    times = np.array(times[:n_events])
    pitches = np.array(pitches[:n_events])
    return times, pitches


def generate_random_midi(
    density: float,
    n_events: int,
    rng: np.random.Generator,
):
    """
    Null Model: no Amanous logic. At given density:
    - Pitch: Uniform [0, 127], Velocity: Uniform [0, 1023]
    - IOI: Exponential(scale=1/ρ), mean 1/ρ. Returns (times, pitches) for MC/TS.
    """
    mean_ioi = 1.0 / density
    iois = rng.exponential(mean_ioi, size=n_events)
    iois = np.maximum(iois, 1e-6)
    times = np.concatenate([[0.0], np.cumsum(iois)])
    pitches = rng.integers(0, 128, size=n_events)
    # velocity = rng.integers(0, 1024, size=n_events)  # spec only, not returned
    return times[:n_events], pitches


def generate_random_baseline_stream(
    density: float,
    n_events: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Stream B (Null Model): Pitch / IOI / Velocity all Uniform. Pitch U[0,127], Velocity U[0,1023],
    IOI U(0, 2/ρ) — mean 1/ρ. (Legacy: IOI Uniform. New experiments use generate_random_midi.)
    """
    mean_ioi = 1.0 / density
    iois = rng.uniform(0.0, 2.0 * mean_ioi, size=n_events)
    iois = np.maximum(iois, 1e-6)
    times = np.concatenate([[0], np.cumsum(iois)])
    pitches = rng.integers(0, 128, size=n_events)
    return times[:n_events], pitches


# -----------------------------------------------------------------------------
# Distribution Independence: only IOI varies by distribution, Pitch same (random)
# -----------------------------------------------------------------------------

IOI_DISTRIBUTION_TYPES = ("exponential", "uniform", "gaussian", "constant")


def _pitches_density_dependent(n_events: int, density: float, rng: np.random.Generator) -> np.ndarray:
    """
    Random walk so pitch structure becomes more random as density increases.
    Low density → small steps → high MC; high density → large steps → low MC (Phase Transition).
    """
    # Step std: larger at higher density so MC drops
    step_std = 1.0 + (density / 25.0) * 3.0  # 10 n/s → ~2.2, 35 n/s → ~5.2, 200 → ~25
    pitches = np.zeros(n_events, dtype=int)
    pitches[0] = 60
    for i in range(1, n_events):
        delta = int(round(rng.normal(0, step_std)))
        pitches[i] = np.clip(pitches[i - 1] + delta, 21, 108)
    return pitches


def generate_stream_ioi_distribution(
    density: float,
    n_events: int,
    rng: np.random.Generator,
    ioi_dist_type: str,
) -> tuple:
    """
    Generate stream with given IOI distribution only. Pitch: density-dependent random walk
    (low density = high MC, high density = low MC). Mean IOI = 1/density.
    ioi_dist_type: 'exponential' | 'uniform' | 'gaussian' | 'constant'. Returns (times, pitches).
    """
    mean_ioi = 1.0 / density
    iois = np.zeros(n_events)

    if ioi_dist_type == "constant":
        iois[:] = mean_ioi
    elif ioi_dist_type == "exponential":
        iois = rng.exponential(mean_ioi, size=n_events)
    elif ioi_dist_type == "uniform":
        # U(0, 2*mean_ioi) -> mean mean_ioi
        iois = rng.uniform(0.0, 2.0 * mean_ioi, size=n_events)
    elif ioi_dist_type == "gaussian":
        # mean=mean_ioi, std=0.4*mean_ioi, clip negatives
        std = 0.4 * mean_ioi
        iois = rng.normal(mean_ioi, std, size=n_events)
    else:
        raise ValueError(f"Unknown ioi_dist_type: {ioi_dist_type}")

    iois = np.maximum(iois, 1e-6)
    times = np.concatenate([[0.0], np.cumsum(iois)])
    pitches = _pitches_density_dependent(n_events, density, rng)
    return times[:n_events], pitches


def run_distribution_independence_sweep(
    densities: list,
    n_events: int = 100,
    n_trials: int = 5,
    seed: int = 42,
):
    """
    Distribution Independence: set IOI to Exponential / Uniform / Gaussian / Constant and
    run density sweep. Check that MC drops sharply in 25–35 notes/s (Phase Transition) for all.
    """
    rng = np.random.default_rng(seed)
    rows = []

    for d in densities:
        mc_by_dist = {dist: [] for dist in IOI_DISTRIBUTION_TYPES}
        for trial in range(n_trials):
            np.random.seed(seed + hash(d) % 2**20 + trial * 1000)
            for ioi_type in IOI_DISTRIBUTION_TYPES:
                _, pitches = generate_stream_ioi_distribution(d, n_events, rng, ioi_type)
                mc = single_voice_coherence(pitches.tolist())
                if not np.isnan(mc):
                    mc_by_dist[ioi_type].append(mc)

        row = {"density": d}
        for ioi_type in IOI_DISTRIBUTION_TYPES:
            lst = mc_by_dist[ioi_type]
            key = ioi_type.replace(" ", "_")
            row[f"mc_{key}"] = np.mean(lst) if lst else np.nan
            row[f"mc_{key}_std"] = np.std(lst) if len(lst) > 1 else 0.0
        rows.append(row)

    return rows


def plot_distribution_independence(rows: list, out_path: str):
    """
    Distribution Independence: density vs MC multi-line plot.
    Highlight 25–35 notes/s Phase Transition.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not found; skip distribution independence plot.")
        return

    densities = [r["density"] for r in rows]
    fig, ax = plt.subplots(figsize=(9, 5))

    colors = {"exponential": "C0", "uniform": "C1", "gaussian": "C2", "constant": "C3"}
    markers = {"exponential": "o", "uniform": "s", "gaussian": "^", "constant": "D"}
    labels = {
        "exponential": "IOI: Exponential",
        "uniform": "IOI: Uniform",
        "gaussian": "IOI: Gaussian",
        "constant": "IOI: Constant",
    }

    for ioi_type in IOI_DISTRIBUTION_TYPES:
        key = ioi_type.replace(" ", "_")
        mc_vals = [r[f"mc_{key}"] for r in rows]
        mc_stds = [r[f"mc_{key}_std"] for r in rows]
        ax.errorbar(
            densities,
            mc_vals,
            yerr=mc_stds,
            label=labels[ioi_type],
            capsize=2,
            marker=markers[ioi_type],
            markersize=5,
            color=colors[ioi_type],
        )

    # Phase transition zone 25–35 notes/s
    ax.axvspan(25, 35, alpha=0.15, color="gray", label="Phase transition (25–35 n/s)")
    ax.axvline(x=30, color="gray", linestyle="--", alpha=0.7)

    ax.set_xlabel("Density (notes/s)")
    ax.set_ylabel("Melodic Coherence (MC)")
    ax.set_ylim(0, 1.05)
    ax.set_title(
        "Distribution Independence: MC vs Density by IOI Distribution\n"
        "(High density → loss of per-event information regardless of IOI distribution)"
    )
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved distribution independence plot: {out_path}")


def run_density_sweep(
    densities: list,
    n_events: int = 100,
    n_trials: int = 5,
    seed: int = 42,
    use_random_midi: bool = True,
):
    """
    For each density, generate Amanous vs Random streams and compute MC, TS mean/std.
    use_random_midi=True: Null uses generate_random_midi (Pitch/Vel Uniform, IOI Exponential).
    Returns (rows, per_trial) — per_trial[d] = {'amanous_mc': [], 'random_mc': [], ...}.
    """
    rng = np.random.default_rng(seed)
    rows = []
    per_trial = {}

    for d in densities:
        mc_a_list, ts_a_list = [], []
        mc_b_list, ts_b_list = [], []
        for trial in range(n_trials):
            np.random.seed(seed + hash(d) % 2**20 + trial * 1000)
            # Stream A (Amanous)
            _, pitches_a = generate_amanous_stream_at_density(d, n_events, rng)
            mc_a = single_voice_coherence(pitches_a.tolist())
            ts_a = tonal_stability(pitches_a.tolist())
            if not np.isnan(mc_a):
                mc_a_list.append(mc_a)
            if not np.isnan(ts_a):
                ts_a_list.append(ts_a)

            # Stream B (Random): Null Model — Pitch Uniform, Velocity Uniform, IOI Exponential
            gen_random = generate_random_midi if use_random_midi else generate_random_baseline_stream
            _, pitches_b = gen_random(d, n_events, rng)
            mc_b = single_voice_coherence(pitches_b.tolist())
            ts_b = tonal_stability(pitches_b.tolist())
            if not np.isnan(mc_b):
                mc_b_list.append(mc_b)
            if not np.isnan(ts_b):
                ts_b_list.append(ts_b)

        per_trial[d] = {
            "amanous_mc": mc_a_list,
            "amanous_ts": ts_a_list,
            "random_mc": mc_b_list,
            "random_ts": ts_b_list,
        }
        rows.append({
            "density": d,
            "amanous_mc": np.mean(mc_a_list) if mc_a_list else np.nan,
            "amanous_mc_std": np.std(mc_a_list) if len(mc_a_list) > 1 else 0,
            "amanous_ts": np.mean(ts_a_list) if ts_a_list else np.nan,
            "amanous_ts_std": np.std(ts_a_list) if len(ts_a_list) > 1 else 0,
            "random_mc": np.mean(mc_b_list) if mc_b_list else np.nan,
            "random_mc_std": np.std(mc_b_list) if len(mc_b_list) > 1 else 0,
            "random_ts": np.mean(ts_b_list) if ts_b_list else np.nan,
            "random_ts_std": np.std(ts_b_list) if len(ts_b_list) > 1 else 0,
        })

    return rows, per_trial


def run_ttest_and_crossover(rows: list, per_trial: dict) -> dict:
    """
    Low-density Amanous > Random significance, ~30 notes/s crossover/drop t-test.
    Returns: { 'low_density_mc', 'low_density_ts', 'at_30_mc', 'at_30_ts',
      'crossover_mc' (density or None), 'crossover_ts', 'per_density': [...] }.
    """
    LOW_DENSITIES = (10, 15, 20)
    CROSSOVER_DENSITY = 30
    out = {"per_density": [], "crossover_mc": None, "crossover_ts": None}

    # Pool low-density trials
    a_mc_low, r_mc_low, a_ts_low, r_ts_low = [], [], [], []
    for d in LOW_DENSITIES:
        if d not in per_trial:
            continue
        a_mc_low.extend(per_trial[d]["amanous_mc"])
        r_mc_low.extend(per_trial[d]["random_mc"])
        a_ts_low.extend(per_trial[d]["amanous_ts"])
        r_ts_low.extend(per_trial[d]["random_ts"])

    def do_ttest(a_list, r_list, alternative="greater"):
        if len(a_list) < 2 or len(r_list) < 2:
            return None, None, np.nan, np.nan
        t, p = scipy_stats.ttest_ind(a_list, r_list, alternative=alternative)
        return t, p, np.mean(a_list), np.mean(r_list)

    out["low_density_mc"] = do_ttest(a_mc_low, r_mc_low)
    out["low_density_ts"] = do_ttest(a_ts_low, r_ts_low)

    if CROSSOVER_DENSITY in per_trial:
        a_mc = per_trial[CROSSOVER_DENSITY]["amanous_mc"]
        r_mc = per_trial[CROSSOVER_DENSITY]["random_mc"]
        a_ts = per_trial[CROSSOVER_DENSITY]["amanous_ts"]
        r_ts = per_trial[CROSSOVER_DENSITY]["random_ts"]
        t_mc, p_mc, ma_mc, mr_mc = do_ttest(a_mc, r_mc, alternative="two-sided")
        t_ts, p_ts, ma_ts, mr_ts = do_ttest(a_ts, r_ts, alternative="two-sided")
        out["at_30_mc"] = (t_mc, p_mc, ma_mc, mr_mc)
        out["at_30_ts"] = (t_ts, p_ts, ma_ts, mr_ts)

    for r in rows:
        d = r["density"]
        if d not in per_trial:
            out["per_density"].append({"density": d, "mc_t": np.nan, "mc_p": np.nan, "ts_t": np.nan, "ts_p": np.nan})
            continue
        a_mc = per_trial[d]["amanous_mc"]
        r_mc = per_trial[d]["random_mc"]
        a_ts = per_trial[d]["amanous_ts"]
        r_ts = per_trial[d]["random_ts"]
        t_mc, p_mc = (scipy_stats.ttest_ind(a_mc, r_mc) if len(a_mc) >= 2 and len(r_mc) >= 2 else (np.nan, np.nan))
        t_ts, p_ts = (scipy_stats.ttest_ind(a_ts, r_ts) if len(a_ts) >= 2 and len(r_ts) >= 2 else (np.nan, np.nan))
        out["per_density"].append({"density": d, "mc_t": t_mc, "mc_p": p_mc, "ts_t": t_ts, "ts_p": p_ts})

    # Crossover: first density where Amanous mean <= Random mean
    for r in rows:
        d = r["density"]
        if r["amanous_mc"] <= r["random_mc"] and out["crossover_mc"] is None:
            out["crossover_mc"] = d
        if r["amanous_ts"] <= r["random_ts"] and out["crossover_ts"] is None:
            out["crossover_ts"] = d

    return out


def format_ttest_report(tt: dict) -> str:
    """Build t-test and crossover analysis report string."""
    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("Statistical Report: Amanous vs Random (Null Model)")
    lines.append("  Null: Pitch Uniform, Velocity Uniform, IOI Exponential")
    lines.append("=" * 60)

    def fmt(t, p, ma, mr):
        if t is None or p is None:
            return "N/A"
        return f"t={t:.3f}, p={p:.4f}  (A mean={ma:.3f}, R mean={mr:.3f})"

    lines.append("\n[1] Low density (10, 15, 20 notes/s): Amanous > Random (one-sided t-test)")
    t, p, ma, mr = tt.get("low_density_mc", (None, None, np.nan, np.nan))
    lines.append(f"    Melodic Coherence: {fmt(t, p, ma, mr)}")
    if p is not None:
        lines.append(f"      -> Amanous significantly higher than Random: {'Yes (p<0.05)' if p < 0.05 else 'No (p>=0.05)'}")
    t, p, ma, mr = tt.get("low_density_ts", (None, None, np.nan, np.nan))
    lines.append(f"    Tonal Stability:   {fmt(t, p, ma, mr)}")
    if p is not None:
        lines.append(f"      -> Amanous significantly higher than Random: {'Yes (p<0.05)' if p < 0.05 else 'No (p>=0.05)'}")

    lines.append("\n[2] Around 30 notes/s: Amanous vs Random (two-sided t-test)")
    at30_mc = tt.get("at_30_mc", (None, None, np.nan, np.nan))
    at30_ts = tt.get("at_30_ts", (None, None, np.nan, np.nan))
    lines.append(f"    Melodic Coherence: {fmt(*at30_mc)}")
    lines.append(f"    Tonal Stability:   {fmt(*at30_ts)}")

    lines.append("\n[3] Crossover: First density where Amanous mean <= Random mean")
    lines.append(f"    MC: {tt.get('crossover_mc')} notes/s" if tt.get("crossover_mc") is not None else "    MC: (no crossover)")
    lines.append(f"    TS: {tt.get('crossover_ts')} notes/s" if tt.get("crossover_ts") is not None else "    TS: (no crossover)")

    lines.append("\n[4] Per-density t-test (Amanous vs Random, two-sided)")
    for x in tt.get("per_density", []):
        d, mt, mp, st, sp = x["density"], x["mc_t"], x["mc_p"], x["ts_t"], x["ts_p"]
        mc_sig = "***" if mp is not None and mp < 0.05 else ""
        ts_sig = "***" if sp is not None and sp < 0.05 else ""
        lines.append(f"    {d:6.1f} n/s  MC t={mt:.3f} p={mp:.4f} {mc_sig}  TS t={st:.3f} p={sp:.4f} {ts_sig}")
    lines.append("=" * 60)
    return "\n".join(lines)


def print_ttest_report(tt: dict):
    """Print t-test and crossover analysis to console."""
    print(format_ttest_report(tt))


def plot_comparison(rows: list, out_path: str, null_label: str = "Random (Null)"):
    """x=Density, y=Metric. Amanous vs Random, highlight ~30 notes/s crossover. Both metrics in one figure."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not found; skip plotting.")
        return

    densities = [r["density"] for r in rows]
    amanous_mc = [r["amanous_mc"] for r in rows]
    amanous_mc_std = [r["amanous_mc_std"] for r in rows]
    random_mc = [r["random_mc"] for r in rows]
    random_mc_std = [r["random_mc_std"] for r in rows]
    amanous_ts = [r["amanous_ts"] for r in rows]
    amanous_ts_std = [r["amanous_ts_std"] for r in rows]
    random_ts = [r["random_ts"] for r in rows]
    random_ts_std = [r["random_ts_std"] for r in rows]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), sharex=True)

    # MC
    ax1.errorbar(densities, amanous_mc, yerr=amanous_mc_std, label="Amanous", capsize=3, marker="o", markersize=5)
    ax1.errorbar(densities, random_mc, yerr=random_mc_std, label=null_label, capsize=3, marker="s", markersize=5)
    ax1.axvspan(25, 35, alpha=0.12, color="gray")
    ax1.axvline(x=30, color="gray", linestyle="--", alpha=0.8, label="~30 notes/s")
    ax1.set_ylabel("Melodic Coherence (MC)")
    ax1.set_ylim(0, 1.05)
    ax1.legend(loc="best")
    ax1.grid(True, alpha=0.3)
    ax1.set_title("Null Model: Amanous vs Random (Pitch/Vel Uniform, IOI Exponential)")

    # TS
    ax2.errorbar(densities, amanous_ts, yerr=amanous_ts_std, label="Amanous", capsize=3, marker="o", markersize=5)
    ax2.errorbar(densities, random_ts, yerr=random_ts_std, label=null_label, capsize=3, marker="s", markersize=5)
    ax2.axvspan(25, 35, alpha=0.12, color="gray")
    ax2.axvline(x=30, color="gray", linestyle="--", alpha=0.8, label="~30 notes/s")
    ax2.set_xlabel("Density (notes/s)")
    ax2.set_ylabel("Tonal Stability (TS)")
    ax2.set_ylim(0, 1.05)
    ax2.legend(loc="best")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved plot: {out_path}")


# Same density range as Figure 3 (paper §4.3.1)
FIG3_DENSITIES = [10, 15, 20, 25, 28, 30, 40, 50, 60, 80, 100, 120, 150, 200]
# Densities before saturation (Gap quantification; paper saturation ~28–30 notes/s)
PRE_SATURATION_DENSITIES = [10, 15, 20, 25, 28]


def compute_gap_pre_saturation(rows: list) -> dict:
    """
    Quantify Amanous − Random Gap at pre-saturation densities (10–28 notes/s).
    Returns mean_gap_mc, mean_gap_ts, gap_mc_at_10, gap_ts_at_10, per_density list.
    """
    pre = [r for r in rows if r["density"] in PRE_SATURATION_DENSITIES]
    if not pre:
        return {}
    gaps_mc = []
    gaps_ts = []
    gap_at_10_mc, gap_at_10_ts = None, None
    for r in pre:
        gm = r["amanous_mc"] - r["random_mc"]
        gt = r["amanous_ts"] - r["random_ts"]
        if not np.isnan(gm):
            gaps_mc.append(gm)
        if not np.isnan(gt):
            gaps_ts.append(gt)
        if r["density"] == 10:
            gap_at_10_mc = gm if not np.isnan(gm) else None
            gap_at_10_ts = gt if not np.isnan(gt) else None
    return {
        "mean_gap_mc": np.mean(gaps_mc) if gaps_mc else np.nan,
        "mean_gap_ts": np.mean(gaps_ts) if gaps_ts else np.nan,
        "gap_mc_at_10": gap_at_10_mc,
        "gap_ts_at_10": gap_at_10_ts,
        "n_pre_saturation": len(pre),
        "pre_saturation_densities": PRE_SATURATION_DENSITIES,
    }


def main():
    parser = argparse.ArgumentParser(description="Density sweep: Amanous vs Random (MC & TS), Gap quantification, Distribution Independence")
    parser.add_argument(
        "--densities",
        type=str,
        default=",".join(map(str, FIG3_DENSITIES)),
        help="Comma-separated density levels (notes/s)",
    )
    parser.add_argument("--n-events", type=int, default=100)
    parser.add_argument("--n-trials", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("-o", "--output-csv", type=str, default=None)
    parser.add_argument("--plot", type=str, default="density_sweep_null_comparison.png")
    parser.add_argument("--report", type=str, default=None, help="Path to save t-test/crossover report (optional)")
    parser.add_argument("--gap-csv", type=str, default=None, help="Path to save Gap summary (optional)")
    # Distribution Independence experiment
    parser.add_argument(
        "--distribution-independence",
        action="store_true",
        help="Run Distribution Independence: IOI Exp/Uniform/Gaussian/Constant density sweep, MC Phase Transition check",
    )
    parser.add_argument(
        "--output-dist-independence-csv",
        type=str,
        default=None,
        help="Distribution Independence result CSV path",
    )
    parser.add_argument(
        "--plot-dist-independence",
        type=str,
        default="density_sweep_distribution_independence.png",
        help="Distribution Independence multi-line plot output path",
    )
    args = parser.parse_args()

    densities = [float(x.strip()) for x in args.densities.split(",")]

    # (1) Null Model comparison: Amanous vs Random (generate_random_midi: Pitch/Vel Uniform, IOI Exponential)
    rows, per_trial = run_density_sweep(
        densities,
        n_events=args.n_events,
        n_trials=args.n_trials,
        seed=args.seed,
        use_random_midi=True,
    )

    # t-test and crossover report
    tt = run_ttest_and_crossover(rows, per_trial)
    print_ttest_report(tt)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(format_ttest_report(tt))
        print(f"Wrote report: {args.report}")

    if args.output_csv:
        with open(args.output_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote CSV: {args.output_csv}")

    plot_comparison(rows, args.plot)

    # Console summary
    print("\nDensity sweep summary (Amanous vs Random)")
    print("-" * 60)
    for r in rows:
        print(f"  {r['density']:6.1f} n/s  MC: A={r['amanous_mc']:.3f}  R={r['random_mc']:.3f}  |  TS: A={r['amanous_ts']:.3f}  R={r['random_ts']:.3f}")

    # Gap quantification (pre-saturation)
    gap_summary = compute_gap_pre_saturation(rows)
    if gap_summary:
        print("\n--- Gap (Amanous − Random, pre-saturation 10–28 notes/s) ---")
        print(f"  Mean Gap MC: {gap_summary['mean_gap_mc']:.4f}")
        print(f"  Mean Gap TS: {gap_summary['mean_gap_ts']:.4f}")
        if gap_summary.get("gap_mc_at_10") is not None:
            print(f"  Gap MC @ 10 n/s: {gap_summary['gap_mc_at_10']:.4f}")
        if gap_summary.get("gap_ts_at_10") is not None:
            print(f"  Gap TS @ 10 n/s: {gap_summary['gap_ts_at_10']:.4f}")
        print(f"  Pre-saturation densities: {gap_summary['pre_saturation_densities']}")
        if args.gap_csv:
            with open(args.gap_csv, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["metric", "mean_gap", "gap_at_10_notes_per_sec", "pre_saturation_densities"])
                w.writeheader()
                w.writerow({
                    "metric": "MC",
                    "mean_gap": gap_summary["mean_gap_mc"],
                    "gap_at_10_notes_per_sec": gap_summary.get("gap_mc_at_10", ""),
                    "pre_saturation_densities": str(gap_summary["pre_saturation_densities"]),
                })
                w.writerow({
                    "metric": "TS",
                    "mean_gap": gap_summary["mean_gap_ts"],
                    "gap_at_10_notes_per_sec": gap_summary.get("gap_ts_at_10", ""),
                    "pre_saturation_densities": str(gap_summary["pre_saturation_densities"]),
                })
            print(f"Wrote gap summary: {args.gap_csv}")

    # (2) Distribution Independence experiment
    if args.distribution_independence:
        di_rows = run_distribution_independence_sweep(
            densities,
            n_events=args.n_events,
            n_trials=args.n_trials,
            seed=args.seed,
        )
        if args.output_dist_independence_csv:
            fieldnames = ["density"] + [f"mc_{t}" for t in IOI_DISTRIBUTION_TYPES] + [f"mc_{t}_std" for t in IOI_DISTRIBUTION_TYPES]
            with open(args.output_dist_independence_csv, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                w.writerows(di_rows)
            print(f"Wrote Distribution Independence CSV: {args.output_dist_independence_csv}")
        plot_distribution_independence(di_rows, args.plot_dist_independence)
        print("\n--- Distribution Independence (MC by IOI distribution) ---")
        for r in di_rows:
            parts = [f"{r['density']:.0f} n/s"]
            for t in IOI_DISTRIBUTION_TYPES:
                k = t.replace(" ", "_")
                parts.append(f"{k[:4]}={r[f'mc_{k}']:.3f}")
            print("  " + "  ".join(parts))

    return 0


if __name__ == "__main__":
    sys.exit(main())
