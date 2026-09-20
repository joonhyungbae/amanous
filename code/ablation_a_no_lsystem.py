#!/usr/bin/env python3
"""
Ablation (a): No L-System (Layer 1 removed).
Random symbol sequence with same A:B count as ABAABABA (5 A, 3 B), 100 runs.
Metrics: same-symbol MC, same-symbol RC, sequential self-similarity (MC).
"""

import os
import sys
import json
import argparse
import numpy as np
from scipy import stats

# Repo root code dir
CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CODE_DIR)

from amanous_composer import get_canonical_config, compose, generate_lsystem
from ablation_metrics import (
    same_symbol_mc,
    same_symbol_rc,
    sequential_self_similarity_mc,
    section_sequence_autocorrelation,
    section_sequence_lz_complexity,
    section_sequence_information_rate,
)



# The ablations run on the symbol-only pipeline: passing the canonical sequence as an
# override gives every section generation 0, so recursion-depth modulation is off in the
# full and the ablated run alike and the two differ only in the ablated component.
CANONICAL_SEQUENCE = "ABAABABA"

def random_sequence_5A_3B(seed: int) -> str:
    """Shuffle ABAABABA (5 A, 3 B) with given seed."""
    rng = np.random.default_rng(seed)
    symbols = list("AAAABBB")  # 5 A, 3 B
    rng.shuffle(symbols)
    return "".join(symbols)


def run_full_pipeline_metrics(config) -> dict:
    """One run with canonical L-system ABAABABA; return metrics."""
    events, sequence, _ = compose(config, lsystem_sequence_override=CANONICAL_SEQUENCE, apply_hw_compensation=True)
    return {
        "same_symbol_mc": same_symbol_mc(events, sequence, config, time_key="onset_time"),
        "same_symbol_rc": same_symbol_rc(events, sequence, config, time_key="onset_time"),
        "sequential_self_sim_mc": sequential_self_similarity_mc(
            events, sequence, config, time_key="onset_time"
        ),
        "section_seq_autocorr": section_sequence_autocorrelation(
            events, sequence, config, time_key="onset_time"
        ),
        "section_seq_lz": section_sequence_lz_complexity(
            events, sequence, config, time_key="onset_time"
        ),
        "section_seq_ir": section_sequence_information_rate(sequence),
        "n_events": len(events),
        "sequence": sequence,
    }


def run_ablated(seed: int, config) -> dict:
    """One ablated run (random sequence 5A 3B)."""
    seq = random_sequence_5A_3B(seed)
    config.seed = seed
    events, sequence, _ = compose(
        config,
        lsystem_sequence_override=seq,
        apply_hw_compensation=True,
    )
    return {
        "same_symbol_mc": same_symbol_mc(events, sequence, config, time_key="onset_time"),
        "same_symbol_rc": same_symbol_rc(events, sequence, config, time_key="onset_time"),
        "sequential_self_sim_mc": sequential_self_similarity_mc(
            events, sequence, config, time_key="onset_time"
        ),
        "section_seq_autocorr": section_sequence_autocorrelation(
            events, sequence, config, time_key="onset_time"
        ),
        "section_seq_lz": section_sequence_lz_complexity(
            events, sequence, config, time_key="onset_time"
        ),
        "section_seq_ir": section_sequence_information_rate(sequence),
        "n_events": len(events),
        "sequence": sequence,
    }


def main():
    parser = argparse.ArgumentParser(description="Ablation (a): No L-System")
    parser.add_argument("--n-runs", type=int, default=100, help="Number of random sequence runs")
    parser.add_argument("--out-dir", type=str, default=CODE_DIR, help="Output directory for JSON/CSV")
    parser.add_argument("--seed", type=int, default=42, help="Seed for full pipeline reference run")
    args = parser.parse_args()

    config = get_canonical_config()
    config.seed = args.seed

    # Full pipeline (reference)
    full = run_full_pipeline_metrics(config)
    print("Full pipeline (ABAABABA):")
    print(f"  Same-symbol MC:        {full['same_symbol_mc']:.4f}")
    print(f"  Same-symbol RC:        {full['same_symbol_rc']:.4f}")
    print(f"  Sequential self-sim.:  {full['sequential_self_sim_mc']:.4f}")
    print(f"  Section-seq. autocorr: {full['section_seq_autocorr']:.4f}")
    print(f"  Section-seq. LZ:      {full['section_seq_lz']:.4f}")
    print(f"  Section-seq. IR:      {full['section_seq_ir']:.4f}")
    print(f"  N events:             {full['n_events']}")

    # Ablated: 100 runs
    ablated_list = []
    for i in range(args.n_runs):
        run_seed = args.seed + 1 + i
        ablated_list.append(run_ablated(run_seed, get_canonical_config()))

    same_mc = [r["same_symbol_mc"] for r in ablated_list if not np.isnan(r["same_symbol_mc"])]
    same_rc = [r["same_symbol_rc"] for r in ablated_list if not np.isnan(r["same_symbol_rc"])]
    seq_mc = [r["sequential_self_sim_mc"] for r in ablated_list if not np.isnan(r["sequential_self_sim_mc"])]
    autocorr_list = [r["section_seq_autocorr"] for r in ablated_list if not np.isnan(r["section_seq_autocorr"])]
    lz_list = [r["section_seq_lz"] for r in ablated_list if not np.isnan(r["section_seq_lz"])]
    ir_list = [r["section_seq_ir"] for r in ablated_list if not np.isnan(r["section_seq_ir"])]

    mean_mc = np.mean(same_mc) if same_mc else np.nan
    std_mc = np.std(same_mc, ddof=1) if len(same_mc) > 1 else 0.0
    mean_rc = np.mean(same_rc) if same_rc else np.nan
    std_rc = np.std(same_rc, ddof=1) if len(same_rc) > 1 else 0.0
    mean_seq = np.mean(seq_mc) if seq_mc else np.nan
    std_seq = np.std(seq_mc, ddof=1) if len(seq_mc) > 1 else 0.0
    mean_autocorr = np.mean(autocorr_list) if autocorr_list else np.nan
    std_autocorr = np.std(autocorr_list, ddof=1) if len(autocorr_list) > 1 else 0.0
    mean_lz = np.mean(lz_list) if lz_list else np.nan
    std_lz = np.std(lz_list, ddof=1) if len(lz_list) > 1 else 0.0
    mean_ir = np.mean(ir_list) if ir_list else np.nan
    std_ir = np.std(ir_list, ddof=1) if len(ir_list) > 1 else 0.0

    # z-score: full value's position in the random (ablated) distribution
    z_seq = (full["sequential_self_sim_mc"] - mean_seq) / std_seq if std_seq > 0 else np.nan
    z_mc = (full["same_symbol_mc"] - mean_mc) / std_mc if std_mc > 0 else np.nan
    z_rc = (full["same_symbol_rc"] - mean_rc) / std_rc if std_rc > 0 else np.nan
    z_autocorr = (full["section_seq_autocorr"] - mean_autocorr) / std_autocorr if std_autocorr > 0 else np.nan
    # LZ: full pipeline should have lower LZ (more structure) → full < mean_random → negative z
    z_lz = (full["section_seq_lz"] - mean_lz) / std_lz if std_lz > 0 else np.nan
    z_ir = (full["section_seq_ir"] - mean_ir) / std_ir if std_ir > 0 else np.nan

    # p-value: one-sided for order-sensitive (full < random for autocorr; full < random for LZ; full > random for IR)
    # L-system ABAABABA has many A-B adjacencies → more negative autocorr than random
    p_seq = float(2 * stats.norm.sf(np.abs(z_seq))) if np.isfinite(z_seq) else np.nan
    p_mc = float(2 * stats.norm.sf(np.abs(z_mc))) if np.isfinite(z_mc) else np.nan
    p_rc = float(2 * stats.norm.sf(np.abs(z_rc))) if np.isfinite(z_rc) else np.nan
    p_autocorr = float(stats.norm.cdf(z_autocorr)) if np.isfinite(z_autocorr) else np.nan  # one-sided: full < random
    p_lz = float(stats.norm.cdf(z_lz)) if np.isfinite(z_lz) else np.nan  # one-sided: full < random
    p_ir = float(stats.norm.sf(z_ir)) if np.isfinite(z_ir) else np.nan  # one-sided: full > random
    # Permutation p (correct when full is fixed): proportion of ablated runs with IR >= full
    n_ge = sum(1 for ir in ir_list if ir >= full["section_seq_ir"])
    p_ir_perm = (1 + n_ge) / (1 + len(ir_list)) if ir_list else np.nan

    print(f"\nAblated (No L-system, {args.n_runs} runs):")
    print(f"  Same-symbol MC:        {mean_mc:.4f} ± {std_mc:.4f}  (full z={z_mc:.2f}, p={p_mc:.2e})")
    print(f"  Same-symbol RC:        {mean_rc:.4f} ± {std_rc:.4f}  (full z={z_rc:.2f}, p={p_rc:.2e})")
    print(f"  Sequential self-sim.:  {mean_seq:.4f} ± {std_seq:.4f}  (full z={z_seq:.2f}, p={p_seq:.2e})")
    print(f"  Section-seq. autocorr: {mean_autocorr:.4f} ± {std_autocorr:.4f}  (full z={z_autocorr:.2f}, p={p_autocorr:.2e} one-sided)")
    print(f"  Section-seq. LZ:       {mean_lz:.4f} ± {std_lz:.4f}  (full z={z_lz:.2f}, p={p_lz:.2e} one-sided)")
    print(f"  Section-seq. IR:       {mean_ir:.4f} ± {std_ir:.4f}  (full z={z_ir:.2f}, p={p_ir:.2e} one-sided, p_perm={p_ir_perm:.2e})")

    out = {
        "ablation": "no_lsystem",
        "full_pipeline": full,
        "ablated_runs": len(ablated_list),
        "ablated": {
            "same_symbol_mc_mean": mean_mc,
            "same_symbol_mc_std": std_mc,
            "same_symbol_rc_mean": mean_rc,
            "same_symbol_rc_std": std_rc,
            "sequential_self_sim_mc_mean": mean_seq,
            "sequential_self_sim_mc_std": std_seq,
            "section_seq_autocorr_mean": mean_autocorr,
            "section_seq_autocorr_std": std_autocorr,
            "section_seq_lz_mean": mean_lz,
            "section_seq_lz_std": std_lz,
            "section_seq_ir_mean": mean_ir,
            "section_seq_ir_std": std_ir,
        },
        "comparison": {
            "z_sequential_self_sim": z_seq,
            "z_same_symbol_mc": z_mc,
            "z_same_symbol_rc": z_rc,
            "z_section_seq_autocorr": z_autocorr,
            "z_section_seq_lz": z_lz,
            "z_section_seq_ir": z_ir,
            "p_sequential_self_sim": p_seq if seq_mc else None,
            "p_same_symbol_mc": p_mc if same_mc else None,
            "p_same_symbol_rc": p_rc if same_rc else None,
            "p_section_seq_autocorr": p_autocorr if autocorr_list else None,
            "p_section_seq_lz": p_lz if lz_list else None,
            "p_section_seq_ir": p_ir if ir_list else None,
            "p_section_seq_ir_permutation": p_ir_perm if ir_list else None,
        },
        "per_run": [
            {
                "same_symbol_mc": r["same_symbol_mc"],
                "same_symbol_rc": r["same_symbol_rc"],
                "sequential_self_sim_mc": r["sequential_self_sim_mc"],
                "section_seq_autocorr": r["section_seq_autocorr"],
                "section_seq_lz": r["section_seq_lz"],
                "section_seq_ir": r["section_seq_ir"],
            }
            for r in ablated_list
        ],
    }

    out_path = os.path.join(args.out_dir, "ablation_a_no_lsystem.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {out_path}")

    # CSV summary
    import csv
    csv_path = os.path.join(args.out_dir, "ablation_a_no_lsystem.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "run", "same_symbol_mc", "same_symbol_rc", "sequential_self_sim_mc",
            "section_seq_autocorr", "section_seq_lz", "section_seq_ir",
        ])
        for i, r in enumerate(ablated_list):
            w.writerow([
                i, r["same_symbol_mc"], r["same_symbol_rc"], r["sequential_self_sim_mc"],
                r["section_seq_autocorr"], r["section_seq_lz"], r["section_seq_ir"],
            ])
    print(f"Wrote {csv_path}")

    return out


if __name__ == "__main__":
    main()
