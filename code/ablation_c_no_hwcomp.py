#!/usr/bin/env python3
"""
Ablation (c): No Hardware Compensation (Layer 4 removed).
Raw event timestamps (trigger_time = onset_time).
Metrics: onset alignment SD (ms), velocity-timing correlation, IOI KS (L3 vs L4).
Reports both linear and power-law (c=0.5) latency models for vel-timing r.
"""

import os
import sys
import json
import argparse

CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CODE_DIR)

from amanous_composer import get_canonical_config, compose
from ablation_metrics import (
    onset_alignment_sd_ms,
    velocity_timing_correlation,
    ioi_ks_l3_vs_l4,
    latency_powerlaw_c05_fn,
)



# The ablations run on the symbol-only pipeline: passing the canonical sequence as an
# override gives every section generation 0, so recursion-depth modulation is off in the
# full and the ablated run alike and the two differ only in the ablated component.
CANONICAL_SEQUENCE = "ABAABABA"

def main():
    parser = argparse.ArgumentParser(description="Ablation (c): No Hardware Compensation")
    parser.add_argument("--out-dir", type=str, default=CODE_DIR)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    config = get_canonical_config()
    config.seed = args.seed

    # NOTE: Full pipeline onset SD = 0 is trivially exact because the same L(v) model
    # is used for both compensation and measurement. This ablation demonstrates
    # Layer 4 necessity (systematic bias without compensation), not compensation precision.

    # Full pipeline (with compensation)
    events_full, seq, _ = compose(config, lsystem_sequence_override=CANONICAL_SEQUENCE, apply_hw_compensation=True)
    align_sd_full = onset_alignment_sd_ms(events_full, compensated=True)
    r_full, p_full = velocity_timing_correlation(events_full, compensated=True)
    ks_full = ioi_ks_l3_vs_l4(events_full)

    # Ablated (no compensation): trigger_time = onset_time
    events_abl, _, _ = compose(config, lsystem_sequence_override=CANONICAL_SEQUENCE, apply_hw_compensation=False)
    # Linear latency model (matches composer)
    align_sd_abl_linear = onset_alignment_sd_ms(events_abl, compensated=False, latency_fn=None)
    r_abl_linear, p_abl_linear = velocity_timing_correlation(events_abl, compensated=False, latency_fn=None)
    # Power-law model (Eq. 5, c=0.5)
    powerlaw_fn = latency_powerlaw_c05_fn()
    align_sd_abl_power = onset_alignment_sd_ms(events_abl, compensated=False, latency_fn=powerlaw_fn)
    r_abl_power, p_abl_power = velocity_timing_correlation(events_abl, compensated=False, latency_fn=powerlaw_fn)
    ks_abl = ioi_ks_l3_vs_l4(events_abl)

    pct_align = (align_sd_abl_linear - align_sd_full) / align_sd_full * 100 if align_sd_full > 0 else (100.0 if align_sd_abl_linear > 0 else 0.0)

    print("Full pipeline (with Layer 4 compensation):")
    print(f"  Onset alignment SD (ms):  {align_sd_full:.4f}")
    print(f"  Vel.-timing correlation: r = {r_full:.4f}, p = {p_full}")
    print(f"  IOI KS (L3 vs L4):       {ks_full:.4f}")
    print("\nAblated (No Layer 4) — Linear latency model:")
    print(f"  Onset SD = {align_sd_abl_linear:.3f} ms, vel-timing r = {r_abl_linear:.3f}")
    print("Ablated (No Layer 4) — Power-law model (c=0.5):")
    print(f"  Onset SD = {align_sd_abl_power:.3f} ms, vel-timing r = {r_abl_power:.3f}")
    print(f"  IOI KS (L3 vs L4):       {ks_abl:.4f}")

    out = {
        "ablation": "no_hw_compensation",
        "full_pipeline": {
            "onset_alignment_sd_ms": align_sd_full,
            "velocity_timing_r": r_full,
            "velocity_timing_p": p_full,
            "ioi_ks_l3_vs_l4": ks_full,
        },
        "ablated": {
            "linear": {
                "onset_alignment_sd_ms": align_sd_abl_linear,
                "velocity_timing_r": r_abl_linear,
                "velocity_timing_p": p_abl_linear,
            },
            "powerlaw_c05": {
                "onset_alignment_sd_ms": align_sd_abl_power,
                "velocity_timing_r": r_abl_power,
                "velocity_timing_p": p_abl_power,
            },
            "ioi_ks_l3_vs_l4": ks_abl,
        },
        "comparison": {
            "pct_change_align_sd": pct_align,
        },
    }

    out_path = os.path.join(args.out_dir, "ablation_c_no_hwcomp.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {out_path}")

    csv_path = os.path.join(args.out_dir, "ablation_c_no_hwcomp.csv")
    with open(csv_path, "w") as f:
        f.write("condition,model,onset_alignment_sd_ms,velocity_timing_r,ioi_ks_l3_vs_l4\n")
        f.write(f"full,linear,{align_sd_full},{r_full},{ks_full}\n")
        f.write(f"ablated,linear,{align_sd_abl_linear},{r_abl_linear},{ks_abl}\n")
        f.write(f"ablated,powerlaw_c05,{align_sd_abl_power},{r_abl_power},{ks_abl}\n")
    print(f"Wrote {csv_path}")

    return out


if __name__ == "__main__":
    main()
