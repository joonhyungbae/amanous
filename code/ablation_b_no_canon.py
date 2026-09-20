#!/usr/bin/env python3
"""
Ablation (b): No Tempo Canon (Layer 3 partial removal).
All sections use tempo ratio 1:1 (both voices same speed).
Metrics: VSS (and temporal component), RC (same-symbol).
"""

import os
import sys
import json
import argparse
import numpy as np
from dataclasses import replace
from scipy import stats

CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CODE_DIR)

from amanous_composer import (
    get_canonical_config,
    compose,
    SymbolConfig,
)
from ablation_metrics import (
    same_symbol_rc,
    vss_components,
    vss_temporal_per_section,
    rc_per_section,
)



# The ablations run on the symbol-only pipeline: passing the canonical sequence as an
# override gives every section generation 0, so recursion-depth modulation is off in the
# full and the ablated run alike and the two differ only in the ablated component.
CANONICAL_SEQUENCE = "ABAABABA"

def config_no_canon(config):
    """Return config with all symbol tempo_ratios set to (1.0, 1.0)."""
    new_configs = {}
    for sym, sc in config.symbol_configs.items():
        new_configs[sym] = replace(sc, tempo_ratios=(1.0, 1.0))
    return replace(config, symbol_configs=new_configs)


def main():
    parser = argparse.ArgumentParser(description="Ablation (b): No Tempo Canon")
    parser.add_argument("--out-dir", type=str, default=CODE_DIR, help="Output directory")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    seed = args.seed

    # Full pipeline
    config_full = get_canonical_config()
    config_full.seed = seed
    events_full, seq, _ = compose(config_full, lsystem_sequence_override=CANONICAL_SEQUENCE, apply_hw_compensation=True)
    vss_full = vss_components(events_full, time_key="trigger_time")
    rc_full = same_symbol_rc(events_full, seq, config_full, time_key="onset_time")

    # Ablated: 1:1 tempo
    config_abl = config_no_canon(get_canonical_config())
    config_abl.seed = seed
    events_abl, seq_abl, _ = compose(config_abl, lsystem_sequence_override=CANONICAL_SEQUENCE, apply_hw_compensation=True)
    vss_abl = vss_components(events_abl, time_key="trigger_time")
    rc_abl = same_symbol_rc(events_abl, seq_abl, config_abl, time_key="onset_time")

    # Section-level metrics (8 sections) for paired comparison
    vss_t_full_sections = vss_temporal_per_section(events_full, seq, config_full, time_key="trigger_time")
    vss_t_abl_sections = vss_temporal_per_section(events_abl, seq_abl, config_abl, time_key="trigger_time")
    rc_full_sections = rc_per_section(events_full, seq, config_full, time_key="onset_time")
    rc_abl_sections = rc_per_section(events_abl, seq_abl, config_abl, time_key="onset_time")
    # Keep paired sections: drop index i only if either full or ablated is non-finite
    vss_t_f = np.array([vss_t_full_sections[i] for i in range(len(vss_t_full_sections)) if np.isfinite(vss_t_full_sections[i]) and np.isfinite(vss_t_abl_sections[i])])
    vss_t_a = np.array([vss_t_abl_sections[i] for i in range(len(vss_t_abl_sections)) if np.isfinite(vss_t_full_sections[i]) and np.isfinite(vss_t_abl_sections[i])])
    rc_f = np.array([rc_full_sections[i] for i in range(len(rc_full_sections)) if np.isfinite(rc_full_sections[i]) and np.isfinite(rc_abl_sections[i])])
    rc_a = np.array([rc_abl_sections[i] for i in range(len(rc_abl_sections)) if np.isfinite(rc_full_sections[i]) and np.isfinite(rc_abl_sections[i])])
    n_vss, n_rc = len(vss_t_f), len(rc_f)

    # Mann-Whitney U (two independent groups of section values), exact
    u_vss, p_vss = (np.nan, np.nan)
    r_rb_vss = np.nan
    if n_vss >= 1:
        res = stats.mannwhitneyu(vss_t_f, vss_t_a, alternative="two-sided", method="exact")
        u_vss, p_vss = res.statistic, res.pvalue
        r_rb_vss = 1.0 - (2.0 * u_vss) / (n_vss * n_vss)
    u_rc, p_rc = (np.nan, np.nan)
    r_rb_rc = np.nan
    if n_rc >= 1:
        res = stats.mannwhitneyu(rc_f, rc_a, alternative="two-sided", method="exact")
        u_rc, p_rc = res.statistic, res.pvalue
        r_rb_rc = 1.0 - (2.0 * u_rc) / (n_rc * n_rc)

    # Comparison
    delta_vss_t = vss_abl["temporal"] - vss_full["temporal"]
    pct_vss_t = (delta_vss_t / vss_full["temporal"] * 100) if vss_full["temporal"] else 0
    delta_rc = rc_abl - rc_full
    pct_rc = (delta_rc / rc_full * 100) if rc_full else 0

    mean_vss_f = float(np.nanmean(vss_t_full_sections)) if vss_t_full_sections else np.nan
    std_vss_f = float(np.nanstd(vss_t_full_sections, ddof=1)) if len(vss_t_full_sections) > 1 else 0.0
    mean_vss_a = float(np.nanmean(vss_t_abl_sections)) if vss_t_abl_sections else np.nan
    std_vss_a = float(np.nanstd(vss_t_abl_sections, ddof=1)) if len(vss_t_abl_sections) > 1 else 0.0
    mean_rc_f = float(np.nanmean(rc_full_sections)) if rc_full_sections else np.nan
    std_rc_f = float(np.nanstd(rc_full_sections, ddof=1)) if len(rc_full_sections) > 1 else 0.0
    mean_rc_a = float(np.nanmean(rc_abl_sections)) if rc_abl_sections else np.nan
    std_rc_a = float(np.nanstd(rc_abl_sections, ddof=1)) if len(rc_abl_sections) > 1 else 0.0

    print("Full pipeline (3:4 and 1:√2 tempo ratios):")
    print(f"  VSS (temporal):  {vss_full['temporal']:.6f}")
    print(f"  VSS (total):     {vss_full['vss']:.4f}")
    print(f"  RC (same-symbol): {rc_full:.4f}")
    print("\nAblated (1:1 tempo for all sections):")
    print(f"  VSS (temporal):  {vss_abl['temporal']:.6f}  (Δ = {pct_vss_t:+.1f}%)")
    print(f"  VSS (total):     {vss_abl['vss']:.4f}")
    print(f"  RC (same-symbol): {rc_abl:.4f}  (Δ = {pct_rc:+.1f}%)")
    print("\nSection-level comparison (8 sections), Mann-Whitney U, rank-biserial r:")
    print(f"  VSS temporal: Full = {mean_vss_f:.4f}±{std_vss_f:.4f}, Ablated = {mean_vss_a:.4f}±{std_vss_a:.4f}, U = {u_vss}, p = {p_vss:.2e}, r = {r_rb_vss:.3f}")
    print(f"  RC same-symbol: Full = {mean_rc_f:.4f}±{std_rc_f:.4f}, Ablated = {mean_rc_a:.4f}±{std_rc_a:.4f}, U = {u_rc}, p = {p_rc:.2e}, r = {r_rb_rc:.3f}")

    out = {
        "ablation": "no_tempo_canon",
        "full_pipeline": {
            "vss_temporal": vss_full["temporal"],
            "vss_pitch": vss_full["pitch"],
            "vss_velocity": vss_full["velocity"],
            "vss": vss_full["vss"],
            "wvss": vss_full["wvss"],
            "same_symbol_rc": rc_full,
            "vss_temporal_per_section": [None if np.isnan(x) else float(x) for x in vss_t_full_sections],
            "rc_per_section": [None if np.isnan(x) else float(x) for x in rc_full_sections],
        },
        "ablated": {
            "vss_temporal": vss_abl["temporal"],
            "vss_pitch": vss_abl["pitch"],
            "vss_velocity": vss_abl["velocity"],
            "vss": vss_abl["vss"],
            "wvss": vss_abl["wvss"],
            "same_symbol_rc": rc_abl,
            "vss_temporal_per_section": [None if np.isnan(x) else float(x) for x in vss_t_abl_sections],
            "rc_per_section": [None if np.isnan(x) else float(x) for x in rc_abl_sections],
        },
        "comparison": {
            "pct_change_vss_temporal": pct_vss_t,
            "pct_change_rc": pct_rc,
            "section_level": {
                "vss_temporal_full_mean": mean_vss_f,
                "vss_temporal_full_std": std_vss_f,
                "vss_temporal_ablated_mean": mean_vss_a,
                "vss_temporal_ablated_std": std_vss_a,
                "vss_temporal_U": float(u_vss) if np.isfinite(u_vss) else None,
                "vss_temporal_p": float(p_vss) if np.isfinite(p_vss) else None,
                "vss_temporal_r": float(r_rb_vss) if np.isfinite(r_rb_vss) else None,
                "rc_full_mean": mean_rc_f,
                "rc_full_std": std_rc_f,
                "rc_ablated_mean": mean_rc_a,
                "rc_ablated_std": std_rc_a,
                "rc_U": float(u_rc) if np.isfinite(u_rc) else None,
                "rc_p": float(p_rc) if np.isfinite(p_rc) else None,
                "rc_r": float(r_rb_rc) if np.isfinite(r_rb_rc) else None,
            },
        },
    }

    out_path = os.path.join(args.out_dir, "ablation_b_no_canon.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {out_path}")

    csv_path = os.path.join(args.out_dir, "ablation_b_no_canon.csv")
    with open(csv_path, "w") as f:
        f.write("condition,vss_temporal,vss,same_symbol_rc\n")
        f.write(f"full,{vss_full['temporal']},{vss_full['vss']},{rc_full}\n")
        f.write(f"ablated,{vss_abl['temporal']},{vss_abl['vss']},{rc_abl}\n")
    print(f"Wrote {csv_path}")

    return out


if __name__ == "__main__":
    main()
